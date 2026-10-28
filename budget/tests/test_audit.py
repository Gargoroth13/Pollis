"""Auditoria do Orçamento: cada adulteração aparece como achado estruturado (09 §34)."""
from budget import plans, transfers
from budget.audit import audit_budget
from budget.constants import Level
from budget.models import BudgetPlan, BudgetPlanLine, GovernmentDecision
from ledger.models import Entry

from .base import BudgetBase


class AuditTests(BudgetBase):
    audit_at_end = False

    def setUp(self):
        super().setUp()
        self.fund(self.union(), 1_000_000)
        self.fund(self.st(), 100_000)
        self.earn(self.mun(), 100_000)
        self.t1 = transfers.transfer_budget(self.president.pk, self.to_state(1_000)).detail
        self.t2 = transfers.transfer_budget(self.governor.pk, self.to_city(2_000)).detail
        lines = {"education": 11_000, "health": 11_000, "infrastructure": 11_000}      # base de 30 dias = 102.000 → piso de 10.200
        assert plans.set_plan(self.mayor.pk, {"city": self.city_a.pk, "lines": lines}).ok
        res = plans.confirm_plan(self.mayor.pk, {"city": self.city_a.pk})
        assert res.ok, res
        self.plan = BudgetPlan.objects.get()
        self.pd = GovernmentDecision.objects.get(kind="plan_confirmed")

    def codes(self):
        return {f["code"] for f in audit_budget().findings}

    def test_clean_world_has_no_findings(self):
        self.assertEqual(audit_budget().findings, [])

    def test_transfer_decision_tampering(self):
        d = GovernmentDecision.objects.get(pk=self.t1["decision"])
        d.data = {**d.data, "amount": 999}
        d.save()
        self.assertIn("TRANSFER_ENTRY_AMOUNT_DIFFERS", self.codes())

    def test_transfer_decision_with_wrong_parties_or_actor(self):
        d = GovernmentDecision.objects.get(pk=self.t1["decision"])
        d.data = {**d.data, "to": {"level": "state", "id": self.state.pk + 1000}}
        d.save()
        self.assertIn("TRANSFER_BAD_PARTIES", self.codes())
        d.data = {**d.data, "to": self.gov(Level.MUNICIPALITY, self.city_a.pk)}
        d.save()
        self.assertIn("TRANSFER_LEVEL_NOT_ALLOWED", self.codes())

    def test_decision_actor_mismatch(self):
        GovernmentDecision.objects.filter(pk=self.t1["decision"]).update(actor_id=self.other.pk)
        self.assertIn("TRANSFER_ACTOR_DIFFERS", self.codes())

    def test_decision_without_ledger_entry(self):
        GovernmentDecision.objects.filter(pk=self.t1["decision"]).update(ledger_key="")
        self.assertIn("TRANSFER_WITHOUT_LEDGER_ENTRY", self.codes())
        self.assertIn("GOV_TRANSFER_WITHOUT_DECISION", self.codes())

    def test_gov_transfer_entry_without_any_decision(self):
        GovernmentDecision.objects.filter(pk=self.t1["decision"]).delete()
        self.assertIn("GOV_TRANSFER_WITHOUT_DECISION", self.codes())

    def test_gov_transfer_between_wrong_levels_is_flagged_even_with_a_decision(self):
        from ledger import services as ledger
        from ledger.constants import Nature
        res = ledger.transfer(self.mun().pk, self.union().pk, 10, Nature.GOV_TRANSFER, key="bad", reference_kind="test", reference_id="1", at=self.clk.now())
        self.assertTrue(res.ok, res)
        self.assertEqual({"GOV_TRANSFER_WITHOUT_DECISION", "GOV_TRANSFER_HIERARCHY"} - self.codes(), set())

    def test_plan_total_and_lines_tampering(self):
        BudgetPlan.objects.filter(pk=self.plan.pk).update(confirmed_total=1)
        self.assertIn("CONFIRMED_PLAN_TOTAL_DIFFERS", self.codes())
        BudgetPlan.objects.filter(pk=self.plan.pk).update(confirmed_total=33_000)
        BudgetPlanLine.objects.filter(plan=self.plan, area="education").update(amount_cents=1)
        c = self.codes()
        self.assertIn("CONFIRMED_PLAN_TOTAL_DIFFERS", c)
        self.assertIn("CONFIRMED_PLAN_DECISION_DIFFERS", c)
        self.assertIn("PLAN_FLOOR_NOT_MET", c)

    def test_plan_without_or_with_duplicate_decision(self):
        self.pd.delete()
        self.assertIn("CONFIRMED_PLAN_DECISION_COUNT", self.codes())

    def test_draft_plan_with_confirmation_data(self):
        BudgetPlan.objects.filter(pk=self.plan.pk).update(status="draft")
        c = self.codes()
        self.assertIn("DRAFT_PLAN_WITH_CONFIRMATION", c)
        self.assertIn("DRAFT_PLAN_WITH_DECISION", c)

    def test_plan_over_available_or_floors_over_100(self):
        BudgetPlan.objects.filter(pk=self.plan.pk).update(confirmation={**self.plan.confirmation, "available": 1, "floors_total_valid": False})
        c = self.codes()
        self.assertIn("PLAN_OVER_AVAILABLE", c)
        self.assertIn("PLAN_FLOORS_OVER_100", c)

    def test_non_municipal_area_in_a_plan(self):
        BudgetPlanLine.objects.create(plan=self.plan, area="military", amount_cents=1)
        self.assertIn("PLAN_NON_MUNICIPAL_AREA", self.codes())

    def test_management_command_exits_with_error_on_findings(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from io import StringIO
        call_command("audit_budget", stdout=StringIO())
        BudgetPlan.objects.filter(pk=self.plan.pk).update(confirmed_total=1)
        with self.assertRaises(CommandError):
            call_command("audit_budget", stdout=StringIO())
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("audit_budget", "--json", stdout=out)
        self.assertIn("CONFIRMED_PLAN_TOTAL_DIFFERS", out.getvalue())
