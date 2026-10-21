"""Varejo (02 §11) e permissões de compra (02 §4): estoque ≠ capacidade de venda; só compra o que tem uso válido."""
from decimal import Decimal

from companies import params, retail, services, stock, support, trade
from companies.audit import audit_companies
from companies.models import SalesCapacityUse, StockMovement, SupportWork
from players import registry

from .test_production import ProductionBase

D = Decimal


class RetailBase(ProductionBase):
    def setUp(self):
        super().setUp()
        self.shop = self.found(self.boss, "retail", "Padaria Central", 0)
        self.seller = self.third
        self.assertTrue(services.fund_company(self.boss.pk, self.shop, 100_000).ok)
        self.hire(self.seller, company=self.shop, salary=1_000, kind="salesperson")
        self.assertTrue(stock.credit_stock(self.shop, "bread", 300, origin="test", key="seed:bread", reference_kind="test",
                                           reference_id="1").ok)

    def codes(self):
        return {f["code"] for f in audit_companies().findings}

    def sell(self, quantity, key, product="bread"):
        return retail.fulfill_sale(self.shop, product, quantity, destination="player:99", key=key, reference_kind="test", reference_id=key)


class PurchasePermissionTests(RetailBase):
    def test_a_producer_buys_only_inputs_of_recipes_it_can_produce(self):
        self.assertIsNone(trade.purchase_refusal(self.firm, "wheat"))                       # insumo da Farinha (1★)
        self.assertIsNone(trade.purchase_refusal(self.firm, "milk"))                        # insumo do Queijo
        res = trade.purchase_refusal(self.firm, "hamburger")
        self.assertEqual(res.code, "NO_VALID_USE")                                          # bem final: não é insumo de receita nenhuma
        self.set_stars(5)
        self.assertEqual(trade.purchase_refusal(self.firm, "flour") is None, True)          # insumo do Pão

    def test_the_star_matters_because_the_recipe_must_be_available_to_that_company(self):
        # Hambúrguer (4★) usa pão, queijo e carne processada: a empresa 1★ não pode produzi-lo, mas pão é insumo de outra receita? Só dele.
        self.assertEqual(trade.purchase_refusal(self.firm, "processed_meat").code, "NO_VALID_USE")
        self.set_stars(4)
        self.assertIsNone(trade.purchase_refusal(self.firm, "processed_meat"))

    def test_retail_buys_only_what_it_resells_and_other_types_have_no_valid_use_yet(self):
        self.assertIsNone(trade.purchase_refusal(self.shop, "bread"))
        self.assertEqual(trade.purchase_refusal(self.shop, "wheat").code, "NO_VALID_USE")
        for ctype in ("services", "construction", "financial"):
            company = self.found(self.boss, ctype, f"X {ctype}", 0)
            self.assertEqual(trade.purchase_refusal(company, "bread").code, "NO_VALID_USE")

    def test_unknown_and_non_tradable_products_and_companies_are_refused(self):
        self.assertEqual(trade.purchase_refusal(self.firm, "nothing").code, "UNKNOWN_PRODUCT")
        self.assertEqual(trade.purchase_refusal(10 ** 9, "wheat").code, "COMPANY_NOT_FOUND")
        self.assertEqual(trade.purchase_refusal("x", "wheat").code, "COMPANY_NOT_FOUND")
        self.assertEqual(trade.purchase_refusal(self.firm, "military_weapons").code, "PRODUCT_NOT_TRADABLE_BETWEEN_COMPANIES")

    def test_credit_stock_enforces_the_permission_and_changes_nothing_when_refused(self):
        before = StockMovement.objects.count()
        res = stock.credit_stock(self.firm, "hamburger", 5, origin="test", key="x:1", reference_kind="test", reference_id="1")
        self.assertEqual((res.ok, res.code), (False, "NO_VALID_USE"))
        self.assertEqual(StockMovement.objects.count(), before)
        self.assertEqual(stock.quantity_of(self.firm, "hamburger"), 0)


class CapacityTests(RetailBase):
    def work_seller(self, times=1):
        for _ in range(times):
            self.work(self.seller)

    def test_a_salesperson_work_adds_daily_capacity_and_is_paid_like_any_work(self):
        out = self.work(self.seller)
        self.assertEqual(out["paid"], 1_000)
        status = retail.capacity_status(self.shop, self.clk.now())
        self.assertEqual((status["whole"], status["used"], status["available"]), (10, 0, 10))      # 10 × skill(0) × especialização(0)
        w = SupportWork.objects.get(player=self.seller)
        self.assertEqual((w.kind, w.contribution), ("salesperson", D(10)))
        self.assertEqual(support.specialization_key_of("salesperson", self.shop, 0), params.SALES_SPECIALIZATION_KEY)
        self.assertEqual(self.codes(), set())

    def test_charisma_raises_the_capacity(self):
        self.set_skill(self.seller, "charisma", 100)
        self.work_seller()
        self.assertEqual(retail.capacity_status(self.shop, self.clk.now())["whole"], 30)

    def test_a_sale_consumes_one_stock_and_one_capacity_each_and_stock_is_independent(self):
        self.work_seller()
        res = self.sell(4, "s1")
        self.assertTrue(res.ok, res)
        self.assertEqual((res.detail["stock_after"], res.detail["capacity_after"]), (296, 6))
        self.assertEqual(stock.quantity_of(self.shop, "bread"), 296)
        movement = StockMovement.objects.get(key="s1")
        self.assertEqual((movement.operation, movement.delta, movement.destination), ("sale", -4, "player:99"))
        self.assertEqual(SalesCapacityUse.objects.get(key="s1").quantity, 4)
        self.assertEqual(self.codes(), set())

    def test_sales_cannot_exceed_the_capacity_even_with_plenty_of_stock(self):
        self.work_seller()
        res = self.sell(11, "s2")
        self.assertEqual((res.ok, res.code, res.detail["available"]), (False, "SALES_CAPACITY_EXCEEDED", 10))
        self.assertIn("sales_capacity_produced_today", {s["key"] for s in res.detail["explained"]["steps"]})
        self.assertEqual(stock.quantity_of(self.shop, "bread"), 300)                        # nada mudou
        self.assertTrue(self.sell(10, "s3").ok)
        self.assertEqual(self.sell(1, "s4").code, "SALES_CAPACITY_EXCEEDED")

    def test_sales_cannot_exceed_the_stock_even_with_plenty_of_capacity(self):
        self.set_skill(self.seller, "charisma", 100)
        self.work_seller(4)                                                                  # ~120+ de capacidade
        stock.debit_stock(self.shop, "bread", 295, destination="test", key="drain", reference_kind="test", reference_id="1")
        res = self.sell(6, "s5")
        self.assertEqual((res.ok, res.code), (False, "INSUFFICIENT_STOCK"))
        self.assertEqual(SalesCapacityUse.objects.filter(key="s5").count(), 0)             # a capacidade não foi gasta

    def test_capacity_resets_every_day_and_unused_capacity_is_lost(self):
        self.work_seller()
        self.clk.advance(days=1)
        self.assertEqual(retail.capacity_status(self.shop, self.clk.now())["available"], 0)
        self.assertEqual(self.sell(1, "late").code, "SALES_CAPACITY_EXCEEDED")
        self.work_seller()
        self.assertTrue(self.sell(10, "new").ok)

    def test_sale_is_idempotent_by_key_and_a_changed_request_conflicts(self):
        self.work_seller()
        self.assertTrue(self.sell(3, "k1").ok)
        again = self.sell(3, "k1")
        self.assertEqual((again.ok, again.detail.get("already_applied")), (True, True))
        self.assertEqual(stock.quantity_of(self.shop, "bread"), 297)
        self.assertEqual(self.sell(4, "k1").code, "IDEMPOTENCY_CONFLICT")

    def test_only_retail_sells_to_players_and_only_declared_retail_products(self):
        res = retail.fulfill_sale(self.firm, "flour", 1, destination="p", key="z1", reference_kind="t", reference_id="1")
        self.assertEqual(res.code, "COMPANY_TYPE_CANNOT_SELL_TO_PLAYERS")
        self.assertEqual(self.sell(1, "z2", product="wheat").code, "PRODUCT_NOT_SOLD_AT_RETAIL")
        self.assertEqual(self.sell(1, "z3", product="nothing").code, "UNKNOWN_PRODUCT")
        for bad in (0, -1, 1.5, True, "1", None):
            self.assertEqual(self.sell(bad, "z4").code, "INVALID_QUANTITY")
        self.assertEqual(retail.fulfill_sale(10 ** 9, "bread", 1, destination="p", key="z5", reference_kind="t",
                                             reference_id="1").code, "COMPANY_NOT_FOUND")
        self.assertEqual(retail.fulfill_sale(self.shop, "bread", 1, destination="", key="z6", reference_kind="t",
                                             reference_id="1").code, "INVALID_PARAMS")

    def test_the_other_salesperson_of_another_shop_does_not_add_capacity_here(self):
        other = self.found(self.boss, "retail", "Outra", 0)
        self.assertEqual(retail.capacity_status(other, self.clk.now())["available"], 0)
        self.work_seller()
        self.assertEqual(retail.capacity_status(other, self.clk.now())["available"], 0)

    def test_the_audit_flags_a_sale_without_its_stock_movement_and_over_capacity(self):
        self.work_seller()
        self.assertTrue(self.sell(5, "a1").ok)
        self.assertEqual(self.codes(), set())
        self.audit_companies_at_end = False
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("UPDATE companies_salescapacityuse SET quantity = 50")
        self.assertIn("SALE_WITHOUT_STOCK_MOVEMENT", self.codes())
        self.assertIn("SALES_CAPACITY_EXCEEDED", self.codes())
