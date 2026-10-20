"""
Concorrência das Empresas. Protocolo (services.py): jogador → empresa → contas do ledger. Em PostgreSQL as linhas são travadas com
`FOR UPDATE`; em SQLite o banco serializa as escritas. Os testes verificam a PROPRIEDADE (sem saldo negativo, dinheiro conservado,
sequências únicas, sem deadlock, auditoria limpa), que vale nos dois.
"""
from django.test import TransactionTestCase

from accounts.models import Usuario
from catalog.loader import sync_catalog
from companies import jobs, payroll, production, services, stock
from companies.audit import audit_companies
from companies.models import Application, CapitalContribution, Company, Position, PositionEvent
from core.models import WorldClock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger import services as ledger
from ledger.audit import audit_ledger, ledger_metrics
from ledger.tests.base import fund_account, install_test_role
from ledger.tests.test_scenario_concurrency import run_together
from players.services import create_player

REAL = 100


class CompanyConcurrencyTests(TransactionTestCase):
    def setUp(self):
        install_test_role(self)
        generate_world(get_scenario(**SMALL))
        WorldClock.load()                  # o ponteiro do mundo existe ANTES das fundações (a auditoria de folha lê o ponteiro)
        self.a, self.b = (create_player(Usuario.objects.create_user(f"c{n}")) for n in (1, 2))

    def money(self, player):
        return ledger.balance_of(ledger.player_account(player.pk).pk)

    def assertClean(self):
        for report in (audit_companies(), audit_ledger()):
            self.assertTrue(report.ok, report.findings)

    def test_simultaneous_foundings_by_one_founder_never_overspend_and_get_distinct_sequences(self):
        fund_account(ledger.player_account(self.a.pk), 40_000 * REAL)            # cabem exatamente 2 Varejos de R$ 15.000
        money = ledger_metrics()["in_circulation"]
        jobs = run_together(*[lambda n=n: services.found_company(self.a.pk, "retail", f"L{n}", 0) for n in range(4)])
        wins = [j for j in jobs if j.result.ok]
        self.assertEqual(len(wins), 2, [j.result for j in jobs])
        self.assertTrue(all(j.result.code == "INSUFFICIENT_FUNDS" for j in jobs if not j.result.ok))
        self.assertEqual(sorted(Company.objects.values_list("founding_sequence", flat=True)), [1, 2])
        self.assertEqual(self.money(self.a), 10_000 * REAL)
        self.assertEqual(ledger_metrics()["in_circulation"], money)
        self.assertClean()

    def test_simultaneous_contributions_and_foundings_conserve_money_and_numbers_stay_unique(self):
        fund_account(ledger.player_account(self.a.pk), 200_000 * REAL)
        company = services.found_company(self.a.pk, "retail", "Base", 0).detail["company"]
        money = ledger_metrics()["in_circulation"]
        calls = [lambda: services.fund_company(self.a.pk, company, 1_000 * REAL) for _ in range(4)]
        calls += [lambda: services.found_company(self.a.pk, "services", "S", 0) for _ in range(2)]
        jobs = run_together(*calls)
        self.assertTrue(all(j.result.ok for j in jobs), [j.result for j in jobs])
        self.assertEqual(sorted(CapitalContribution.objects.values_list("sequence", flat=True)), [1, 2, 3, 4])
        self.assertEqual(ledger.balance_of(services.company_account(company).pk), 4_000 * REAL)
        self.assertEqual(sorted(Company.objects.values_list("founding_sequence", flat=True)), [1, 2, 3])
        self.assertEqual(ledger_metrics()["in_circulation"], money)
        self.assertClean()

    def test_two_founders_and_cross_contributions_never_deadlock(self):
        for p in (self.a, self.b):
            fund_account(ledger.player_account(p.pk), 100_000 * REAL)
        ca = services.found_company(self.a.pk, "retail", "A", 0).detail["company"]
        cb = services.found_company(self.b.pk, "retail", "B", 0).detail["company"]
        for _ in range(4):
            jobs = run_together(lambda: services.fund_company(self.a.pk, ca, REAL), lambda: services.fund_company(self.b.pk, cb, REAL),
                                lambda: services.found_company(self.a.pk, "retail", "A2", 0),
                                lambda: services.found_company(self.b.pk, "retail", "B2", 0))
            self.assertTrue(all(j.result.ok for j in jobs), [j.result for j in jobs])
        self.assertClean()


class JobsConcurrencyTests(TransactionTestCase):
    """Protocolo: jogadores (id crescente) → empresa → vaga → candidatura → registro monetário. Sem deadlock, sem violar o banco."""

    def setUp(self):
        install_test_role(self)
        generate_world(get_scenario(**SMALL))
        WorldClock.load()
        self.boss, self.boss2, self.w1, self.w2, self.w3 = (
            create_player(Usuario.objects.create_user(f"j{n}")) for n in range(5))
        for p in (self.boss, self.boss2, self.w1, self.w2, self.w3):
            fund_account(ledger.player_account(p.pk), 200_000 * REAL)
        self.firm = services.found_company(self.boss.pk, "industrial", "Aço", 1_500).detail["company"]
        self.firm2 = services.found_company(self.boss2.pk, "industrial", "Ferro", 1_500).detail["company"]
        services.fund_company(self.boss.pk, self.firm, 50_000)
        sync_catalog()
        self.assertTrue(production.set_production(self.boss.pk, self.firm, "flour").ok)
        self.assertTrue(stock.credit_stock(self.firm, "wheat", 300, origin="test", key="seed:wheat", reference_kind="test",
                                           reference_id="1").ok)

    def opened(self, company=None, owner=None, salary=2_000):
        return jobs.open_position((owner or self.boss).pk, company or self.firm, "worker", salary, {}).detail["position"]

    def applied(self, player, position):
        res = jobs.apply_to_position(player.pk, position)
        self.assertTrue(res.ok, res)
        return res.detail["application"]

    def assertClean(self, companies=True):
        reports = [audit_ledger()] + ([audit_companies()] if companies else [])
        for report in reports:
            self.assertTrue(report.ok, report.findings)

    def test_two_approvals_for_one_vacancy_hire_exactly_one(self):
        for _ in range(4):
            position = self.opened()
            a1, a2 = self.applied(self.w1, position), self.applied(self.w2, position)
            out = run_together(lambda: jobs.approve_application(self.boss.pk, a1), lambda: jobs.approve_application(self.boss.pk, a2))
            self.assertEqual(sum(j.result.ok for j in out), 1, [j.result for j in out])
            self.assertEqual(Position.objects.get(pk=position).status, "filled")
            jobs.dismiss(self.boss.pk, position)
        self.assertClean()

    def test_one_candidate_approved_by_two_owners_at_once_gets_one_job(self):
        for _ in range(4):
            p1, p2 = self.opened(), self.opened(self.firm2, self.boss2)
            a1, a2 = self.applied(self.w1, p1), self.applied(self.w1, p2)
            out = run_together(lambda: jobs.approve_application(self.boss.pk, a1), lambda: jobs.approve_application(self.boss2.pk, a2))
            self.assertEqual(sum(j.result.ok for j in out), 1, [j.result for j in out])
            self.assertEqual(Position.objects.filter(holder=self.w1).exclude(kind="owner").count(), 1)
            jobs.resign(self.w1.pk)
        self.assertClean()

    def test_applications_racing_a_close_never_leave_a_pending_application_on_a_closed_vacancy(self):
        for _ in range(6):
            position = self.opened()
            out = run_together(lambda: jobs.close_position(self.boss.pk, position),
                               *[lambda p=p: jobs.apply_to_position(p.pk, position) for p in (self.w1, self.w2, self.w3)])
            self.assertTrue(out[0].result.ok)
            self.assertFalse(Application.objects.filter(position_id=position, status="pending").exists())
        self.assertClean()

    def test_resign_versus_dismiss_ends_the_job_exactly_once(self):
        for _ in range(4):
            position = self.opened()
            a = self.applied(self.w1, position)
            self.assertTrue(jobs.approve_application(self.boss.pk, a).ok)
            out = run_together(lambda: jobs.resign(self.w1.pk), lambda: jobs.dismiss(self.boss.pk, position))
            self.assertEqual(sum(j.result.ok for j in out), 1, [j.result for j in out])
            ended = PositionEvent.objects.filter(position_id=position, kind__in=["resigned", "dismissed"]).count()
            self.assertEqual(ended, 1)
        self.assertClean()

    def test_many_players_applying_at_once_each_gets_one_application(self):
        position = self.opened()
        out = run_together(*[lambda p=p: jobs.apply_to_position(p.pk, position) for p in (self.w1, self.w2, self.w3)] * 2)
        self.assertEqual(sum(j.result.ok for j in out), 3)
        self.assertTrue(all(j.result.code in ("OK", "ALREADY_APPLIED") for j in out))
        self.assertEqual(Application.objects.filter(position_id=position).count(), 3)
        self.assertClean()

    def test_works_funding_dismissal_and_the_payroll_tick_together_never_deadlock_nor_create_money(self):
        from decimal import Decimal
        from core import clock as game_clock
        from players import registry
        from players.models import Player
        positions = []
        for w in (self.w1, self.w2):
            position = self.opened(salary=3_000)
            self.assertTrue(jobs.approve_application(self.boss.pk, self.applied(w, position)).ok)
            positions.append(position)
        money = ledger_metrics()["in_circulation"]
        tick_at = game_clock.now() + 86_400 * 400          # o MESMO instante de tick em todas as rodadas (a folha é idempotente)

        def work(player):
            Player.objects.filter(pk=player.pk).update(energy=Decimal(100), nutrition=Decimal(100), burnout=Decimal(0))
            return registry.execute_action(player.pk, "work")

        for _ in range(3):
            out = run_together(lambda: work(self.w1), lambda: work(self.w2), lambda: work(self.w1),
                               lambda: services.fund_company(self.boss.pk, self.firm, 100),
                               lambda: payroll.run_daily_payroll(tick_at),
                               lambda: jobs.open_position(self.boss.pk, self.firm, "worker", 1_000, {}))
            self.assertTrue(all(j.result.ok for j in out if j.result is not None and hasattr(j.result, "ok")), [j.result for j in out])
        self.assertEqual(ledger_metrics()["in_circulation"], money)
        self.assertClean(companies=False)
        # cada salário de trabalho tem o seu pedido e sequência sem buracos
        from companies.models import WorkWage
        for w in (self.w1, self.w2):
            seqs = list(WorkWage.objects.filter(player=w).order_by("sequence").values_list("sequence", flat=True))
            self.assertEqual(seqs, list(range(1, len(seqs) + 1)))

    def test_works_purchases_sales_and_production_changes_together_keep_the_stock_exact_and_within_capacity(self):
        """Produção (Trabalho), entrada por compra, saída por venda e troca de produto, todos sobre a MESMA empresa: o estoque é a soma
        dos movimentos, nunca passa da capacidade da estrela nem fica negativo, e a empresa trava sempre antes do estoque."""
        from decimal import Decimal
        from companies.models import StockItem, StockMovement
        from players import registry
        from players.models import Player
        for w in (self.w1, self.w2, self.w3):
            self.assertTrue(jobs.approve_application(self.boss.pk, self.applied(w, self.opened(salary=2_000))).ok)

        def work(player):
            Player.objects.filter(pk=player.pk).update(energy=Decimal(100), nutrition=Decimal(100), burnout=Decimal(0))
            return registry.execute_action(player.pk, "work")

        counter = iter(range(10_000))

        def buy():
            return stock.credit_stock(self.firm, "wheat", 7, origin="test", key=f"buy:{next(counter)}", reference_kind="test",
                                      reference_id="c")

        def sell():
            return stock.debit_stock(self.firm, "flour", 1, destination="test", key=f"sell:{next(counter)}", reference_kind="test",
                                     reference_id="c")

        for _ in range(3):
            out = run_together(lambda: work(self.w1), lambda: work(self.w2), lambda: work(self.w3), buy, buy, sell, sell,
                               lambda: production.set_production(self.boss.pk, self.firm, "cheese"))
            for j in out:
                self.assertIsNone(getattr(j, "error", None), getattr(j, "error", None))
                self.assertIn(j.result.code, ("OK", "INSUFFICIENT_STOCK", "COOLDOWN_ACTIVE", "ALREADY_PRODUCING", "COMPANY_IN_SETUP",
                                              "MISSING_INPUTS", "STOCK_FULL"))
        capacity = int(stock.capacity_of(Company.objects.get(pk=self.firm).stars).value)
        self.assertLessEqual(stock.used_of(self.firm), capacity)
        for item in StockItem.objects.filter(company_id=self.firm):
            moved = sum(StockMovement.objects.filter(company_id=self.firm, product_id=item.product_id).values_list("delta", flat=True))
            self.assertEqual(item.quantity, moved)
        self.assertClean()

    def test_support_works_production_dismissal_and_vacancy_limit_never_break_the_daily_effect_or_the_limit(self):
        """Engenheiro, Advogado e funcionário de produção trabalhando juntos, demissão e abertura de vagas de suporte em disputa:
        o limite da estrela nunca é excedido, cada contribuição tem o seu salário e a auditoria fica limpa."""
        from decimal import Decimal
        from companies.models import Position, SupportWork
        from players import registry
        from players.models import Player
        eng = self.opened_kind("engineer")
        law = self.opened_kind("lawyer")
        self.assertTrue(jobs.approve_application(self.boss.pk, self.applied(self.w1, eng)).ok)
        self.assertTrue(jobs.approve_application(self.boss.pk, self.applied(self.w2, law)).ok)
        self.assertTrue(jobs.approve_application(self.boss.pk, self.applied(self.w3, self.opened())).ok)

        def work(player):
            Player.objects.filter(pk=player.pk).update(energy=Decimal(100), nutrition=Decimal(100), burnout=Decimal(0))
            return registry.execute_action(player.pk, "work")

        for _ in range(3):
            out = run_together(lambda: work(self.w1), lambda: work(self.w2), lambda: work(self.w3), lambda: work(self.w1),
                               lambda: jobs.open_position(self.boss.pk, self.firm, "engineer", 1_000, {}),
                               lambda: jobs.open_position(self.boss.pk, self.firm, "engineer", 1_000, {}),
                               lambda: jobs.open_position(self.boss.pk, self.firm, "lawyer", 1_000, {}))
            for j in out:
                self.assertIsNone(getattr(j, "error", None), getattr(j, "error", None))
        for kind in ("engineer", "lawyer"):
            self.assertLessEqual(Position.objects.filter(company_id=self.firm, kind=kind).exclude(status="closed").count(), 1)
        self.assertGreater(SupportWork.objects.count(), 0)
        out = run_together(lambda: work(self.w1), lambda: jobs.dismiss(self.boss.pk, eng), lambda: work(self.w2))
        for j in out:
            self.assertIsNone(getattr(j, "error", None), getattr(j, "error", None))
        self.assertClean()

    def opened_kind(self, kind, salary=1_000):
        return jobs.open_position(self.boss.pk, self.firm, kind, salary, {}).detail["position"]

    def test_simultaneous_support_vacancies_never_exceed_the_limit_of_the_star(self):
        """Quatro requisições do mesmo Dono (a trava do jogador e a da empresa serializam) abrindo vaga de Engenheiro ao mesmo tempo em 1★: sobra exatamente uma, rodada após rodada."""
        from companies.models import Position
        for _ in range(6):
            out = run_together(*[lambda: jobs.open_position(self.boss2.pk, self.firm2, "engineer", 1_000, {}) for _ in range(4)])
            codes = sorted(j.result.code for j in out)
            self.assertEqual(codes, ["OK", "SUPPORT_LIMIT_REACHED", "SUPPORT_LIMIT_REACHED", "SUPPORT_LIMIT_REACHED"])
            open_ids = list(Position.objects.filter(company_id=self.firm2, kind="engineer", status="open").values_list("pk", flat=True))
            self.assertEqual(len(open_ids), 1)
            self.assertTrue(jobs.close_position(self.boss2.pk, open_ids[0]).ok)
        self.assertClean()
