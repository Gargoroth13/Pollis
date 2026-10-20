"""Ações no Action Registry (mesmo caminho de jogadores e Bots) e auditoria das Empresas."""
from companies import params, services
from companies.audit import audit_companies
from companies.constants import CompanyType, PositionKind
from companies.models import Company, Position
from ledger.models import Entry
from players import registry

from .base import CompanyTestCase

FOUND = {"type": "retail", "name": "Loja", "owner_salary_cents": 500}


class RegistryTests(CompanyTestCase):
    def test_the_actions_are_registered_with_stable_descriptors(self):
        ids = {d.id: d for d in registry.list_descriptors()}
        self.assertEqual((ids["found_company"].name, ids["found_company"].target),
                         ("Fundar empresa", registry.TargetSpec(registry.TARGET_PARAMS, True)))
        self.assertEqual(ids["fund_company"].name, "Aportar capital na empresa")

    def test_found_and_fund_through_the_registry(self):
        res = registry.execute_action(self.player.pk, "found_company", dict(FOUND))
        self.assertTrue(res.ok, res)
        company = res.detail["company"]
        self.assertTrue(registry.execute_action(self.player.pk, "fund_company", {"company": company, "amount_cents": 100}).ok)
        self.assertEqual(Position.objects.get(company_id=company).salary, 500)

    def test_check_and_preview_use_the_same_refusals_and_explain_the_cost(self):
        ok = registry.check_action(self.player.pk, "found_company", dict(FOUND))
        self.assertEqual((ok.available, ok.code, ok.preview["cost_cents"]), (True, "OK", 1_500_000))
        self.assertEqual(ok.preview["cost"].value, 1_500_000)
        bad = registry.check_action(self.player.pk, "found_company", {**FOUND, "type": "bank"})
        self.assertEqual((bad.available, bad.code), (False, "INVALID_COMPANY_TYPE"))
        poor = registry.check_action(self.new_player("poor").pk, "found_company", dict(FOUND))
        self.assertEqual((poor.available, poor.code), (False, "INSUFFICIENT_FUNDS"))
        self.assertEqual(registry.check_action(self.player.pk, "found_company").code, "OK")        # sem alvo: disponibilidade geral

    def test_invalid_targets(self):
        for action, bad in (("found_company", {"type": "retail"}), ("found_company", "retail"),
                            ("fund_company", {"company": 1}), ("fund_company", {"company": 1, "amount_cents": 1, "x": 2})):
            self.assertEqual(registry.execute_action(self.player.pk, action, bad).code, "INVALID_PARAMS", (action, bad))
        self.assertEqual(registry.execute_action(self.player.pk, "found_company").code, "TARGET_REQUIRED")


class AuditTests(CompanyTestCase):
    audit_companies_at_end = False

    def test_a_clean_world_passes_and_reports_stats(self):
        company = self.found()
        services.fund_company(self.player.pk, company, 700)
        report = audit_companies()
        self.assertTrue(report.ok, report.findings)
        self.assertEqual((report.stats["companies"], report.stats["contributions"], report.stats["capital"]), (1, 1, 700))

    def test_the_audit_flags_a_missing_owner_a_missing_account_and_a_wrong_founding_amount(self):
        company = self.found()
        Company.objects.filter(pk=company).update(founding_cost=1)
        from ledger.models import Account
        Account.objects.filter(kind="company", owner_id=company).delete()
        codes = {f["code"] for f in audit_companies().findings}
        self.assertEqual(codes, {"FOUNDING_ENTRY_MISMATCH", "COMPANY_ACCOUNT_MISSING"})

    def test_the_audit_flags_an_owner_position_without_holder(self):
        company = self.found()
        Position.objects.all().delete()
        self.assertIn("OWNER_POSITION_INVALID", {f["code"] for f in audit_companies().findings})

    def test_provisional_table_covers_every_parameter(self):
        rows = {r.parameter: r for r in params.provisional_table()}
        expected = {"initial_stars", "min_wage_per_day_cents", "wage_ceiling_per_day_cents", "income_tax_rate"}
        expected |= {f"relevant_skill.{k.value}" for k in PositionKind} | {f"hirable_kinds.{t.value}" for t in CompanyType}
        self.assertEqual(set(rows), expected)
        self.assertEqual(rows["initial_stars"].status, "PROV")
        self.assertEqual(rows["wage_ceiling_per_day_cents"].value, "None")      # T sem teto: None, nunca 0


class JobsAuditTests(CompanyTestCase):
    audit_companies_at_end = False

    def setUp(self):
        super().setUp()
        from companies import jobs
        self.company = self.found(self.player, "industrial", "Fábrica", 0)
        self.position = jobs.open_position(self.player.pk, self.company, "worker", 1_000, {}).detail["position"]
        application = jobs.apply_to_position(self.other.pk, self.position).detail["application"]
        self.assertTrue(jobs.approve_application(self.player.pk, application).ok)

    def codes(self):
        return {f["code"] for f in audit_companies().findings}

    def test_a_clean_hire_passes(self):
        report = audit_companies()
        self.assertTrue(report.ok, report.findings)

    def test_the_audit_flags_forbidden_kinds_and_missing_events_and_the_database_refuses_incoherent_status(self):
        from companies.models import PositionEvent
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():           # o próprio banco recusa status incoerente
            Position.objects.filter(pk=self.position).update(status="open")
        Position.objects.filter(pk=self.position).update(kind="salesperson")
        self.assertIn("POSITION_KIND_NOT_ALLOWED", self.codes())
        Position.objects.filter(pk=self.position).update(kind="worker")
        from django.db import connection
        with connection.cursor() as cursor:                      # o modelo é imutável: apagar só por SQL, de propósito
            cursor.execute("DELETE FROM companies_positionevent WHERE kind IN ('hired', 'position_opened')")
        self.assertTrue({"FILLED_POSITION_WITHOUT_HIRE_EVENT", "POSITION_WITHOUT_OPEN_EVENT"} <= self.codes())
        self.assertEqual(PositionEvent.objects.count(), 1)

    def test_the_audit_flags_a_pending_application_on_a_filled_position(self):
        from companies.models import Application
        Application.objects.create(position_id=self.position, applicant=self.player, created_at=1)
        self.assertIn("PENDING_APPLICATION_ON_CLOSED_POSITION", self.codes())
