"""Agregação diária (design/17 §17.10, §17.19): histórico bruto → dia fechado → páginas consultam o agregado. Idempotente e auditável."""
from core import ticks
from ledger.models import Entry
from market import rollup
from market.audit import audit_market
from market.models import CompanyCostDay, DailyProductStat, RollupMark

from .base import MarketBase


class RollupTests(MarketBase):
    def test_closing_a_day_stores_exactly_what_the_raw_history_says_and_is_idempotent(self):
        self.sell("flour", 10, 1_000, day=0, hour=12)
        self.sell("flour", 30, 2_000, day=0, hour=13)
        self.hook()
        self.go(1, 1)
        self.assertTrue(rollup.close_day(self.day0, at=self.clk.now()))
        row = DailyProductStat.objects.get(day=self.day0, product__key="flour")
        self.assertEqual((row.transactions, row.volume, row.value_cents, row.min_price_cents, row.max_price_cents, row.available_stock),
                         (2, 40, 70_000, 1_000, 2_000, None))
        self.assertGreater(row.production, 0)
        before = (DailyProductStat.objects.count(), CompanyCostDay.objects.count(), RollupMark.objects.count())
        self.assertFalse(rollup.close_day(self.day0, at=self.clk.now()))             # já fechado: nada muda
        self.assertEqual((DailyProductStat.objects.count(), CompanyCostDay.objects.count(), RollupMark.objects.count()), before)
        self.assertEqual(rollup.ensure_closed(self.day0), [])
        self.assertTrue(audit_market().ok)

    def test_ensure_closed_fills_the_missing_days_from_the_first_activity_and_never_the_current_day(self):
        self.assertEqual(rollup.ensure_closed(self.day0 + 5), [])                    # sem atividade nenhuma: nada a fechar
        self.sell("flour", 1, 1_000, day=2)
        self.go(6)
        closed = rollup.ensure_closed(self.day0 + 5, at=self.clk.now())
        self.assertEqual(closed, [self.day0 + 2, self.day0 + 3, self.day0 + 4, self.day0 + 5])
        self.assertEqual(rollup.ensure_closed(self.day0 + 5), [])
        self.assertEqual(sorted(RollupMark.objects.values_list("day", flat=True)), closed)
        self.assertEqual(DailyProductStat.objects.count(), 1)                        # só o dia com atividade tem linha por produto
        self.assertTrue(audit_market().ok)

    def test_the_daily_tick_closes_the_day_that_ended_with_a_snapshot_of_the_supply_and_catches_up(self):
        from catalog.models import Product
        pid = Product.objects.get(key="flour").pk
        self.sell("flour", 5, 1_000, day=0, hour=13)
        rollup.register_supply_provider("test_supply", lambda: {pid: 77})
        self.go(3, 0, 5)                                                              # três dias depois, logo após a meia-noite
        ticks.advance_world()
        self.assertEqual(sorted(RollupMark.objects.values_list("day", flat=True)), [self.day0, self.day0 + 1, self.day0 + 2])
        first = DailyProductStat.objects.get(day=self.day0, product__key="flour")
        self.assertEqual((first.volume, first.available_stock), (5, None))            # tick atrasado: a oferta de agora NÃO vira a do dia antigo
        last = DailyProductStat.objects.filter(day=self.day0 + 2)
        self.assertFalse(last.exists())                                               # sem atividade nesse dia: sem linha
        self.go(4, 0, 5)
        ticks.advance_world()
        self.assertIn(self.day0 + 3, RollupMark.objects.values_list("day", flat=True))
        self.assertTrue(audit_market().ok)

    def test_a_tick_with_no_market_activity_stores_no_product_rows_but_the_owner_payroll_is_a_real_cost(self):
        self.go(2, 0, 5)
        ticks.advance_world()
        self.assertEqual(DailyProductStat.objects.count(), 0)
        rows = sorted(CompanyCostDay.objects.values_list("day", "category", "amount_cents"))
        self.assertEqual({(c, a) for _, c, a in rows}, {("salaries", 1_900), ("taxes", 100)})     # folha do Dono: líquido + IR, da conta da empresa
        self.assertEqual({d for d, _, _ in rows}, {self.day0 + 1})                  # o dia 2 (corrente) ainda não é gravado

    def test_the_supply_snapshot_is_taken_only_by_a_tick_processed_on_its_own_day(self):
        from catalog.models import Product
        pid = Product.objects.get(key="flour").pk
        self.sell("flour", 5, 1_000, day=0, hour=13)
        rollup.register_supply_provider("test_supply", lambda: {pid: 77})
        self.go(1, 0, 5)                                                              # o tick da meia-noite roda a tempo
        ticks.advance_world()
        self.assertEqual(DailyProductStat.objects.get(day=self.day0, product_id=pid).available_stock, 77)

    def test_buying_and_selling_are_not_consumption_in_the_aggregate_either(self):
        self.sell("wheat", 50, 100, buyer=("company", self.firm), seller=("player", self.third.pk), day=0)
        self.go(1, 1)
        rollup.ensure_closed(self.day0, at=self.clk.now())
        row = DailyProductStat.objects.get(day=self.day0, product__key="wheat")
        self.assertEqual((row.volume, row.production, row.consumption), (50, 0, 0))

    def test_the_audit_detects_tampered_aggregates_marks_and_early_closing(self):
        self.audit_market_at_end = False
        self.sell("flour", 10, 1_000, day=0)
        self.go(2)
        rollup.ensure_closed(self.day0 + 1, at=self.clk.now())
        self.assertTrue(audit_market().ok)
        DailyProductStat.objects.filter(day=self.day0).update(volume=11)
        codes = {f["code"] for f in audit_market().findings}
        self.assertEqual(codes, {"AGGREGATE_VALUE_MISMATCH"})
        DailyProductStat.objects.filter(day=self.day0).delete()
        self.assertEqual({f["code"] for f in audit_market().findings}, {"AGGREGATE_ROW_MISMATCH"})
        RollupMark.objects.filter(day=self.day0).delete()
        DailyProductStat.objects.create(product_id=1, day=self.day0, volume=1)
        self.assertEqual({f["code"] for f in audit_market().findings}, {"AGGREGATE_WITHOUT_MARK"})
        DailyProductStat.objects.all().delete()
        RollupMark.objects.create(day=self.day0 + 2, computed_at=self.clk.now())                  # o dia corrente nem terminou
        self.assertIn("DAY_CLOSED_BEFORE_IT_ENDED", {f["code"] for f in audit_market().findings})

    def test_the_audit_detects_a_sale_whose_payment_or_arithmetic_no_longer_matches(self):
        self.audit_market_at_end = False
        self.sell("flour", 10, 1_000, day=0)
        from market.models import MarketTransaction
        MarketTransaction.objects.update(quantity=11, total_cents=11_000)
        self.assertEqual({f["code"] for f in audit_market().findings}, {"SALE_ENTRY_MISSING"})
        MarketTransaction.objects.update(quantity=10, total_cents=10_000, competence_day=self.day0 + 1, seller_id=10 ** 9)
        self.assertEqual({f["code"] for f in audit_market().findings}, {"COMPETENCE_DAY_MISMATCH", "PARTY_MISSING"})
        MarketTransaction.objects.update(channel="x")
        self.assertIn("INVALID_ENUM_VALUE", {f["code"] for f in audit_market().findings})

    def test_the_audit_cli_exits_with_an_error_when_something_is_wrong_and_exports_json(self):
        from io import StringIO
        from django.core.management import call_command
        from django.core.management.base import CommandError
        self.audit_market_at_end = False
        self.sell("flour", 10, 1_000, day=0)
        out = StringIO()
        call_command("audit_market", "--json", stdout=out)
        self.assertIn('"ok": true', out.getvalue())
        from market.models import MarketTransaction
        MarketTransaction.objects.update(quantity=11, total_cents=11_000)
        with self.assertRaises(CommandError):
            call_command("audit_market", stdout=StringIO())

    def test_windowed_usage_queries_have_the_time_indexes(self):
        from companies.models import StockMovement
        from inventory.models import InventoryMovement
        for model in (StockMovement, InventoryMovement):
            self.assertTrue(any(i.fields == ["operation", "at"] for i in model._meta.indexes), model)
