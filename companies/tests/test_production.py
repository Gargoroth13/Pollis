"""Produção empresarial (02 §5-8, §13, §18-20): um produto por vez, setup/cooldown, o Trabalho produz, insumos, estoque, qualidade."""
from decimal import Decimal
from unittest import mock

from catalog.constants import Sector
from companies import jobs, params, payroll, production, services, stock
from companies.audit import audit_companies
from companies.constants import CompanyType, StockOperation
from companies.models import Company, ProductionChange, ProductionLine, StockItem, StockMovement, WorkWage
from players import registry
from players.tests.base import T0
from skills.services import get_levels, get_skill_snapshot

from .test_wages import WageBase

D = Decimal


class ProductionBase(WageBase):
    """Siderúrgica (Industrial) produzindo Farinha (trigo → farinha), com 400 de trigo e um funcionário de produção."""

    def units(self, product, company=None):
        return stock.quantity_of(company or self.firm, product)

    def work_result(self, player=None):
        out = self.work(player)
        return out

    def hook(self, player=None):
        """Roda o Trabalho e devolve o resultado do hook de produção."""
        player = player or self.worker
        self.set_state(player, energy=D(100), nutrition=D(100), health=D(100), burnout=D(0), hospitalized_until=None,
                       health_critical=False)
        res = registry.execute_action(player.pk, "work", None)
        self.assertTrue(res.ok, res)
        return res.detail["hooks"][production.ACTION_HOOK]

    def set_stars(self, stars, company=None):
        Company.objects.filter(pk=company or self.firm).update(stars=stars)


class SelectionTests(ProductionBase):
    def test_the_first_choice_is_free_and_instant_and_leaves_a_record(self):
        fresh = self.found(self.boss, "industrial", "Moinho", 0)
        money = self.money(self.boss)
        res = production.set_production(self.boss.pk, fresh, "flour")
        self.assertEqual((res.ok, res.detail["initial"], res.detail["setup_until"], res.detail["cooldown_until"]),
                         (True, True, None, None))
        line = ProductionLine.objects.get(company_id=fresh)
        self.assertEqual((line.product.key, line.changes, line.carry), ("flour", 1, 0))
        self.assertEqual(self.money(self.boss), money)                           # sem custo nesta etapa
        change = ProductionChange.objects.get(company_id=fresh)
        self.assertEqual((change.sequence, change.from_product, change.to_product.key, change.cost), (1, None, "flour", 0))

    def test_only_the_owner_chooses_and_only_producing_types_may(self):
        self.assertRefused(production.set_production(self.worker.pk, self.firm, "flour"), "NOT_OWNER")
        self.assertRefused(production.set_production(self.boss.pk, 10 ** 9, "flour"), "COMPANY_NOT_FOUND")
        self.assertRefused(production.set_production(self.boss.pk, "x", "flour"), "INVALID_PARAMS")
        self.assertRefused(production.set_production(10 ** 9, self.firm, "flour"), "PLAYER_NOT_FOUND")
        for ctype in ("retail", "services", "construction", "financial"):
            company = self.found(self.third, ctype, f"Empresa {ctype}", 0)
            self.assertRefused(production.set_production(self.third.pk, company, "flour"), "COMPANY_TYPE_CANNOT_PRODUCE")

    def test_the_industrial_company_takes_manufactured_products_only_and_the_catalog_must_be_ready(self):
        self.assertRefused(production.set_production(self.boss.pk, self.firm, "wheat"), "PRODUCT_NOT_FOR_COMPANY_TYPE")
        self.assertRefused(production.set_production(self.boss.pk, self.firm, "nothing"), "UNKNOWN_PRODUCT")
        self.assertRefused(production.set_production(self.boss.pk, self.firm, 7), "INVALID_PARAMS")
        with mock.patch("companies.production.catalog.check_production_ready",
                        return_value=production.ActionResult(False, "UNSPECIFIED_DESIGN_VALUE", {"key": "sugar", "missing": ["yield_quantity"]})):
            res = production.set_production(self.boss.pk, self.firm, "sugar")
        self.assertRefused(res, "PRODUCTION_NOT_READY", reason="UNSPECIFIED_DESIGN_VALUE", missing=["yield_quantity"])

    def test_the_star_required_by_the_recipe_is_enforced_with_what_is_missing(self):
        self.assertTrue(production.set_production(self.boss.pk, self.firm, "cheese").ok)        # 1★: ok
        fresh = self.found(self.boss, "industrial", "Aciaria", 0)
        res = production.set_production(self.boss.pk, fresh, "steel")              # Aço exige 2★
        self.assertRefused(res, "STARS_TOO_LOW", required=2, stars=1)
        self.set_stars(2, fresh)
        self.assertTrue(production.set_production(self.boss.pk, fresh, "steel").ok)

    def test_a_matrix_needs_the_terrain_provider_and_respects_its_category(self):
        farm = self.found(self.boss, "matrix", "Fazenda", 0)
        self.assertRefused(production.set_production(self.boss.pk, farm, "wheat"), "MATRIX_SITE_UNDEFINED")     # P1.07 ainda não existe
        production.register_site_provider("test_site", lambda company_id: frozenset({Sector.AGRO}))
        self.addCleanup(production.unregister_site_provider, "test_site")
        self.assertRefused(production.set_production(self.boss.pk, farm, "iron"), "PRODUCT_OUTSIDE_TERRAIN_CATEGORY",
                           allowed=["agro"])
        self.assertRefused(production.set_production(self.boss.pk, farm, "flour"), "PRODUCT_NOT_FOR_COMPANY_TYPE")
        self.assertTrue(production.set_production(self.boss.pk, farm, "wheat").ok)

    def test_changing_product_costs_setup_and_cooldown_resets_the_fraction_and_keeps_a_history(self):
        ProductionLine.objects.filter(company_id=self.firm).update(carry=D("0.5"))
        res = production.set_production(self.boss.pk, self.firm, "cheese")
        self.assertEqual((res.ok, res.detail["initial"]), (True, False))
        line = ProductionLine.objects.get(company_id=self.firm)
        now = self.clk.now()
        self.assertEqual((line.setup_until, line.cooldown_until, line.carry, line.changes),
                         (now + params.SETUP_SECONDS, now + params.COOLDOWN_SECONDS, 0, 2))
        self.assertLess(params.SETUP_SECONDS, params.COOLDOWN_SECONDS)             # 02 §5.3: setup << cooldown
        self.assertRefused(production.set_production(self.boss.pk, self.firm, "cheese"), "ALREADY_PRODUCING")
        res = production.set_production(self.boss.pk, self.firm, "flour")
        self.assertRefused(res, "COOLDOWN_ACTIVE", until=now + params.COOLDOWN_SECONDS, remaining=params.COOLDOWN_SECONDS)
        self.clk.advance(seconds=params.COOLDOWN_SECONDS)
        self.assertTrue(production.set_production(self.boss.pk, self.firm, "flour").ok)
        self.assertEqual([(c.sequence, c.from_product.key if c.from_product else None, c.to_product.key)
                          for c in ProductionChange.objects.filter(company_id=self.firm)],
                         [(1, None, "flour"), (2, "flour", "cheese"), (3, "cheese", "flour")])

    def test_a_fixed_cost_above_zero_is_refused_until_the_design_defines_nature_and_destination(self):
        with mock.patch.object(params, "PRODUCTION_CHANGE_COST_CENTS", 100):
            self.assertRefused(production.set_production(self.boss.pk, self.firm, "cheese"), "PRODUCTION_CHANGE_COST_UNDEFINED")
            fresh = self.found(self.boss, "industrial", "Nova", 0)
            self.assertTrue(production.set_production(self.boss.pk, fresh, "flour").ok)        # a 1ª escolha não é troca
        self.assertEqual(ProductionLine.objects.get(company_id=self.firm).product.key, "flour")

    def test_the_owner_sees_what_each_product_would_need(self):
        rows = {r["product"]: r for r in production.producible_products(self.firm)}
        self.assertEqual((rows["cheese"]["available"], rows["cheese"]["code"]), (True, "OK"))
        self.assertEqual(rows["wheat"]["code"], "PRODUCT_NOT_FOR_COMPANY_TYPE")
        self.assertEqual((rows["steel"]["available"], rows["steel"]["code"], rows["steel"]["detail"]["required"]),
                         (False, "STARS_TOO_LOW", 2))
        retail = self.found(self.third, "retail", "Loja", 0)
        self.assertEqual(production.producible_products(retail), [])

    def test_the_action_goes_through_the_registry_with_the_same_refusals(self):
        target = {"company": self.firm, "product": "cheese"}
        check = registry.check_action(self.boss.pk, "set_production", target)
        self.assertEqual((check.available, check.code), (True, "OK"))
        bad = registry.check_action(self.worker.pk, "set_production", target)
        run = registry.execute_action(self.worker.pk, "set_production", target)
        self.assertEqual((bad.code, run.code, run.ok), ("NOT_OWNER", "NOT_OWNER", False))
        self.assertEqual(registry.execute_action(self.boss.pk, "set_production", {"company": 1}).code, "INVALID_PARAMS")
        self.assertTrue(registry.execute_action(self.boss.pk, "set_production", target).ok)


class WorkProducesTests(ProductionBase):
    def test_a_work_turns_inputs_into_stock_with_the_factors_explained(self):
        out = self.hook()
        self.assertEqual((out["produced"], out["consumed"], out["limited_by"], out["product"]), (1, {"wheat": 1}, [], "flour"))
        self.assertEqual((self.units("flour"), self.units("wheat")), (1, 399))
        steps = {s["key"] for s in out["per_work"].to_dict()["steps"]}
        self.assertEqual(steps, {"units_per_work_base", "skill_production", "specialization_production", "engineering_bonus", "catalog_yield"})
        kinds = list(StockMovement.objects.filter(company_id=self.firm).values_list("operation", flat=True))
        self.assertEqual(sorted(kinds[-2:]), ["input_consumption", "production"])
        moved = StockMovement.objects.get(operation="production")
        self.assertEqual((moved.actor, moved.reference_kind, moved.reference_id), (self.worker.pk, "work_production", f"{self.worker.pk}:1"))
        self.assertEqual(WorkWage.objects.get().sequence, 1)                # a mesma ação gerou salário e produção

    def test_the_fraction_is_carried_so_nothing_is_lost(self):
        self.set_skill(self.worker, "physical", 20)                          # fator 1 + 20 × 0,02 = 1,4 (e a especialização cresce)
        results = [self.hook() for _ in range(5)]
        total = sum(r["per_work"].value for r in results)
        produced = sum(r["produced"] for r in results)
        carry = ProductionLine.objects.get(company_id=self.firm).carry
        self.assertEqual(D(produced) + carry, total)                         # unidades + fração pendente = produção calculada
        self.assertTrue(0 <= carry < 1)
        self.assertGreater(produced, 5)                                       # skill e especialização aumentam a produção
        self.assertEqual(self.units("flour"), produced)

    def test_skill_and_specialization_raise_the_output_per_work(self):
        low = production.output_per_work("flour", D(0), D(0))
        high = production.output_per_work("flour", D(100), D(0))
        spec = production.output_per_work("flour", D(0), D(50))
        self.assertEqual((low.value, high.value, spec.value), (D(1), D(3), D("1.5")))
        self.assertEqual(production.skill_factor(D(1)).value, D("1.02"))      # 02 §7: skill 1, especialização 0 → ~1 unidade
        raw = production.output_per_work("wheat", D(0), D(0))
        self.assertEqual(raw.step("catalog_yield").amount, D(1))             # `raw_yield` da Matriz

    def test_the_balance_curve_of_skills_wins_over_the_provisional_one_when_it_is_defined(self):
        from django.test import override_settings
        from skills import curves
        curves.register_production_curve("test_double", lambda level: production.Calc("c", 2).result())
        self.addCleanup(curves.unregister_production_curve, "test_double")
        with override_settings(POLIS_SKILLS_BALANCE={"production_curve": "test_double"}):
            self.assertEqual(production.skill_factor(D(100)).value, D(2))
        self.assertEqual(production.skill_factor(D(100)).value, D(3))

    def test_working_in_the_product_builds_specialization_for_that_product(self):
        for _ in range(3):
            self.hook()
        spec = get_skill_snapshot(self.worker.pk).specializations
        self.assertEqual(spec["flour"].value, D(3))
        self.assertNotIn("cheese", spec)
        self.assertGreater(production.output_per_work("flour", D(0), spec["flour"].value).value, 1)

    def test_the_quality_of_the_stock_is_the_average_by_unit_of_who_worked_and_the_star_caps_it(self):
        other, _ = self.hire(self.third, company=self.firm, salary=2_000)
        self.set_skill(self.worker, "physical", 100)
        self.set_skill(self.third, "physical", 20)
        self.hook(self.worker)
        self.hook(self.third)
        item = StockItem.objects.get(company_id=self.firm, product__key="flour")
        units_w = StockMovement.objects.get(operation="production", actor=self.worker.pk).delta
        units_t = StockMovement.objects.get(operation="production", actor=self.third.pk).delta
        self.assertEqual(item.quantity, units_w + units_t)
        self.assertIsNotNone(item.quality)
        self.assertGreater(item.quality, D(20))
        self.assertLess(item.quality, D(101))
        company = Company.objects.get(pk=self.firm)
        eff = production.effective_quality(company, item.quality)
        self.assertEqual(eff.value, min(item.quality, D(100)))                 # 1★: teto 100
        self.set_stars(3)
        self.assertEqual(production.effective_quality(Company.objects.get(pk=self.firm), item.quality).value, item.quality)
        self.assertIsNone(production.effective_quality(company, None))         # qualidade desconhecida ≠ 0

    def test_non_production_positions_and_the_owner_do_not_produce_and_are_never_blocked(self):
        engineer, _ = self.hire(self.third, company=self.firm, salary=1_500, kind="engineer")
        self.audit_companies_at_end = False
        ProductionLine.objects.filter(company_id=self.firm).update(product=None, changes=0)    # empresa parada de propósito
        out = self.work(self.third)
        self.assertEqual(out["recognized"], 1_500)                              # recebe salário; sem produção, sem bloqueio
        self.assertEqual(StockMovement.objects.filter(operation="production").count(), 0)
        self.assertIsNone(self.work(self.boss))                                 # o Dono sem emprego: Trabalho livre, sem produção


class BlockedWorkTests(ProductionBase):
    def refusal(self):
        self.set_state(self.worker, energy=D(100))
        before = self.snap(self.worker).energy
        res = registry.execute_action(self.worker.pk, "work", None)
        check = registry.check_action(self.worker.pk, "work", None)
        self.assertEqual((res.ok, check.available), (False, False))
        self.assertEqual(res.code, check.code)
        self.assertEqual(self.snap(self.worker).energy, before)                 # recusa não gasta Energia
        return res.code

    def test_no_product_chosen_blocks_the_work_before_it_spends_energy_and_pays_nothing(self):
        self.audit_companies_at_end = False                                      # a empresa sem produto adulterada de propósito
        ProductionLine.objects.filter(company_id=self.firm).update(product=None, changes=0)
        self.assertEqual(self.refusal(), "COMPANY_NO_PRODUCT")
        self.assertEqual((WorkWage.objects.count(), StockMovement.objects.filter(operation="production").count()), (0, 0))

    def test_during_setup_nobody_works_and_after_it_everybody_can(self):
        self.assertRefused(production.set_production(self.boss.pk, self.firm, "flour"), "ALREADY_PRODUCING")
        self.assertTrue(production.set_production(self.boss.pk, self.firm, "cheese").ok)
        stock.credit_stock(self.firm, "milk", 50, origin="test", key="seed:milk", reference_kind="test", reference_id="1")
        self.assertEqual(self.refusal(), "COMPANY_IN_SETUP")
        self.clk.advance(seconds=params.SETUP_SECONDS)
        out = self.hook()
        self.assertEqual((out["product"], out["produced"]), ("cheese", 1))

    def test_missing_inputs_block_and_partial_inputs_reduce(self):
        self.assertTrue(stock.debit_stock(self.firm, "wheat", 400, destination="test", key="sale:w", reference_kind="test",
                                          reference_id="1").ok)
        self.assertEqual(self.refusal(), "MISSING_INPUTS")
        stock.credit_stock(self.firm, "wheat", 1, origin="test", key="seed:w1", reference_kind="test", reference_id="2")
        self.set_skill(self.worker, "physical", 100)                            # 3 unidades por trabalho
        out = self.hook()
        self.assertEqual((out["produced"], out["limited_by"], out["consumed"]), (1, ["MISSING_INPUTS"], {"wheat": 1}))
        self.assertEqual((self.units("wheat"), self.units("flour")), (0, 1))
        self.assertTrue(0 <= ProductionLine.objects.get(company_id=self.firm).carry < 1)

    def test_a_full_stock_blocks_and_a_nearly_full_one_reduces(self):
        capacity = int(stock.capacity_of(1).value)
        stock.credit_stock(self.firm, "flour", capacity - 400 - 1, origin="test", key="seed:fl", reference_kind="test", reference_id="3")
        self.set_skill(self.worker, "physical", 100)
        out = self.hook()                                                        # só cabe 1 unidade
        self.assertEqual((out["produced"], out["limited_by"]), (1, ["STOCK_FULL"]))
        self.assertEqual(stock.used_of(self.firm), capacity - 1)             # trigo consumido libera 1 unidade
        missing = capacity - stock.used_of(self.firm)
        self.assertTrue(stock.credit_stock(self.firm, "flour", missing, origin="test", key="seed:fill", reference_kind="test",
                                           reference_id="4").ok)
        self.assertEqual(stock.used_of(self.firm), capacity)
        self.assertEqual(self.refusal(), "STOCK_FULL")

    def test_the_block_does_not_apply_to_players_without_a_production_job(self):
        self.assertIsNone(self.work(self.third))
        self.assertTrue(registry.check_action(self.third.pk, "work", None).available)


class MatrixProductionTests(ProductionBase):
    def test_a_matrix_produces_raw_material_without_inputs(self):
        production.register_site_provider("test_site", lambda company_id: frozenset({Sector.AGRO}))
        self.addCleanup(production.unregister_site_provider, "test_site")
        farm = self.found(self.third, "matrix", "Fazenda", 0)
        self.assertTrue(production.set_production(self.third.pk, farm, "wheat").ok)
        self.boss = self.third
        miner = self.new_player("p4")
        self.fund(miner, 1_000)
        position = self.open("worker", 1_000, company=farm, player=self.third)
        a = self.apply(miner, position)
        self.assertTrue(jobs.approve_application(self.third.pk, a).ok)
        out = self.hook(miner)
        self.assertEqual((out["produced"], out["consumed"], out["limited_by"]), (1, {}, []))
        self.assertEqual(stock.quantity_of(farm, "wheat"), 1)


class StockServiceTests(ProductionBase):
    def credit(self, quantity=10, key="k1", product="milk", **kw):
        return stock.credit_stock(self.firm, product, quantity, origin="test", key=key, reference_kind="test", reference_id=key, **kw)

    def test_external_systems_may_only_buy_in_and_sell_out(self):
        self.assertTrue(self.credit().ok)
        for op in (StockOperation.PRODUCTION, StockOperation.INPUT_CONSUMPTION, StockOperation.SALE):
            self.assertRefused(stock.credit_stock(self.firm, "milk", 1, operation=op, origin="x", key=f"c-{op.value}",
                                                  reference_kind="t", reference_id="1"), "OPERATION_NOT_ALLOWED")
        for op in (StockOperation.PRODUCTION, StockOperation.PURCHASE, StockOperation.INPUT_CONSUMPTION):
            self.assertRefused(stock.debit_stock(self.firm, "milk", 1, operation=op, destination="x", key=f"d-{op.value}",
                                                 reference_kind="t", reference_id="1"), "OPERATION_NOT_ALLOWED")
        self.assertTrue(stock.debit_stock(self.firm, "milk", 4, destination="sale:1", key="d1", reference_kind="t", reference_id="1").ok)
        self.assertEqual(self.units("milk"), 6)

    def test_refusals_leave_no_trace(self):
        before = StockMovement.objects.count()
        self.assertRefused(self.credit(0), "INVALID_QUANTITY")
        self.assertRefused(self.credit(True), "INVALID_QUANTITY")
        self.assertRefused(self.credit(10 ** 13), "INVALID_QUANTITY")
        self.assertRefused(self.credit(product="nothing"), "UNKNOWN_PRODUCT")
        self.assertRefused(stock.credit_stock(10 ** 9, "milk", 1, origin="t", key="x", reference_kind="t", reference_id="1"), "COMPANY_NOT_FOUND")
        self.assertRefused(stock.credit_stock(self.firm, "milk", 1, origin="", key="x", reference_kind="t", reference_id="1"), "INVALID_PARAMS")
        self.assertRefused(self.credit(quality=-1), "INVALID_QUALITY")
        self.assertRefused(stock.debit_stock(self.firm, "milk", 5, destination="x", key="x", reference_kind="t", reference_id="1"),
                           "INSUFFICIENT_STOCK", have=0, required=5)
        self.assertRefused(self.credit(10 ** 6), "STOCK_FULL")
        self.assertEqual(StockMovement.objects.count(), before)

    def test_the_same_key_is_applied_once_and_a_different_content_is_a_conflict(self):
        first = self.credit(10, key="same")
        again = self.credit(10, key="same")
        self.assertEqual((first.ok, again.ok, again.detail.get("already_applied")), (True, True, True))
        self.assertEqual(self.units("milk"), 10)
        self.assertRefused(self.credit(11, key="same"), "IDEMPOTENCY_CONFLICT")

    def test_quality_is_the_unit_average_and_unknown_stays_unknown_never_zero(self):
        self.credit(10, key="a", quality=D(10))
        self.credit(30, key="b", quality=D(50))
        self.assertEqual(StockItem.objects.get(product__key="milk").quality, D("40"))
        stock.debit_stock(self.firm, "milk", 5, destination="s", key="d", reference_kind="t", reference_id="1")
        self.assertEqual(StockItem.objects.get(product__key="milk").quality, D("40"))      # sair não muda a média
        self.credit(5, key="c")                                                           # qualidade desconhecida
        self.assertIsNone(StockItem.objects.get(product__key="milk").quality)
        stock.debit_stock(self.firm, "milk", 40, destination="s", key="d2", reference_kind="t", reference_id="2")
        self.assertFalse(StockItem.objects.filter(product__key="milk").exists())            # zerou: o item some, a trilha fica
        self.assertEqual(StockMovement.objects.filter(product__key="milk").count(), 5)

    def test_the_capacity_follows_the_star_and_a_full_stock_refuses_the_whole_entry(self):
        self.assertEqual(stock.capacity_of(1).value, 500)
        self.assertEqual([int(stock.capacity_of(n).value) for n in (1, 2, 3, 4, 5)], [500, 1000, 1500, 2000, 2500])
        room = 500 - stock.used_of(self.firm)
        self.assertRefused(self.credit(room + 1), "STOCK_FULL", used=400, adding=room + 1, capacity=500)
        self.assertTrue(self.credit(room).ok)
        self.set_stars(2)
        self.assertTrue(self.credit(10, key="more").ok)

    def test_the_trail_is_immutable(self):
        from companies.models import CompaniesImmutableError
        self.credit()
        movement = StockMovement.objects.first()
        movement.delta = 99
        with self.assertRaises(CompaniesImmutableError):
            movement.save()
        with self.assertRaises(CompaniesImmutableError):
            movement.delete()


class ProductionAuditTests(ProductionBase):
    audit_companies_at_end = False

    def codes(self):
        return {f["code"] for f in audit_companies().findings}

    def test_a_clean_production_world_passes(self):
        for _ in range(3):
            self.hook()
        report = audit_companies()
        self.assertTrue(report.ok, report.findings)

    def test_the_audit_flags_tampered_stock_and_unpaid_or_unregistered_production(self):
        self.hook()
        StockItem.objects.filter(product__key="flour").update(quantity=99)
        self.assertIn("STOCK_ITEM_MISMATCH", self.codes())
        StockItem.objects.filter(product__key="flour").update(quantity=1)
        self.assertTrue(audit_companies().ok)
        StockItem.objects.filter(product__key="flour").update(quality=D("77"))
        self.assertIn("STOCK_QUALITY_MISMATCH", self.codes())
        StockItem.objects.filter(product__key="flour").update(quality=None)
        movement = StockMovement.objects.get(operation="production")
        explained = dict(movement.explained)
        explained["consumed"] = {"wheat": 5}
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("UPDATE companies_stockmovement SET explained = %s WHERE id = %s",
                           [__import__("json").dumps(explained), movement.pk])
        self.assertIn("INPUT_CONSUMPTION_MISMATCH", self.codes())

    def test_the_audit_flags_a_history_that_disagrees_with_the_line_and_a_broken_cooldown(self):
        ProductionLine.objects.filter(company_id=self.firm).update(changes=5)
        self.assertIn("PRODUCTION_HISTORY_MISMATCH", self.codes())
        ProductionLine.objects.filter(company_id=self.firm).update(changes=1)
        self.assertTrue(production.set_production(self.boss.pk, self.firm, "cheese").ok)       # 1ª troca (a escolha inicial não tem espera)
        second = ProductionChange.objects.get(company_id=self.firm, sequence=2)
        self.assertEqual(second.cooldown_until, second.at + params.COOLDOWN_SECONDS)
        self.clk.advance(seconds=params.COOLDOWN_SECONDS)
        self.assertTrue(production.set_production(self.boss.pk, self.firm, "flour").ok)
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("UPDATE companies_productionchange SET at = %s WHERE sequence = 3", [second.cooldown_until - 1])
        self.assertIn("COOLDOWN_VIOLATED", self.codes())
