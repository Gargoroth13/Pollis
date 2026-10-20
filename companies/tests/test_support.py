"""Cargos de suporte (02 §9): Engenheiro (bônus diário de produção) e Advogado (multiplicador de risco de Burnout, piso 1%)."""
from decimal import Decimal

from companies import jobs, params, production, stock, support
from companies.audit import audit_companies
from companies.models import CompaniesImmutableError, Company, Position, SupportWork, WorkWage
from players import registry
from players.models import Player
from skills.services import get_levels, specialization_value

from .test_production import ProductionBase

D = Decimal


class SupportBase(ProductionBase):
    def support_hire(self, player, kind, salary=1_000, company=None):
        return self.hire(player, company=company or self.firm, salary=salary, kind=kind)[0]

    def burnout_after_work(self, player):
        """Ganho de Burnout de UM Trabalhar do jogador (Energia/Burnout zerados antes)."""
        self.set_state(player, energy=D(100), nutrition=D(100), health=D(100), burnout=D(0), hospitalized_until=None, health_critical=False)
        res = registry.execute_action(player.pk, "work", None)
        self.assertTrue(res.ok, res)
        return res.detail["burnout_change"]

    def codes(self):
        return {f["code"] for f in audit_companies().findings}


class SupportLimitTests(SupportBase):
    def test_vacancies_for_each_support_kind_are_limited_by_the_star_and_closing_frees_a_slot(self):
        first = self.open("engineer", 1_000, company=self.firm)
        res = jobs.open_position(self.boss.pk, self.firm, "engineer", 1_000, {})
        self.assertRefused(res, "SUPPORT_LIMIT_REACHED", kind="engineer", stars=1, limit=1, have=1)
        self.assertTrue(jobs.open_position(self.boss.pk, self.firm, "lawyer", 1_000, {}).ok)          # o limite é por cargo
        self.assertRefused(jobs.open_position(self.boss.pk, self.firm, "lawyer", 1_000, {}), "SUPPORT_LIMIT_REACHED", kind="lawyer")
        self.assertTrue(jobs.close_position(self.boss.pk, first).ok)
        self.assertTrue(jobs.open_position(self.boss.pk, self.firm, "engineer", 1_000, {}).ok)
        self.assertEqual(self.codes(), set())

    def test_an_occupied_support_position_counts_and_more_stars_allow_more(self):
        self.support_hire(self.third, "engineer")
        self.assertRefused(jobs.open_position(self.boss.pk, self.firm, "engineer", 1_000, {}), "SUPPORT_LIMIT_REACHED", have=1)
        self.set_stars(3)
        self.assertTrue(jobs.open_position(self.boss.pk, self.firm, "engineer", 1_000, {}).ok)
        self.assertTrue(jobs.open_position(self.boss.pk, self.firm, "engineer", 1_000, {}).ok)
        self.assertRefused(jobs.open_position(self.boss.pk, self.firm, "engineer", 1_000, {}), "SUPPORT_LIMIT_REACHED", limit=3)
        self.assertEqual({n: params.SUPPORT_LIMIT_PER_STAR[n] for n in params.STARS}, {n: n for n in params.STARS})   # 02a §2.3

    def test_the_limit_is_checked_by_the_registry_before_the_action_is_tried(self):
        self.open("engineer", 1_000, company=self.firm)
        check = registry.check_action(self.boss.pk, "open_position",
                                      {"company": self.firm, "kind": "engineer", "salary_cents": 1_000, "requirements": {}})
        self.assertEqual((check.available, check.code), (False, "SUPPORT_LIMIT_REACHED"))


class EngineerTests(SupportBase):
    def setUp(self):
        super().setUp()
        self.engineer = self.third
        self.support_hire(self.engineer, "engineer")

    def test_an_engineer_work_registers_the_daily_contribution_and_is_paid_like_any_work(self):
        wages = WorkWage.objects.filter(player=self.engineer).count()
        out = self.work(self.engineer)
        self.assertEqual(out["paid"], 1_000)
        w = SupportWork.objects.get(player=self.engineer)
        self.assertEqual((w.kind, w.company_id, w.sequence, w.level, w.specialization), ("engineer", self.firm, wages + 1, 0, 0))
        self.assertEqual(w.contribution, D("0.020000"))                      # base × skill(0) × especialização(0)
        self.assertEqual(WorkWage.objects.get(player=self.engineer, sequence=w.sequence).position_id, w.position_id)
        self.assertEqual(self.codes(), set())

    def test_skill_and_specialization_raise_the_contribution_with_the_factors_explained(self):
        self.set_skill(self.engineer, "intelligence", 100)
        self.work(self.engineer)
        first = SupportWork.objects.get(player=self.engineer)
        self.assertEqual(first.contribution, D("0.06"))                       # 0,02 × (1 + 100 × 0,02)
        steps = {s["key"] for s in first.explained["steps"]}
        self.assertEqual(steps, {"engineer_base_per_work", "skill_effect", "specialization_effect"})
        self.assertGreater(specialization_value(self.engineer.pk, "flour"), 0)   # o Engenheiro se especializa no produto da empresa
        self.work(self.engineer)
        second = SupportWork.objects.filter(player=self.engineer).order_by("id").last()
        self.assertGreater(second.contribution, first.contribution)

    def test_the_daily_bonus_multiplies_what_the_production_workers_make_and_resets_next_day(self):
        self.set_skill(self.worker, "physical", 100)                          # 3 unidades por trabalho
        self.set_skill(self.engineer, "intelligence", 100)
        before = self.hook()
        self.assertEqual(before["per_work"].value, D(3))
        self.assertEqual(before["per_work"].step("engineering_bonus").amount, D(1))
        for _ in range(5):
            self.work(self.engineer)
        bonus = support.engineering_bonus(self.firm, self.clk.now())
        self.assertGreaterEqual(bonus.value, D("0.30"))                      # 5 × 0,06 (+ especialização que cresce)
        spec = specialization_value(self.worker.pk, "flour")                  # a especialização do funcionário também cresceu
        after = self.hook()
        self.assertEqual(after["per_work"].step("engineering_bonus").amount, 1 + bonus.value)
        pw = after["per_work"]
        self.assertEqual(pw.value, pw.step("units_per_work_base").amount * pw.step("skill_production").amount
                         * pw.step("specialization_production").amount * (1 + bonus.value) * pw.step("catalog_yield").amount)
        self.assertEqual(pw.step("specialization_production").amount, 1 + spec * params.SPECIALIZATION_PRODUCTION_PER_POINT)
        self.assertEqual(after["per_work"].step("engineering_bonus").detail.value, bonus.value)      # detalhamento (20)
        self.clk.advance(days=1)
        self.assertEqual(support.engineering_bonus(self.firm, self.clk.now()).value, D(0))
        self.assertEqual(self.hook()["per_work"].step("engineering_bonus").amount, D(1))
        self.assertEqual(self.codes(), set())

    def test_the_bonus_of_one_company_never_reaches_another(self):
        other = self.found(self.third, "industrial", "Outra", 0)
        self.assertTrue(production.set_production(self.third.pk, other, "flour").ok)
        self.work(self.engineer)
        self.assertEqual(support.engineering_bonus(other, self.clk.now()).value, D(0))
        self.assertGreater(support.engineering_bonus(self.firm, self.clk.now()).value, 0)

    def test_the_calibration_target_of_the_design_is_reached_by_the_structure_without_an_artificial_cap(self):
        """02 §9.1: empresa grande, Engenheiros com barra cheia → ~2,5× a produção base (alvo de balanceamento, não teto)."""
        stars = params.STARS[-1]
        works_per_bar = 5                                                     # 100 de Energia / 20 por Trabalhar (04 §2.2)
        total = sum(support.contribution_of("engineer", D(100), D(0)).value
                    for _ in range(params.SUPPORT_LIMIT_PER_STAR[stars] * works_per_bar))
        self.assertEqual(1 + total, D("2.5"))

    def test_support_works_do_not_need_a_product_and_are_not_blocked_by_the_production_state(self):
        from companies.models import ProductionLine
        ProductionLine.objects.filter(company_id=self.firm).update(setup_until=self.clk.now() + 3600)
        self.audit_companies_at_end = False
        out = self.work(self.engineer)
        self.assertEqual(out["paid"], 1_000)
        self.assertEqual(self.refusal_of_worker(), "COMPANY_IN_SETUP")          # quem produz continua bloqueado

    def refusal_of_worker(self):
        self.set_state(self.worker, energy=D(100), nutrition=D(100), health=D(100), burnout=D(0))
        return registry.execute_action(self.worker.pk, "work", None).code

    def test_support_contributions_are_immutable(self):
        self.work(self.engineer)
        w = SupportWork.objects.get()
        w.contribution = D(5)
        with self.assertRaises(CompaniesImmutableError):
            w.save()
        with self.assertRaises(CompaniesImmutableError):
            w.delete()

    def test_a_dismissed_engineer_stops_adding_but_the_day_keeps_what_was_done(self):
        self.work(self.engineer)
        before = support.engineering_bonus(self.firm, self.clk.now()).value
        position = Position.objects.get(holder_id=self.engineer.pk)
        self.assertTrue(jobs.dismiss(self.boss.pk, position.pk).ok)
        self.assertEqual(support.engineering_bonus(self.firm, self.clk.now()).value, before)
        out = self.work(self.engineer)                                         # sem emprego: Trabalho livre, nada de suporte
        self.assertIsNone(out)
        self.assertEqual(SupportWork.objects.count(), 1)


class LawyerTests(SupportBase):
    def setUp(self):
        super().setUp()
        self.lawyer = self.third
        self.support_hire(self.lawyer, "lawyer")

    def test_without_a_lawyer_work_the_burnout_gain_is_the_base_one(self):
        change = self.burnout_after_work(self.worker)
        self.assertEqual(change.value, D(5))
        self.assertEqual(change.step("risk").amount, D(1))

    def test_a_lawyer_work_lowers_the_risk_multiplier_of_the_employees_with_the_factors_explained(self):
        self.set_skill(self.lawyer, "intelligence", 100)
        self.work(self.lawyer)
        change = self.burnout_after_work(self.worker)
        self.assertEqual(change.value, D(5) * D("0.94"))                       # risco 100% − 6%
        risk = change.step("risk").detail                                      # piso de 1% sobre o multiplicador resolvido
        self.assertEqual(risk.value, D("0.94"))
        resolved = risk.steps[0].detail                                        # como o multiplicador foi composto (20)
        self.assertEqual(resolved.step("companies_lawyer").detail.step("lawyer_reduction_today").amount, D("-0.06"))
        self.assertEqual(self.codes(), set())

    def test_study_is_reduced_too_and_leisure_is_not_touched(self):
        self.set_skill(self.lawyer, "intelligence", 100)
        self.work(self.lawyer)
        self.set_state(self.worker, energy=D(100), nutrition=D(100), health=D(100), burnout=D(50))
        study = registry.execute_action(self.worker.pk, "study", None)
        self.assertTrue(study.ok, study)
        self.assertEqual(study.detail["burnout_change"].value, D(3) * D("0.94"))
        self.set_state(self.worker, energy=D(100), burnout=D(50))
        leisure = registry.execute_action(self.worker.pk, "leisure", None)
        self.assertEqual(leisure.detail["burnout_change"].value, D(-10))        # redução de Lazer inalterada (02 §9.2)

    def test_the_lawyer_himself_benefits_after_his_own_first_work_but_not_the_owner_nor_outsiders(self):
        self.set_skill(self.lawyer, "intelligence", 100)
        self.work(self.lawyer)
        self.assertEqual(self.burnout_after_work(self.lawyer).value, D(5) * D("0.94"))      # é funcionário da empresa
        self.assertEqual(self.burnout_after_work(self.boss).value, D(5))                    # o Dono não é um emprego contratado
        stranger = self.new_player("p4")
        self.assertEqual(self.burnout_after_work(stranger).value, D(5))

    def test_the_effect_is_per_company_and_resets_every_day(self):
        self.work(self.lawyer)
        other_company = self.found(self.boss, "industrial", "Outra", 0)
        production.set_production(self.boss.pk, other_company, "flour")
        stock.credit_stock(other_company, "wheat", 50, origin="test", key="seed:o", reference_kind="test", reference_id="9")
        other_worker = self.new_player("p5")
        self.hire(other_worker, company=other_company, salary=1_000)
        self.assertEqual(self.burnout_after_work(other_worker).value, D(5))
        self.assertLess(self.burnout_after_work(self.worker).value, D(5))
        self.clk.advance(days=1)
        self.assertEqual(self.burnout_after_work(self.worker).value, D(5))

    def test_many_works_hit_the_one_percent_floor_and_never_go_below(self):
        self.set_skill(self.lawyer, "intelligence", 100)
        for _ in range(40):
            self.work(self.lawyer)
        change = self.burnout_after_work(self.worker)
        self.assertEqual(change.value, D(5) * D("0.01"))
        self.assertTrue(change.step("risk").detail.step("risk_floor").binding)
        raw = support.lawyer_risk(self.firm, self.clk.now())
        self.assertLess(raw.value, 0)                                           # a soma passa de 100%; o piso é de `players`

    def test_the_action_preview_shows_what_will_be_paid(self):
        self.set_skill(self.lawyer, "intelligence", 100)
        self.work(self.lawyer)
        check = registry.check_action(self.worker.pk, "work", None)
        self.assertEqual(check.preview["burnout_change"].value, D(5) * D("0.94"))
        paid = self.burnout_after_work(self.worker)
        self.assertEqual(paid.value, check.preview["burnout_change"].value)

    def test_the_lawyer_specializes_in_his_own_activity(self):
        self.work(self.lawyer)
        self.assertGreater(specialization_value(self.lawyer.pk, params.LAWYER_SPECIALIZATION_KEY), 0)


class SupportAuditTests(SupportBase):
    def test_the_audit_flags_support_work_without_a_paid_work_and_a_wrong_day_and_limit_overflow(self):
        engineer = self.third
        self.support_hire(engineer, "engineer")
        self.work(engineer)
        self.assertEqual(self.codes(), set())
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("UPDATE companies_supportwork SET competence_day = competence_day + 1")
        self.assertIn("SUPPORT_WORK_DAY_MISMATCH", self.codes())
        with connection.cursor() as cursor:
            cursor.execute("UPDATE companies_supportwork SET competence_day = competence_day - 1, sequence = 99")
        self.assertIn("SUPPORT_WORK_WITHOUT_PAID_WORK", self.codes())
        with connection.cursor() as cursor:
            cursor.execute("UPDATE companies_supportwork SET sequence = 1, contribution = 9")
        self.assertIn("SUPPORT_CONTRIBUTION_MISMATCH", self.codes())
        self.audit_companies_at_end = False
        Company.objects.filter(pk=self.firm).update(stars=1)
        Position.objects.filter(holder_id=engineer.pk).update()
        extra = Position.objects.create(company_id=self.firm, kind="engineer", salary=1_000, status="open", requirements={},
                                        created_at=self.clk.now())
        self.assertIn("SUPPORT_LIMIT_EXCEEDED", self.codes())
        self.assertIsNotNone(extra.pk)
