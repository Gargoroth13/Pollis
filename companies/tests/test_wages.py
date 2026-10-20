"""Salário do Trabalho (por ação), folha diária do Dono (tick do mundo), `PENDING` e quitação (02 §16; 24 §24.12-24.13; GD 2026-10-19)."""
from decimal import Decimal

from companies import jobs, payroll, services
from companies.audit import audit_companies
from companies.models import WorkWage
from core import ticks
from core.models import WorldClock
from ledger import obligations, remuneration
from ledger.audit import ledger_metrics
from ledger import services as ledger
from ledger.constants import Nature, ObligationStatus
from ledger.models import Obligation, RemunerationRequest
from ledger.money import competence_day_of, from_reais
from players import registry
from players.tests.base import T0

from .test_jobs import JobsBase

DAY = 86_400
FIRST_MIDNIGHT = T0 + 12 * 3600          # T0 é 12:00 do horário do jogo: o tick diário seguinte é 00:00 do dia 6
TAX = Decimal("0.05")


class WageBase(JobsBase):
    owner_salary = 2_000                  # R$ 20/dia
    wage = 2_000                          # R$ 20 por ação de Trabalhar
    company_cash = 100_000                # R$ 1.000

    def setUp(self):
        super().setUp()
        services_company = self.found(self.boss, "industrial", "Siderúrgica", self.owner_salary)
        self.firm = services_company
        if self.company_cash:
            self.assertTrue(services.fund_company(self.boss.pk, self.firm, self.company_cash * 100).ok)
        self.position, _ = self.hire(self.worker, company=self.firm, salary=self.wage)

    def hire(self, player, position=None, company=None, salary=2_000, **kw):
        position = position or self.open(kw.get("kind", "worker"), salary, kw.get("requirements"), company=company)
        application = self.apply(player, position)
        res = jobs.approve_application(self.boss.pk, application)
        self.assertTrue(res.ok, res)
        return position, application

    def firm_account(self):
        return services.company_account(self.firm)

    def firm_money(self):
        return ledger.balance_of(self.firm_account().pk)

    def work(self, player=None):
        player = player or self.worker
        self.set_state(player, energy=Decimal(100), nutrition=Decimal(100), health=Decimal(100), burnout=Decimal(0),
                       hospitalized_until=None, health_critical=False)         # dias de espera não são o assunto destes testes
        res = registry.execute_action(player.pk, "work", None)
        self.assertTrue(res.ok, res)
        return res.detail["hooks"].get(payroll.WAGE_HOOK)

    def next_day(self, days=1):
        self.clk.advance(days=days)

    def world_tick(self):
        return ticks.advance_world()

    def goto_midnight(self):
        self.clk.set(FIRST_MIDNIGHT)
        self.world_tick()

    def requests(self, kind):
        return list(RemunerationRequest.objects.filter(reference_kind=kind).order_by("id"))


class WorkWageTests(WageBase):
    def test_each_work_of_an_employee_pays_the_position_salary_from_the_company_with_income_tax(self):
        w0, c0, u0 = self.money(self.worker), self.firm_money(), self.union()
        out = self.work()
        self.assertEqual((out["due"], out["recognized"], out["paid"], out["pending"]), (2_000, 2_000, 2_000, 0))
        tax = int(2_000 * TAX)
        self.assertEqual((out["tax"], out["net"]), (tax, 2_000 - tax))
        self.assertEqual((self.money(self.worker), self.firm_money(), self.union()), (w0 + 2_000 - tax, c0 - 2_000, u0 + tax))
        row = WorkWage.objects.get()
        self.assertEqual((row.player_id, row.position_id, row.company_id, row.sequence, row.due),
                         (self.worker.pk, self.position, self.firm, 1, 2_000))
        self.assertIn("sobra_S", out["explained"]["factors"])           # feedback explicável (20)
        self.work()
        self.assertEqual([w.sequence for w in WorkWage.objects.order_by("id")], [1, 2])

    def test_work_without_a_job_is_still_allowed_and_pays_nothing(self):
        before = self.money(self.third)
        self.assertIsNone(self.work(self.third))
        self.assertEqual((self.money(self.third), WorkWage.objects.count()), (before, 0))

    def test_the_owner_working_without_a_job_is_not_paid_a_work_wage(self):
        self.assertIsNone(self.work(self.boss))                    # o salário do Dono é diário, não por ação (02 §16)
        self.assertEqual(WorkWage.objects.count(), 0)

    def test_a_refused_work_pays_nothing(self):
        self.set_state(self.worker, energy=Decimal(0))
        res = registry.execute_action(self.worker.pk, "work", None)
        self.assertEqual((res.ok, res.code), (False, "INSUFFICIENT_ENERGY"))
        self.assertEqual((WorkWage.objects.count(), RemunerationRequest.objects.filter(reference_kind="work_wage").count()), (0, 0))

    def test_the_job_gives_the_activity_context_so_the_relevant_skill_grows(self):
        from skills.services import get_levels
        before = get_levels(self.worker.pk)
        self.work()
        after = get_levels(self.worker.pk)
        self.assertGreater(after[jobs.relevant_skill("worker")], before[jobs.relevant_skill("worker")])       # Físico
        others = [s for s in before if s != jobs.relevant_skill("worker")]
        self.assertTrue(all(after[s] == before[s] for s in others))
        boss_before = get_levels(self.boss.pk)
        self.work(self.boss)
        self.assertEqual(get_levels(self.boss.pk), boss_before)           # sem emprego: sem contexto, sem ganho (como antes)

    def test_the_cap_is_daily_not_per_click_and_the_work_is_never_blocked(self):
        self.position2, _ = self.hire(self.third, company=self.firm, salary=3_000)
        out = [self.work(self.third) for _ in range(3)]                  # W = R$ 50/dia = 5.000 centavos (11 §11.1 padrão)
        self.assertEqual([o["recognized"] for o in out], [3_000, 2_000, 0])
        self.assertEqual([o["paid"] for o in out], [3_000, 2_000, 0])
        self.assertEqual(out[1]["explained"]["restricted_by"], ["sobra_S"])
        self.assertEqual(WorkWage.objects.filter(player=self.third).count(), 3)          # a 3ª ação aconteceu, com R$ 0
        self.next_day()
        self.assertEqual(self.work(self.third)["recognized"], 3_000)        # contador novo no dia seguinte

    def test_s_comes_from_the_skill_of_the_position(self):
        self.set_skill(self.worker, "physical", 100)                        # S = 100 × 1,5 = R$ 150
        self.assertEqual(payroll.limits_for(self.worker.pk, Nature.WAGE, T0), (5_000, 15_000, None))
        self.set_skill(self.worker, "intelligence", 400)                    # a skill do cargo é Físico: Inteligência não conta
        self.assertEqual(payroll.limits_for(self.worker.pk, Nature.WAGE, T0)[1], 15_000)
        self.assertEqual(payroll.limits_for(self.boss.pk, Nature.OWNER_SALARY, T0)[1], 0)
        self.set_skill(self.boss, "intelligence", 20)
        self.assertEqual(payroll.limits_for(self.boss.pk, Nature.OWNER_SALARY, T0)[1], 3_000)
        with self.assertRaises(ValueError):
            payroll.limits_for(self.boss.pk, Nature.POLITICAL_SALARY, T0)       # natureza de outro sistema: sem valor inventado
        with self.assertRaises(ValueError):
            payroll.limits_for(self.third.pk, Nature.WAGE, T0)

    def test_a_higher_skill_raises_the_daily_cap_above_the_minimum_wage(self):
        self.set_skill(self.worker, "physical", 100)
        self.assertTrue(jobs.dismiss(self.boss.pk, self.position).ok)
        position, _ = self.hire(self.worker, company=self.firm, salary=9_000)
        out = [self.work() for _ in range(3)]
        total = sum(o["recognized"] for o in out)
        _, s_cap, _ = payroll.limits_for(self.worker.pk, Nature.WAGE, self.clk.now())
        self.assertEqual(out[0]["recognized"], 9_000)
        self.assertGreater(total, 5_000)                                  # acima do piso W: o limite pessoal S vale
        self.assertLessEqual(total, s_cap)                                # (a skill cresce a cada Trabalho: S sobe junto)
        self.assertEqual(total + sum(o["discarded"] for o in out), sum(o["due"] for o in out))

    def test_another_registered_provider_is_never_overridden(self):
        remuneration.clear_providers()
        sentinel = lambda pid, nature, at: (1, 1, None)  # noqa: E731
        remuneration.register_limits_provider(sentinel)
        payroll.ensure_limits_provider()
        self.assertIs(remuneration._limits_provider, sentinel)
        remuneration.clear_providers()
        payroll.ensure_limits_provider()
        self.assertIs(remuneration._limits_provider, payroll.limits_for)


class PendingWageTests(WageBase):
    company_cash = 10                      # R$ 10: não cobre o salário de R$ 20

    def test_without_cash_the_wage_becomes_an_auditable_obligation_and_no_money_is_created(self):
        w0, c0, u0 = self.money(self.worker), self.firm_money(), self.union()
        circulation = ledger_metrics()["in_circulation"]
        out = self.work()
        self.assertEqual((out["recognized"], out["paid"], out["pending"]), (2_000, 0, 2_000))
        self.assertEqual((out["tax"], out["net"]), (100, 1_900))          # o imposto é retido SÓ quando o valor for pago
        self.assertEqual((self.money(self.worker), self.firm_money(), self.union()), (w0, c0, u0))       # nada se moveu
        ob = Obligation.objects.get()
        self.assertEqual((ob.amount_due, ob.amount_paid, ob.status, ob.nature, ob.debtor_id, ob.creditor_id),
                         (2_000, 0, ObligationStatus.OPEN.value, Nature.WAGE.value, self.firm_account().pk,
                          ledger.player_account(self.worker.pk).pk))
        self.assertEqual(ob.reference_kind, "work_wage")
        self.assertEqual(RemunerationRequest.objects.get(key=WorkWage.objects.get().request_key).obligation_id, ob.pk)
        self.assertEqual(obligations.pending_summary(self.firm_account().pk)["total"], 2_000)
        self.assertEqual(ledger_metrics()["in_circulation"], circulation)          # dívida não é dinheiro (24 §24.9)

    def test_the_pending_wage_is_paid_once_when_the_company_has_cash_never_twice(self):
        self.work()
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, 50_000).ok)         # R$ 500
        self.goto_midnight()
        ob = Obligation.objects.get(nature=Nature.WAGE.value)
        self.assertEqual((ob.status, ob.amount_paid), (ObligationStatus.PAID.value, 2_000))
        paid_once = self.money(self.worker)
        self.world_tick()
        payroll.run_daily_payroll(FIRST_MIDNIGHT)                                          # repetir o mesmo dia: nada de novo
        self.assertEqual(self.money(self.worker), paid_once)
        self.assertEqual(Obligation.objects.get(nature=Nature.WAGE.value).amount_paid, 2_000)

    def test_the_dismissed_employee_still_receives_what_the_company_owed(self):
        self.work()
        self.assertTrue(jobs.dismiss(self.boss.pk, self.position).ok)
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, 50_000).ok)
        before = self.money(self.worker)
        self.goto_midnight()
        self.assertEqual(self.money(self.worker), before + 2_000 - int(2_000 * TAX))


class DirectPayrollTests(WageBase):
    company_cash = 10
    audit_companies_at_end = False         # chama a folha de um dia SEM avançar o ponteiro do mundo: a auditoria de dias acusaria

    def test_the_company_settles_oldest_first_and_before_the_new_payroll(self):
        for _ in range(3):
            self.work()
            self.next_day()
        wages = list(Obligation.objects.filter(nature=Nature.WAGE.value).order_by("competence_day"))
        self.assertEqual([o.amount_due for o in wages], [2_000, 2_000, 2_000])
        self.assertTrue(services.fund_company(self.boss.pk, self.firm, 3_000).ok)        # R$ 10 + R$ 30 = cobre 2 dos 3
        self.assertEqual(self.firm_money(), 4_000)
        payroll.run_daily_payroll(self.clk.now())
        paid = [Obligation.objects.get(pk=o.pk) for o in wages]
        self.assertEqual([(o.status, o.amount_paid) for o in paid],
                         [(ObligationStatus.PAID.value, 2_000), (ObligationStatus.PAID.value, 2_000),
                          (ObligationStatus.OPEN.value, 0)])                               # a mais antiga primeiro
        self.assertEqual(self.firm_money(), 0)
        todays = next(r for r in self.requests("owner_payroll") if r.reference_id.startswith(f"{self.firm}:"))
        self.assertEqual((todays.paid, todays.pending), (0, 2_000))                          # a folha do dia não furou a fila


class OwnerPayrollTests(WageBase):
    def test_the_owner_is_paid_once_per_day_by_the_company_in_one_batch_at_the_daily_tick(self):
        b0, c0, u0 = self.money(self.boss), self.firm_money(), self.union()      # a Fábrica do setUp não tem caixa: pendente
        self.clk.set(FIRST_MIDNIGHT - 1)
        self.world_tick()
        self.assertEqual(self.requests("owner_payroll"), [])
        self.clk.set(FIRST_MIDNIGHT)
        self.world_tick()
        reqs = self.requests("owner_payroll")
        self.assertEqual(len(reqs), 2)                                  # a Siderúrgica e a Fábrica do setUp (R$ 20 cada)
        firm_req = next(r for r in reqs if r.reference_id.startswith(f"{self.firm}:"))
        self.assertEqual((firm_req.nature, firm_req.status, firm_req.recognized, firm_req.paid, firm_req.pending, firm_req.tax),
                         (Nature.OWNER_SALARY.value, "recognized", 2_000, 2_000, 0, 100))
        self.assertEqual(firm_req.competence_day, competence_day_of(FIRST_MIDNIGHT))
        self.assertEqual(len({r.batch for r in reqs}), 1)               # UM lote por tick (24 §24.13)
        self.assertEqual(self.firm_money(), c0 - 2_000)
        self.assertEqual(self.union() - u0, 100)                        # imposto de renda retido, vai à União
        self.assertEqual(self.money(self.boss), b0 + 1_900)
        other = next(r for r in reqs if r is not firm_req)
        self.assertEqual((other.recognized, other.paid, other.pending), (2_000, 0, 2_000))

    def test_catching_up_several_days_pays_each_day_once_and_re_running_never_duplicates(self):
        self.clk.set(FIRST_MIDNIGHT + 2 * DAY)                          # 3 ticks diários de uma vez (lazy)
        self.world_tick()
        days = sorted(competence_day_of(FIRST_MIDNIGHT + i * DAY) for i in range(3))
        firm_days = sorted(r.competence_day for r in self.requests("owner_payroll") if r.reference_id.startswith(f"{self.firm}:"))
        self.assertEqual(firm_days, days)
        n = RemunerationRequest.objects.count()
        before = self.money(self.boss)
        self.world_tick()
        payroll.run_daily_payroll(FIRST_MIDNIGHT + 2 * DAY)
        self.assertEqual((RemunerationRequest.objects.count(), self.money(self.boss)), (n, before))

    def test_a_company_founded_after_a_tick_is_not_paid_for_the_day_it_did_not_exist(self):
        self.clk.set(FIRST_MIDNIGHT + 6 * 3600)
        late = self.found(self.third, "retail", "Tardia", 1_000)
        self.world_tick()
        self.assertEqual([r for r in self.requests("owner_payroll") if r.reference_id.startswith(f"{late}:")], [])
        self.clk.set(FIRST_MIDNIGHT + DAY)
        self.world_tick()
        self.assertEqual(len([r for r in self.requests("owner_payroll") if r.reference_id.startswith(f"{late}:")]), 1)

    def test_a_zero_salary_owner_has_no_payroll_request(self):
        free = self.found(self.third, "retail", "Sem pro-labore", 0)
        self.goto_midnight()
        self.assertEqual([r for r in self.requests("owner_payroll") if r.reference_id.startswith(f"{free}:")], [])

    def test_the_owner_salary_is_capped_by_the_daily_limit_like_any_remuneration(self):
        rich = self.found(self.third, "retail", "Pro-labore alto", 20_000)
        self.assertTrue(services.fund_company(self.third.pk, rich, 100_000 * 100).ok)
        self.goto_midnight()
        r = next(r for r in self.requests("owner_payroll") if r.reference_id.startswith(f"{rich}:"))
        self.assertEqual((r.due, r.recognized, r.discarded, r.paid), (20_000, 5_000, 15_000, 5_000))      # W = R$ 50/dia
        self.assertEqual(r.explained["restricted_by"], ["sobra_S"])

    def test_without_cash_the_owner_salary_is_pending_then_paid_when_funded(self):
        poor = self.found(self.third, "retail", "Sem caixa", 1_500)
        self.goto_midnight()
        r = next(r for r in self.requests("owner_payroll") if r.reference_id.startswith(f"{poor}:"))
        self.assertEqual((r.recognized, r.paid, r.pending), (1_500, 0, 1_500))
        ob = Obligation.objects.get(pk=r.obligation_id)
        self.assertEqual((ob.status, ob.nature, ob.creditor_id), (ObligationStatus.OPEN.value, Nature.OWNER_SALARY.value,
                                                                  ledger.player_account(self.third.pk).pk))
        before = self.money(self.third)
        self.assertTrue(services.fund_company(self.third.pk, poor, 50_000).ok)
        spent = before - self.money(self.third)
        self.clk.set(FIRST_MIDNIGHT + DAY)
        self.world_tick()
        self.assertEqual(Obligation.objects.get(pk=ob.pk).status, ObligationStatus.PAID.value)
        # o aporte saiu do próprio Dono; a folha devolve só o salário (nunca dinheiro novo)
        self.assertEqual(self.money(self.third), before - spent + 2 * 1_500 - 2 * int(1_500 * TAX))
        self.assertEqual(Obligation.objects.filter(debtor_id=services.company_account(poor).pk).count(), 1)


class PayrollAuditTests(WageBase):
    audit_companies_at_end = False
    audit_at_end = False                   # estes testes ADULTERAM registros de propósito

    def test_the_audit_is_clean_after_wages_payroll_and_pending(self):
        self.work()
        self.clk.set(FIRST_MIDNIGHT + DAY)
        self.world_tick()
        report = audit_companies()
        self.assertTrue(report.ok, report.findings)

    def test_the_audit_flags_a_skipped_payroll_day_a_changed_wage_and_a_missing_request(self):
        self.work()
        self.clk.set(FIRST_MIDNIGHT + DAY)
        self.world_tick()
        RemunerationRequest.objects.filter(reference_kind="owner_payroll", reference_id__startswith=f"{self.firm}:") \
            .order_by("id").first().delete()
        wage = WorkWage.objects.get()
        RemunerationRequest.objects.filter(key=wage.request_key).update(due=1)
        codes = {f["code"] for f in audit_companies().findings}
        self.assertTrue({"PAYROLL_DAYS_MISMATCH", "WAGE_REQUEST_MISMATCH"} <= codes, codes)
        RemunerationRequest.objects.filter(key=wage.request_key).delete()
        self.assertIn("WAGE_REQUEST_MISSING", {f["code"] for f in audit_companies().findings})
