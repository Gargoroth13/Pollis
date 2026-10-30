"""Materiais da obra (G5, GD 2026-10-29): consumo CONFIGURÁVEL; tabela vazia e consumo desligado por padrão; trilha de estoque; bloqueio antes de gastar Energia."""
from decimal import Decimal
from unittest import mock

from companies import construction, params, stock
from companies.constants import StockOperation
from companies.models import ConstructionWork, StockItem, StockMovement, WorkWage

from .test_construction import ConstructionBase

D = Decimal
TABLE = {"low_density_simple": {"cement": 2, "wood": 1}}


class MaterialsTests(ConstructionBase):
    def configure(self, consumes=True, table=None):
        for target, value in (("CONSTRUCTION_CONSUMES_MATERIALS", consumes), ("CONSTRUCTION_MATERIALS_PER_WORK", TABLE if table is None else table)):
            patcher = mock.patch.object(params, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def give(self, product, quantity, n=[0]):
        n[0] += 1
        res = stock.credit_stock(self.build, product, quantity, origin="test", key=f"mat{n[0]}", reference_kind="test", reference_id=str(n[0]))
        self.assertTrue(res.ok, res)

    def have(self, product):
        item = StockItem.objects.filter(company_id=self.build, product__key=product).first()
        return 0 if item is None else item.quantity

    def test_by_default_nothing_is_consumed_and_the_table_is_empty_no_number_invented(self):
        self.assertEqual((params.CONSTRUCTION_CONSUMES_MATERIALS, params.CONSTRUCTION_MATERIALS_PER_WORK), (False, {}))
        self.start()
        self.assertTrue(self.builder_work().ok)
        self.assertEqual(StockMovement.objects.filter(reference_kind="construction_work").count(), 0)

    def test_without_stock_the_work_is_blocked_before_spending_energy_and_pays_nothing(self):
        self.configure()
        self.start()
        self.set_state(self.mason, energy=D(100))
        res = self.builder_work()
        self.assertEqual((res.ok, res.code), (False, "CONSTRUCTION_NO_MATERIALS"))
        self.assertEqual(WorkWage.objects.filter(player=self.mason).count(), 0)
        self.assertEqual(ConstructionWork.objects.count(), 0)
        self.assertEqual(self.state(self.mason).energy, D(100))

    def test_partial_stock_still_blocks_and_nothing_is_consumed(self):
        self.configure()
        self.give("cement", 2)                                         # falta a madeira
        self.start()
        self.assertEqual(self.builder_work().code, "CONSTRUCTION_NO_MATERIALS")
        self.assertEqual(self.have("cement"), 2)

    def test_each_work_consumes_the_configured_units_through_the_immutable_stock_trail(self):
        self.configure()
        self.give("cement", 5)
        self.give("wood", 3)
        self.start()
        res = self.builder_work()
        self.assertTrue(res.ok, res)
        self.assertEqual((self.have("cement"), self.have("wood")), (3, 2))
        moves = StockMovement.objects.filter(reference_kind="construction_work").order_by("product__key")
        self.assertEqual([(m.product.key, m.delta, m.operation, m.destination) for m in moves],
                         [("cement", -2, StockOperation.INPUT_CONSUMPTION.value, "construction"), ("wood", -1, StockOperation.INPUT_CONSUMPTION.value, "construction")])
        self.assertEqual(ConstructionWork.objects.get().explained["materials_consumed"], {"cement": 2, "wood": 1})
        self.assertEqual(self.codes(), set())                          # a auditoria confere trabalho × movimentos de estoque

    def test_the_stock_runs_out_and_the_construction_stops_exactly_there(self):
        self.configure()
        self.give("cement", 4)
        self.give("wood", 2)
        self.start()
        self.assertTrue(self.builder_work().ok)
        self.assertTrue(self.builder_work().ok)
        self.assertEqual(self.builder_work().code, "CONSTRUCTION_NO_MATERIALS")
        self.assertEqual((self.have("cement"), self.have("wood")), (0, 0))
        self.assertEqual(ConstructionWork.objects.count(), 2)
        self.assertEqual(self.codes(), set())

    def test_a_project_without_a_table_line_consumes_nothing_even_with_the_switch_on(self):
        self.configure(table={"high_density_simple": {"cement": 9}})
        self.start()
        self.assertTrue(self.builder_work().ok)
        self.assertEqual(StockMovement.objects.filter(reference_kind="construction_work").count(), 0)

    def test_the_check_action_shows_the_block(self):
        from players import registry
        self.configure()
        self.start()
        self.assertIn("CONSTRUCTION_NO_MATERIALS", registry.check_action(self.mason.pk, "work", None).blocked_by)

    def test_the_construction_company_may_buy_only_the_configured_materials(self):
        from companies import trade
        self.assertEqual(trade.purchase_refusal(self.build, "cement").code, "NO_VALID_USE")           # padrão: consumo desligado
        self.configure()
        self.assertIsNone(trade.purchase_refusal(self.build, "cement"))
        self.assertEqual(trade.purchase_refusal(self.build, "steel").code, "NO_VALID_USE")           # fora da tabela

    def test_the_audit_flags_tampered_materials(self):
        from django.db import connection
        self.configure()
        self.give("cement", 5)
        self.give("wood", 3)
        self.start()
        self.builder_work()
        self.assertEqual(self.codes(), set())
        with connection.cursor() as cur:                              # adulteração direta no banco: o trabalho diz 1 de madeira, o estoque diz 2
            cur.execute("UPDATE companies_stockmovement SET delta = -2 WHERE reference_kind = %s AND delta = -1", ["construction_work"])
        report = {f["code"] for f in __import__("companies.audit", fromlist=["x"]).audit_companies().findings}
        self.assertIn("CONSTRUCTION_MATERIALS_MISMATCH", report)
        self.audit_companies_at_end = False

    def test_the_provisional_table_lists_the_switch_and_the_empty_table(self):
        rows = {r.parameter: r for r in params.provisional_table()}
        self.assertEqual(rows["construction.consumes_materials"].value, "False")
        self.assertEqual(rows["construction.materials_per_work"].value, "{}")
        self.assertEqual(rows["construction.commercial_3"].status, "GD")
