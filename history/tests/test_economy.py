from decimal import Decimal as D

from core import ticks
from history import economy, params
from history.constants import Priority, Status
from history.models import NewsItem
from market.tests.base import MarketBase

from .base import AuditMixin


class PriceTrendNewsTests(AuditMixin, MarketBase):
    """Mesmo cálculo de tendência do 17; limiar e intervalo mínimo parametrizados (12.4, 12.12)."""

    def trend_sales(self, last, prev=1_000, qty=100):
        self.sell("flour", qty, prev, day=3)             # 7 dias anteriores
        self.sell("flour", qty, last, day=10)            # últimos 7 dias
        self.go(14, 0)

    def news(self):
        return list(NewsItem.objects.filter(category="economy"))

    def test_a_rise_above_the_threshold_publishes_a_headline_with_the_real_percentage(self):
        self.trend_sales(1_080)
        checks = economy.check_price_trends(self.clk.now())
        self.assertEqual([(c.product, c.outcome) for c in checks], [("flour", "published")])
        n = self.news()[0]
        self.assertIn("8%", n.headline + n.body)
        self.assertIn("Farinha", n.headline + n.body)
        self.assertEqual((n.ref_kind, n.ref_id, n.priority), ("product", "flour", int(Priority.MINOR_ECONOMIC)))
        self.assertEqual(D(n.data["pct"]).quantize(D("0.01")), D("8.00"))
        self.assertEqual(n.data["last_7d"]["volume"], 100)           # dado estruturado de origem guardado (12.11)

    def test_a_fall_publishes_a_fall_headline(self):
        self.trend_sales(900)
        economy.check_price_trends(self.clk.now())
        n = self.news()[0]
        self.assertEqual(n.template_key, "economy.price_down")
        self.assertIn("10%", n.headline + n.body)

    def test_small_oscillation_never_publishes(self):
        self.trend_sales(1_049)                          # +4,9% < 5%
        self.assertEqual([c.outcome for c in economy.check_price_trends(self.clk.now())], ["below_threshold"])
        self.assertEqual(self.news(), [])

    def test_exactly_the_threshold_publishes(self):
        self.trend_sales(1_050)                          # +5,0%
        self.assertEqual([c.outcome for c in economy.check_price_trends(self.clk.now())], ["published"])

    def test_no_data_in_one_of_the_periods_is_not_news_and_never_zero(self):
        self.sell("flour", 100, 1_080, day=10)           # só o período atual
        self.go(14, 0)
        self.assertEqual([c.outcome for c in economy.check_price_trends(self.clk.now())], ["no_data"])
        self.assertEqual(self.news(), [])

    def test_a_big_move_is_a_major_economic_event_and_outranks_a_small_one(self):
        self.trend_sales(1_300)                          # +30%
        economy.check_price_trends(self.clk.now())
        self.assertEqual(self.news()[0].priority, int(Priority.MAJOR_ECONOMIC))

    def test_rerunning_the_same_day_does_not_duplicate(self):
        self.trend_sales(1_080)
        economy.check_price_trends(self.clk.now())
        again = economy.check_price_trends(self.clk.now())
        self.assertEqual([c.outcome for c in again], ["duplicate"])
        self.assertEqual(len(self.news()), 1)

    def test_the_same_product_does_not_repeat_inside_the_minimum_interval_but_does_after_it(self):
        self.trend_sales(1_080)
        economy.check_price_trends(self.clk.now())
        self.go(15, 0)                                   # 1 dia depois: ainda com tendência acima do limiar
        self.assertEqual([c.outcome for c in economy.check_price_trends(self.clk.now())], ["suppressed"])
        self.go(14 + params.INDICATOR_MIN_INTERVAL_SECONDS // 86400, 0)
        self.sell("flour", 100, 1_200, day=14 + 3, hour=1)       # sai o período antigo: nova tendência acima do limiar
        self.go(14 + 3, 2)
        self.assertEqual([c.outcome for c in economy.check_price_trends(self.clk.now())], ["published"])
        self.assertEqual(len(self.news()), 2)

    def test_the_world_daily_tick_publishes_it_once_after_the_market_rollup(self):
        self.sell("flour", 100, 1_000, day=3)            # o mundo processa os ticks À MEDIDA que o tempo passa (sem ver vendas futuras)
        self.go(10, 0)
        ticks.advance_world()
        self.assertEqual(self.news(), [])
        self.sell("flour", 100, 1_080, day=10)
        self.go(14, 0)
        ticks.advance_world()
        items = sorted(self.news(), key=lambda n: n.at)
        # o 1º tick com os dois períodos de dados é o do dia 11; os dos dias 12 e 13 caem no intervalo mínimo; o do dia 14 (exatamente 3 dias depois) passa
        self.assertEqual([n.at for n in items], [self.at(11, 0), self.at(14, 0)])
        self.assertTrue(all(n.template_key == "economy.price_up" for n in items))
        ticks.advance_world()                            # nada novo pendente: idempotente
        self.assertEqual(len(self.news()), 2)

    def test_the_check_reads_aggregates_not_the_raw_transaction_history_of_old_days(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.trend_sales(1_080)
        from market import rollup
        rollup.ensure_closed(self.day0 + 13, at=self.clk.now())               # dias fechados: a consulta seguinte só lê os agregados
        with CaptureQueriesContext(connection) as ctx:
            economy.check_price_trends(self.clk.now())
        raw = [q["sql"] for q in ctx.captured_queries if 'FROM "market_markettransaction"' in q["sql"]]
        # só o dia corrente é calculado ao vivo (limitado por índice); dias fechados não tocam a tabela bruta
        for sql in raw:
            self.assertIn("competence_day", sql, sql)
