"""Plano orçamentário municipal e pisos (09 §5, §27; 11 §11.2.1): rascunho, confirmação com Explained, pisos sobre a base de 30 dias, dotação por área."""
from decimal import Decimal as D
from unittest import mock

from budget import params, periods, plans
from budget.audit import audit_budget
from budget.constants import Area, Level
from budget.models import BudgetPlan, BudgetPlanLine, GovernmentDecision
from players import registry

from .base import BudgetBase


class PlanBase(BudgetBase):
    def setUp(self):
        super().setUp()
        self.earn(self.mun(), 100_000)              # receita dos últimos 30 dias = base dos pisos
        self.base = 100_000

    def set(self, lines, player=None, **extra):
        return plans.set_plan((player or self.mayor).pk, {"city": self.city_a.pk, "lines": lines, **extra})

    def confirm(self, player=None, **extra):
        return plans.confirm_plan((player or self.mayor).pk, {"city": self.city_a.pk, **extra})

    def good(self, **over):
        lines = {"education": 10_000, "health": 10_000, "infrastructure": 10_000, "administration": 20_000, "social_programs": 5_000}
        lines.update(over)
        return lines


class SetPlanTests(PlanBase):
    def test_the_mayor_drafts_a_plan_and_can_redo_it(self):
        r1 = self.set(self.good())
        self.assertTrue(r1.ok, r1)
        self.assertEqual((r1.detail["status"], r1.detail["total"], r1.detail["period"]), ("draft", 55_000, periods.period_of(self.day_of_now())))
        r2 = self.set({"education": 7})
        self.assertTrue(r2.ok)
        self.assertEqual(BudgetPlan.objects.count(), 1)
        self.assertEqual({l.area: l.amount_cents for l in BudgetPlanLine.objects.all()}, {"education": 7})          # área omitida = linha inexistente

    def test_only_the_mayor_of_that_city_acts(self):
        self.assertEqual(self.set(self.good(), self.other).code, "NOT_OFFICE_HOLDER")
        self.assertEqual(self.set(self.good(), self.governor).code, "NOT_OFFICE_HOLDER")
        self.assertEqual(plans.set_plan(self.mayor.pk, {"city": self.city_b.pk, "lines": {}}).code, "NO_OFFICE_HOLDER")
        self.assertEqual(BudgetPlan.objects.count(), 0)

    def test_invalid_input(self):
        cases = [(None, "INVALID_PARAMS"), ({"city": self.city_a.pk}, "INVALID_PARAMS"), ({"city": self.city_a.pk, "lines": {}, "x": 1}, "INVALID_PARAMS"),
                 ({"city": 10 ** 9, "lines": {}}, "GOVERNMENT_NOT_FOUND"), ({"city": True, "lines": {}}, "GOVERNMENT_NOT_FOUND"),
                 ({"city": self.city_a.pk, "lines": []}, "INVALID_LINES"), ({"city": self.city_a.pk, "lines": {"x": 1}}, "INVALID_AREA"),
                 ({"city": self.city_a.pk, "lines": {"military": 1}}, "AREA_NOT_MUNICIPAL"),
                 ({"city": self.city_a.pk, "lines": {"health": -1}}, "INVALID_AMOUNT"), ({"city": self.city_a.pk, "lines": {"health": 1.5}}, "INVALID_AMOUNT"),
                 ({"city": self.city_a.pk, "lines": {"health": True}}, "INVALID_AMOUNT"),
                 ({"city": self.city_a.pk, "lines": {}, "period": "a"}, "INVALID_PERIOD")]
        for target, code in cases:
            res = plans.set_plan(self.mayor.pk, target)
            self.assertEqual((res.ok, res.code), (False, code), target)
        self.assertEqual(plans.set_plan("x", {"city": self.city_a.pk, "lines": {}}).code, "PLAYER_NOT_FOUND")
        self.assertEqual(BudgetPlan.objects.count(), 0)

    def test_a_past_period_is_refused_and_a_future_one_is_allowed(self):
        cur = periods.period_of(self.day_of_now())
        self.assertEqual(self.set(self.good(), period=cur - 1).code, "PERIOD_ENDED")
        self.assertTrue(self.set(self.good(), period=cur + 1).ok)

    def test_a_confirmed_plan_does_not_change(self):
        self.set(self.good())
        self.assertTrue(self.confirm().ok)
        self.assertEqual(self.set({"education": 1}).code, "PLAN_CONFIRMED")
        self.assertEqual(BudgetPlanLine.objects.get(area="education").amount_cents, 10_000)


class ConfirmTests(PlanBase):
    def test_confirmation_records_the_decision_with_the_floors_breakdown(self):
        self.set(self.good())
        res = self.confirm()
        self.assertTrue(res.ok, res)
        chk = res.detail["check"]
        self.assertEqual((chk["base_revenue_30_days"], chk["planned_total"], chk["available"], chk["reserve"]), (100_000, 55_000, 100_000, 45_000))
        self.assertEqual([(f["area"], f["required"], f["planned"], f["ok"]) for f in chk["floors"]],
                         [("education", 10_000, 10_000, True), ("health", 10_000, 10_000, True), ("infrastructure", 10_000, 10_000, True)])
        d = GovernmentDecision.objects.get(pk=res.detail["decision"])
        self.assertEqual((d.kind, d.level, d.territory_id, d.actor_id), ("plan_confirmed", "municipality", self.city_a.pk, self.mayor.pk))
        plan = BudgetPlan.objects.get()
        self.assertEqual((plan.status, plan.confirmed_total, plan.confirmed_by_id, plan.confirmed_at), ("confirmed", 55_000, self.mayor.pk, self.clk.now()))

    def test_each_floor_is_checked_one_centavo_below_fails_exactly_at_the_floor_passes(self):
        for area in ("education", "health", "infrastructure"):
            BudgetPlan.objects.all().delete()
            self.set(self.good(**{area: 9_999}))
            res = self.confirm()
            self.assertEqual(res.code, "FLOOR_NOT_MET", area)
            short = [f for f in res.detail["floors"] if not f["ok"]]
            self.assertEqual([(f["area"], f["shortfall"]) for f in short], [(area, 1)])
            self.assertEqual(BudgetPlan.objects.get().status, "draft")
            self.assertEqual(GovernmentDecision.objects.count(), 0)
        BudgetPlan.objects.all().delete()
        self.set(self.good())
        self.assertTrue(self.confirm().ok)

    def test_the_floor_is_rounded_up_never_down(self):
        self.earn(self.mun(), 1)                                   # base 100.001 → 10% = 10.000,1 → exige 10.001
        self.set(self.good())
        res = self.confirm()
        self.assertEqual(res.code, "FLOOR_NOT_MET")
        self.assertEqual({f["required"] for f in res.detail["floors"]}, {10_001})

    def test_a_missing_area_counts_as_zero_for_the_floor(self):
        self.set({"health": 10_000, "infrastructure": 10_000})
        res = self.confirm()
        self.assertEqual((res.code, [f["area"] for f in res.detail["floors"] if not f["ok"]]), ("FLOOR_NOT_MET", ["education"]))

    def test_the_floor_base_is_the_last_30_days_of_revenue_only(self):
        self.go_days(31)                                           # a receita de 100.000 saiu da janela de 30 dias
        self.set(self.good(education=0, health=0, infrastructure=0))
        res = self.confirm()
        self.assertTrue(res.ok, res)                               # sem receita nos últimos 30 dias, o piso exigido é 0
        self.assertEqual((res.detail["check"]["base_revenue_30_days"], {f["required"] for f in res.detail["check"]["floors"]}), (0, {0}))

    def test_the_floor_base_ignores_scenario_grants_and_counts_received_transfers(self):
        self.fund(self.mun(), 500_000)                             # dotação do cenário NÃO é receita
        self.set(self.good())
        self.assertEqual(self.confirm().detail["check"]["base_revenue_30_days"], 100_000)

    def test_the_plan_cannot_exceed_what_the_city_has_available(self):
        self.set(self.good(administration=100_000))
        res = self.confirm()
        self.assertEqual(res.code, "PLAN_EXCEEDS_AVAILABLE")
        self.assertEqual((res.detail["planned_total"], res.detail["available"]), (135_000, 100_000))

    def test_the_boundary_total_equal_to_available_is_allowed(self):
        self.set(self.good(administration=100_000 - 10_000 * 3 - 5_000))
        res = self.confirm()
        self.assertTrue(res.ok, res)
        self.assertEqual(res.detail["check"]["reserve"], 0)

    def test_committed_money_is_not_available_for_the_plan(self):
        from ledger import services as ledger
        self.assertTrue(ledger.hold(self.mun().pk, 50_000, key="h", reference_kind="test", reference_id="1", at=self.clk.now()).ok)
        self.set(self.good())
        res = self.confirm()
        self.assertEqual((res.code, res.detail["available"]), ("PLAN_EXCEEDS_AVAILABLE", 50_000))

    def test_floors_summing_over_100_percent_are_refused(self):
        with mock.patch.dict("budget.params.FLOOR_PCT", {Area.EDUCATION: D("40"), Area.HEALTH: D("40"), Area.INFRASTRUCTURE: D("30")}):
            self.set(self.good(education=40_000, health=40_000, infrastructure=30_000))
            res = self.confirm()
        self.assertEqual((res.code, res.detail["floors_total_pct"]), ("FLOORS_EXCEED_100_PERCENT", "110"))

    def test_confirm_requires_a_plan_and_the_mayor_and_is_not_repeatable(self):
        self.assertEqual(self.confirm().code, "PLAN_NOT_FOUND")
        self.set(self.good())
        self.assertEqual(self.confirm(self.other).code, "NOT_OFFICE_HOLDER")
        self.assertTrue(self.confirm().ok)
        self.assertEqual(self.confirm().code, "PLAN_CONFIRMED")
        self.assertEqual(GovernmentDecision.objects.count(), 1)

    def test_invalid_confirm_input(self):
        for target, code in ((None, "INVALID_PARAMS"), ({}, "INVALID_PARAMS"), ({"city": self.city_a.pk, "x": 1}, "INVALID_PARAMS"),
                             ({"city": 10 ** 9}, "GOVERNMENT_NOT_FOUND"), ({"city": self.city_a.pk, "period": 1.5}, "INVALID_PERIOD")):
            self.assertEqual(plans.confirm_plan(self.mayor.pk, target).code, code, target)

    def test_floors_exist_only_for_municipal_plans_and_military_is_not_a_municipal_area(self):
        from budget.constants import FLOOR_AREAS, MUNICIPAL_AREAS
        self.assertEqual(plans.set_plan(self.governor.pk, {"city": self.city_a.pk, "lines": {}}).code, "NOT_OFFICE_HOLDER")
        self.assertNotIn(Area.MILITARY, MUNICIPAL_AREAS)
        self.assertEqual(set(FLOOR_AREAS), {Area.EDUCATION, Area.HEALTH, Area.INFRASTRUCTURE})

    def test_the_audit_accepts_confirmed_plans(self):
        self.set(self.good())
        self.confirm()
        r = audit_budget()
        self.assertTrue(r.ok, r.findings)
        self.assertEqual(r.stats["plans"], 1)


class HeadroomTests(PlanBase):
    def test_no_confirmed_plan_means_unknown_not_zero(self):
        self.assertIsNone(plans.area_headroom(self.city_a.pk, Area.HEALTH, self.clk.now()))
        self.set(self.good())
        self.assertIsNone(plans.area_headroom(self.city_a.pk, Area.HEALTH, self.clk.now()))      # rascunho não vale

    def test_headroom_is_the_line_minus_the_categorized_spending_of_the_period(self):
        self.set(self.good())
        self.confirm()
        self.spend(self.mun(), 4_000, category="health")
        self.spend(self.mun(), 500, category="health")
        self.spend(self.mun(), 1_000, category="education")
        self.assertEqual(plans.area_headroom(self.city_a.pk, Area.HEALTH, self.clk.now()), 5_500)
        self.assertEqual(plans.area_headroom(self.city_a.pk, Area.EDUCATION, self.clk.now()), 9_000)
        v = plans.plan_view(self.city_a.pk, None, self.clk.now())
        self.assertEqual((v["spent_by_area"]["health"], v["headroom_by_area"]["administration"], v["status"]), (4_500, 20_000, "confirmed"))

    def test_an_area_without_a_line_has_zero_headroom(self):
        self.set(self.good())
        self.confirm()
        self.assertEqual(plans.area_headroom(self.city_a.pk, Area.MILITARY, self.clk.now()), 0)

    def test_the_view_is_public_and_none_without_a_plan(self):
        self.assertIsNone(plans.plan_view(self.city_b.pk, None, self.clk.now()))
        self.set(self.good())
        v = plans.plan_view(self.city_a.pk, None, self.clk.now())
        self.assertEqual((v["status"], v["total"], v["confirmation"]), ("draft", 55_000, None))


class PlanActionTests(PlanBase):
    def test_availability_matches_execution(self):
        t = {"city": self.city_a.pk, "lines": self.good()}
        for player in (self.mayor, self.other):
            a = registry.check_action(player.pk, "set_budget_plan", t)
            self.assertEqual(a.available, player is self.mayor, a)
        self.assertEqual(registry.check_action(self.mayor.pk, "confirm_budget_plan", {"city": self.city_a.pk}).code, "PLAN_NOT_FOUND")
        self.assertTrue(registry.execute_action(self.mayor.pk, "set_budget_plan", t).ok)
        self.assertEqual(registry.check_action(self.mayor.pk, "confirm_budget_plan", {"city": self.city_a.pk}).code, "OK")
        self.assertTrue(registry.execute_action(self.mayor.pk, "confirm_budget_plan", {"city": self.city_a.pk}).ok)
        self.assertEqual(registry.check_action(self.mayor.pk, "set_budget_plan", t).code, "PLAN_CONFIRMED")

    def test_the_preview_shows_the_plan(self):
        self.set(self.good())
        pv = registry.check_action(self.mayor.pk, "confirm_budget_plan", {"city": self.city_a.pk}).preview
        self.assertEqual(pv["plan"]["total"], 55_000)
