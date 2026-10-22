"""Estatísticas por Produto (design/17 §17.3-17.13, §17.20): só vendas concluídas; "Sem dados"; produção/consumo reais; tendência; gráficos."""
from decimal import Decimal

from catalog import services as catalog
from companies import stock
from inventory import services as inventory
from inventory.constants import Operation
from market import rollup, stats
from market.constants import NO_DATA, OK, WINDOW_24H
from market.models import DailyProductStat
from players import registry

from .base import MarketBase

D = Decimal


class PriceStatsTests(MarketBase):
    def now_stats(self, product="flour"):
        return stats.product_stats(product, self.clk.now())

    def test_without_sales_every_price_indicator_is_no_data_and_never_zero_or_the_catalog_base_price(self):
        self.go(0)
        s = self.now_stats()
        for name in ("avg_price", "min_price", "max_price", "trend"):
            self.assertEqual((s[name].status, s[name].value), (NO_DATA, None), name)
        self.assertGreater(catalog.get_product("flour").base_price, 0)       # existe um preço-base, e ele NÃO aparece
        self.assertEqual(stats.product_stats("nothing"), None)

    def test_the_average_is_weighted_by_quantity(self):
        self.sell("flour", 10, 1_000, day=0, hour=12)
        self.sell("flour", 100, 2_000, day=0, hour=13)
        self.go(0, 14)
        s = self.now_stats()
        self.assertEqual(s["avg_price"].status, OK)
        self.assertEqual(s["avg_price"].value.quantize(D("0.01")), D("1909.09"))         # R$ 19,09: não é a média simples (R$ 15)
        self.assertEqual((s["avg_price"].detail["transactions"], s["avg_price"].detail["quantity"],
                          s["avg_price"].detail["value_cents"]), (2, 110, 210_000))

    def test_min_and_max_come_only_from_completed_sales(self):
        self.sell("flour", 3, 1_500, day=0, hour=12)
        self.sell("flour", 1, 900, day=0, hour=13)
        self.sell("flour", 7, 2_200, day=0, hour=14)
        self.go(0, 15)
        s = self.now_stats()
        self.assertEqual((s["min_price"].value, s["max_price"].value), (900, 2_200))
        # um produto com preço-base mas sem venda continua sem dados; vendas de outro produto não vazam
        other = self.now_stats("wheat")
        self.assertEqual((other["min_price"].status, other["avg_price"].status), (NO_DATA, NO_DATA))

    def test_the_24h_window_is_moving_and_exclusive_at_its_start(self):
        base = self.at(0, 12)
        self.sell("flour", 1, 1_000, day=0, hour=12)                                  # t = base
        pid = catalog.get_product("flour").pk
        self.assertEqual(stats.avg_price_24h(pid, base - 1).status, NO_DATA)                  # venda "no futuro": fora
        self.assertEqual(stats.avg_price_24h(pid, base).value, 1_000)                         # o instante da venda: dentro
        self.assertEqual(stats.avg_price_24h(pid, base + WINDOW_24H - 1).value, 1_000)        # ainda dentro
        self.assertEqual(stats.avg_price_24h(pid, base + WINDOW_24H).status, NO_DATA)         # exatamente 24 h atrás: fora

    def test_the_effective_price_is_the_practiced_one_regardless_of_the_base_price(self):
        base = catalog.get_product("flour").base_price
        self.sell("flour", 5, 10 * 100 * 3, day=0)                                    # R$ 30 por unidade, longe de qualquer base
        self.go(0, 13)
        self.assertEqual(self.now_stats()["avg_price"].value, 3_000)
        self.assertNotEqual(self.now_stats()["avg_price"].value, base)


class SupplyAndUsageTests(MarketBase):
    def test_the_available_stock_is_no_data_until_a_supply_system_reports_it_and_a_real_zero_is_not_no_data(self):
        self.go(0)
        pid = catalog.get_product("flour").pk
        self.assertEqual(stats.available_stock(pid).status, NO_DATA)
        rollup.register_supply_provider("test_supply", lambda: {pid: 0})
        self.assertEqual((stats.available_stock(pid).status, stats.available_stock(pid).value), (OK, 0))
        rollup.unregister_supply_provider("test_supply")
        rollup.register_supply_provider("test_supply", lambda: {pid: 40})
        rollup.register_supply_provider("test_supply_b", lambda: {pid: 2, 999: 5})
        self.addCleanup(rollup.unregister_supply_provider, "test_supply_b")
        self.assertEqual(stats.available_stock(pid).value, 42)                       # soma dos provedores
        with self.assertRaises(ValueError):
            rollup.register_supply_provider("test_supply", lambda: {})

    def test_production_and_consumption_come_from_real_events_and_buying_or_selling_is_not_consuming(self):
        self.go(0)
        for _ in range(4):
            self.hook()                                                              # Trabalhar: produz Farinha e consome Trigo
        from companies.models import StockMovement
        produced = sum(StockMovement.objects.filter(operation="production", product__key="flour").values_list("delta", flat=True))
        used = -sum(StockMovement.objects.filter(operation="input_consumption", product__key="wheat").values_list("delta", flat=True))
        self.assertGreater(produced, 0)
        self.assertGreater(used, 0)
        # compras e vendas movem estoque/dinheiro, mas não são consumo
        self.assertTrue(stock.credit_stock(self.firm, "wheat", 50, origin="test", key="buy:wheat", reference_kind="test", reference_id="1").ok)
        self.sell("wheat", 50, 100, buyer=("company", self.firm), seller=("player", self.third.pk), day=0)
        flour = stats.usage_24h(catalog.get_product("flour").pk, self.clk.now())
        wheat = stats.usage_24h(catalog.get_product("wheat").pk, self.clk.now())
        self.assertEqual((flour["production"].value, flour["consumption"].value), (produced, 0))
        self.assertEqual((wheat["production"].value, wheat["consumption"].value), (0, used))
        self.assertEqual(wheat["consumption"].detail["recipe_inputs"], used)

    def test_player_consumption_counts_and_a_period_without_events_is_a_real_zero(self):
        self.go(0)
        self.assertTrue(inventory.credit(self.third.pk, "bread", 3, operation=Operation.PURCHASE, origin="test", key="give:bread",
                                         reference_kind="test", reference_id="1").ok)
        pid = catalog.get_product("bread").pk
        self.assertEqual(stats.usage_24h(pid, self.clk.now())["consumption"].value, 0)      # ter o item não é consumir
        res = registry.execute_action(self.third.pk, "consume", "bread")
        self.assertTrue(res.ok, res)
        use = stats.usage_24h(pid, self.clk.now())
        self.assertEqual((use["consumption"].value, use["consumption"].detail["player_consumption"]), (1, 1))
        self.clk.set(self.clk.now() + WINDOW_24H + 1)
        self.assertEqual(stats.usage_24h(pid, self.clk.now())["consumption"].value, 0)       # saiu da janela


class TrendAndChartTests(MarketBase):
    def test_trend_compares_the_last_7_days_with_the_7_before_by_weighted_averages(self):
        self.sell("flour", 100, 1_000, day=3)               # 7 dias anteriores: R$ 10,00
        self.sell("flour", 100, 1_080, day=10)              # últimos 7 dias: R$ 10,80
        self.go(14)
        t = stats.trend(catalog.get_product("flour").pk, self.clk.now())
        self.assertEqual((t.status, t.value.quantize(D("0.01"))), (OK, D("8.00")))
        self.assertEqual((t.detail["previous_7d"]["volume"], t.detail["last_7d"]["volume"]), (100, 100))

    def test_trend_averages_are_weighted_by_quantity_inside_each_period(self):
        self.sell("flour", 10, 1_000, day=2)
        self.sell("flour", 90, 2_000, day=5)                 # média anterior = 1.900
        self.sell("flour", 100, 1_900, day=12)               # média atual = 1.900
        self.go(14)
        self.assertEqual(stats.trend(catalog.get_product("flour").pk, self.clk.now()).value, 0)

    def test_without_sales_in_both_periods_the_trend_is_no_data_never_zero(self):
        pid = catalog.get_product("flour").pk
        self.go(9)
        self.assertEqual(stats.trend(pid, self.clk.now()).status, NO_DATA)
        self.sell("flour", 100, 1_080, day=10)               # só o período atual
        self.go(14)
        t = stats.trend(pid, self.clk.now())
        self.assertEqual((t.status, t.value), (NO_DATA, None))
        self.assertIsNone(t.detail["previous_7d"])

    def test_period_boundaries_are_calendar_days_of_the_game(self):
        pid = catalog.get_product("flour").pk
        self.sell("flour", 10, 1_000, day=7, hour=23, minute=59)       # último segundo dos 7 dias anteriores (today = 14)
        self.sell("flour", 10, 2_000, day=8, hour=0)                   # primeiro instante dos últimos 7 dias
        self.go(14)
        t = stats.trend(pid, self.clk.now())
        self.assertEqual((t.detail["previous_7d"]["volume"], t.detail["last_7d"]["volume"], t.value), (10, 10, 100))

    def test_the_30_day_chart_has_one_point_per_day_and_no_sale_means_no_price(self):
        self.sell("flour", 10, 1_000, day=2)
        self.sell("flour", 30, 2_000, day=2, hour=15)
        self.sell("flour", 5, 3_000, day=9)
        self.go(10)
        c = stats.charts("flour", self.clk.now())
        self.assertEqual(len(c["price"]), 30)
        self.assertEqual(len(c["supply_demand"]), 30)
        by_day = {p["day"] - self.day0: p for p in c["price"]}
        self.assertEqual(by_day[2]["avg_price_cents"], D(70_000) / 40)
        self.assertEqual((by_day[9]["avg_price_cents"], by_day[9]["volume"]), (3_000, 5))
        self.assertIsNone(by_day[5]["avg_price_cents"])                  # sem venda: sem preço (não 0, não o preço-base)
        self.assertEqual(by_day[5]["volume"], 0)
        self.assertEqual(sum(p["volume"] for p in c["price"]), 45)
        self.assertIsNone(stats.charts("nothing"))

    def test_the_chart_matches_the_stored_aggregates_and_a_live_day_matches_itself_once_closed(self):
        self.sell("flour", 10, 1_000, day=0)
        self.sell("flour", 20, 1_500, day=1, hour=10)
        live = {p["day"]: p for p in stats.charts("flour", self.clk.now())["price"]}[self.day0 + 1]      # dia corrente, ao vivo
        self.assertEqual(DailyProductStat.objects.filter(day=self.day0 + 1).count(), 0)                 # o dia corrente nunca é gravado
        self.go(2, 1)                                                                                    # o dia 1 acabou
        closed = {p["day"]: p for p in stats.charts("flour", self.clk.now())["price"]}[self.day0 + 1]
        self.assertEqual(live, closed)
        row = DailyProductStat.objects.get(day=self.day0 + 1, product__key="flour")
        self.assertEqual((row.volume, row.value_cents, row.min_price_cents, row.max_price_cents), (20, 30_000, 1_500, 1_500))

    def test_the_overview_ranks_risers_fallers_and_volume_only_among_products_with_enough_data(self):
        for product, prev in (("flour", 1_000), ("wheat", 1_000), ("bread", 1_000)):
            self.sell(product, 10, prev, day=3)
        for product, last in (("flour", 1_200), ("wheat", 800), ("bread", 1_050)):
            self.sell(product, 10, last, day=10)
        self.sell("cheese", 10, 5_000, day=10)                 # só um período: não entra em altas/quedas, entra no volume
        self.sell("cheese", 1, 5_000, day=14, hour=2)
        ov = stats.market_overview(self.clk.now())
        self.assertEqual([r["product"] for r in ov["risers"]], ["flour", "bread"])
        self.assertEqual([r["product"] for r in ov["fallers"]], ["wheat"])
        self.assertEqual(ov["risers"][0]["trend_pct"].quantize(D("0.01")), D("20.00"))
        self.assertEqual(ov["top_volume"][0]["product"], "cheese")                            # 24 h: só a venda de hoje
        self.assertEqual(len(ov["top_volume"]), 1)
        self.assertEqual(stats.market_overview(self.at(40), limit=3), {"risers": [], "fallers": [], "top_volume": []})

    def test_the_number_of_queries_does_not_grow_with_the_history(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.sell("flour", 1, 1_000, day=0)
        self.go(5)
        stats.product_stats("flour", self.clk.now())            # fecha os dias (uma vez)
        with CaptureQueriesContext(connection) as small:
            stats.product_stats("flour", self.clk.now())
        for i in range(30):
            self.sell("flour", 1, 1_000 + i, day=5, hour=12, minute=i)
        with CaptureQueriesContext(connection) as large:
            stats.product_stats("flour", self.clk.now())
        self.assertEqual(len(small), len(large))
        self.assertLessEqual(len(large), 12, [q["sql"][:80] for q in large.captured_queries])
