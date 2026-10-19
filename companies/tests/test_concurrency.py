"""
Concorrência das Empresas. Protocolo (services.py): jogador → empresa → contas do ledger. Em PostgreSQL as linhas são travadas com
`FOR UPDATE`; em SQLite o banco serializa as escritas. Os testes verificam a PROPRIEDADE (sem saldo negativo, dinheiro conservado,
sequências únicas, sem deadlock, auditoria limpa), que vale nos dois.
"""
from django.test import TransactionTestCase

from accounts.models import Usuario
from companies import services
from companies.audit import audit_companies
from companies.models import CapitalContribution, Company
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
