"""Construtora (02 §12; 10 §6): uma obra ativa por vez, progresso 0%→100% a cada Trabalhar, conclusão, bloqueio sem obra."""
from decimal import Decimal

from companies import construction, params, services
from companies.audit import audit_companies
from companies.models import CompaniesImmutableError, Company, ConstructionJob, ConstructionWork, WorkWage
from players import registry

from .test_production import ProductionBase

D = Decimal


class ConstructionBase(ProductionBase):
    def setUp(self):
        super().setUp()
        self.build = self.found(self.boss, "construction", "Construtora Beta", 0)
        self.assertTrue(services.fund_company(self.boss.pk, self.build, 100_000).ok)
        self.mason = self.third
        self.hire(self.mason, company=self.build, salary=1_000)

    def codes(self):
        return {f["code"] for f in audit_companies().findings}

    def start(self, project="low_density_simple", player=None, company=None):
        return construction.start_construction((player or self.boss).pk, company or self.build, project)

    def builder_work(self, player=None):
        player = player or self.mason
        self.set_state(player, energy=D(100), nutrition=D(100), health=D(100), burnout=D(0), hospitalized_until=None, health_critical=False)
        res = registry.execute_action(player.pk, "work", None)
        return res


class StartTests(ConstructionBase):
    def test_the_owner_starts_one_project_and_it_begins_at_zero(self):
        res = self.start()
        self.assertTrue(res.ok, res)
        job = ConstructionJob.objects.get()
        self.assertEqual((job.project, job.status, job.progress, job.sequence, job.completed_at), ("low_density_simple", "active", 0, 1, None))
        self.assertEqual(res.detail["work_units"], 50)
        self.assertEqual(construction.status_of(self.build)["active"]["project"], "low_density_simple")

    def test_refusals_owner_type_project_stars_and_one_active_at_a_time(self):
        self.assertEqual(self.start(player=self.mason).code, "NOT_OWNER")
        self.assertEqual(self.start(company=self.firm).code, "COMPANY_TYPE_CANNOT_BUILD")
        self.assertEqual(self.start(company=10 ** 9).code, "COMPANY_NOT_FOUND")
        self.assertEqual(self.start(company="x").code, "INVALID_PARAMS")
        self.assertEqual(self.start(project="castle").code, "UNKNOWN_PROJECT")
        self.assertEqual(self.start(project=7).code, "INVALID_PARAMS")
        self.assertEqual(construction.start_construction(10 ** 9, self.build, "low_density_simple").code, "PLAYER_NOT_FOUND")
        res = self.start("low_density_luxury")
        self.assertEqual((res.code, res.detail["required"], res.detail["stars"]), ("STARS_TOO_LOW", 3, 1))   # 10 §6: luxo baixa = 3★
        self.assertTrue(self.start().ok)
        self.assertEqual(self.start("low_density_simple").code, "CONSTRUCTION_ACTIVE")
        self.assertEqual(ConstructionJob.objects.count(), 1)

    def test_the_minimum_stars_follow_the_design_table(self):
        self.assertEqual({k: p.min_stars for k, p in params.CONSTRUCTION_PROJECTS.items()},
                         {"low_density_simple": 1, "high_density_simple": 2, "low_density_luxury": 3, "high_density_luxury": 4,
                          "commercial_1": 1, "commercial_2": 2, "commercial_3": 3, "commercial_4": 4, "commercial_5": 5,
                          "industrial": 2})
        Company.objects.filter(pk=self.build).update(stars=4)
        self.assertTrue(self.start("high_density_luxury").ok)

    def test_the_registry_offers_the_same_refusals(self):
        check = registry.check_action(self.boss.pk, "start_construction", {"company": self.build, "project": "castle"})
        self.assertEqual((check.available, check.code), (False, "UNKNOWN_PROJECT"))
        res = registry.execute_action(self.boss.pk, "start_construction", {"company": self.build, "project": "low_density_simple"})
        self.assertTrue(res.ok, res)
        self.assertEqual(registry.execute_action(self.boss.pk, "start_construction",
                                                 {"company": self.build, "project": "low_density_simple"}).code, "CONSTRUCTION_ACTIVE")


class WorkTests(ConstructionBase):
    def test_without_an_active_project_the_work_is_blocked_before_spending_energy_and_pays_nothing(self):
        self.set_state(self.mason, energy=D(100))
        res = self.builder_work()
        self.assertEqual((res.ok, res.code), (False, "COMPANY_NO_PROJECT"))
        self.assertIn("COMPANY_NO_PROJECT", registry.check_action(self.mason.pk, "work", None).blocked_by)
        self.assertEqual(WorkWage.objects.filter(player=self.mason).count(), 0)

    def test_each_work_advances_the_project_by_the_factors_and_is_paid(self):
        self.start()
        res = self.builder_work()
        self.assertTrue(res.ok, res)
        out = res.detail["hooks"][construction.ACTION_HOOK]
        self.assertEqual((out["progress_added"], out["progress"], out["completed"]), (D(2), D(2), False))      # 100 / 50 × skill(0)=1
        self.assertEqual(set(s.key for s in out["per_work"].steps),
                         {"progress_base_per_work", "skill_production", "specialization_production", "engineering_bonus"})
        self.assertEqual(res.detail["hooks"]["companies_work_wage"]["paid"], 1_000)
        w = ConstructionWork.objects.get()
        self.assertEqual((w.progress_added, w.progress_after), (D(2), D(2)))
        self.assertEqual(self.codes(), set())

    def test_skill_specialization_and_engineer_make_the_construction_faster(self):
        self.start()
        self.set_skill(self.mason, "physical", 100)
        first = self.builder_work().detail["hooks"][construction.ACTION_HOOK]
        self.assertEqual(first["progress_added"], D(6))                                                          # 2 × 3
        second = self.builder_work().detail["hooks"][construction.ACTION_HOOK]
        self.assertGreater(second["progress_added"], D(6))                                                       # especialização no projeto cresceu
        engineer = self.new_player("p9")
        self.hire(engineer, company=self.build, salary=1_000, kind="engineer")
        self.work(engineer)
        third = self.builder_work().detail["hooks"][construction.ACTION_HOOK]
        self.assertGreater(third["progress_added"], second["progress_added"])
        self.assertGreater(third["per_work"].step("engineering_bonus").amount, 1)
        self.assertEqual(self.codes(), set())

    def test_reaching_one_hundred_percent_completes_the_project_runs_the_hooks_and_frees_the_company(self):
        seen = []
        construction.register_completion_hook("test_prop", lambda job: seen.append((job.company_id, job.project, job.progress)))
        self.addCleanup(construction.unregister_completion_hook, "test_prop")
        self.start()
        self.set_skill(self.mason, "physical", 100)
        for _ in range(60):
            res = self.builder_work()
            if not res.ok:
                break
            if res.detail["hooks"][construction.ACTION_HOOK]["completed"]:
                break
        job = ConstructionJob.objects.get()
        self.assertEqual((job.status, job.progress), ("completed", D(100)))
        self.assertIsNotNone(job.completed_at)
        self.assertEqual(seen, [(self.build, "low_density_simple", D(100))])
        self.assertEqual(sum(ConstructionWork.objects.values_list("progress_added", flat=True)), D(100))        # o excedente se perde
        self.assertEqual(self.builder_work().code, "COMPANY_NO_PROJECT")                                         # acabou: sem obra ativa
        self.assertEqual(self.start("high_density_simple").code, "STARS_TOO_LOW")                                # 2★ exigidas
        self.assertTrue(self.start("low_density_simple").ok)                                                     # outra obra pode começar
        self.assertEqual(ConstructionJob.objects.count(), 2)
        self.assertEqual(self.codes(), set())

    def test_non_workers_of_the_construction_company_and_other_types_are_not_blocked(self):
        engineer = self.new_player("p9")
        self.hire(engineer, company=self.build, salary=1_000, kind="engineer")
        self.assertIsNotNone(self.work(engineer))                              # Engenheiro trabalha mesmo sem obra
        services_company = self.found(self.boss, "services", "Consultoria", 0)
        self.assertTrue(services.fund_company(self.boss.pk, services_company, 100_000).ok)
        clerk = self.new_player("p8")
        self.hire(clerk, company=services_company, salary=1_000)
        self.assertIsNotNone(self.work(clerk))                                 # Serviços: sem produto/obra, o Trabalho segue (e é pago)

    def test_progress_rows_are_immutable_and_the_audit_flags_tampering(self):
        self.start()
        self.builder_work()
        w = ConstructionWork.objects.get()
        with self.assertRaises(CompaniesImmutableError):
            w.delete()
        self.audit_companies_at_end = False
        ConstructionJob.objects.update(progress=D(50))
        self.assertIn("CONSTRUCTION_PROGRESS_MISMATCH", self.codes())
        ConstructionJob.objects.update(progress=D(2))
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("UPDATE companies_constructionwork SET sequence = 99")
        self.assertIn("CONSTRUCTION_WORK_WITHOUT_PAID_WORK", self.codes())

    def test_the_database_allows_only_one_active_project_and_a_coherent_completion(self):
        self.start()
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConstructionJob.objects.create(company_id=self.build, sequence=2, project="low_density_simple", status="active",
                                           progress=0, started_at=1, actor=self.boss.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConstructionJob.objects.filter(company_id=self.build).update(status="completed")             # sem data nem 100%
