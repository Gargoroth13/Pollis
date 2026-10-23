"""
Concorrência dos Contratos: aceite duplo, aceite × retirada, execução diária repetida, quebra × execução, duas entregas disputando o
mesmo estoque e quebra dupla. Vale em PostgreSQL e em SQLite (o banco serializa); em PG nada mascara deadlock.
"""
from django.test import TransactionTestCase

from accounts.models import Usuario
from catalog.loader import sync_catalog
from companies import production, stock
from companies import services as company_services
from contracts import services
from contracts.audit import audit_contracts
from contracts.models import Contract, ContractEvent, ContractExecution
from core import clock as game_clock
from core.models import WorldClock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.models import Entry
from ledger.money import competence_day_of
from ledger.tests.base import fund_account, install_test_role
from ledger.tests.test_scenario_concurrency import run_together
from market.audit import audit_market
from players.services import create_player

REAL = 100


class ContractConcurrencyTests(TransactionTestCase):
    def setUp(self):
        install_test_role(self)
        generate_world(get_scenario(**SMALL))
        sync_catalog()
        WorldClock.load()
        self.boss, self.third, self.worker = (create_player(Usuario.objects.create_user(f"c{n}")) for n in (1, 2, 3))
        for p in (self.boss, self.third, self.worker):
            fund_account(ledger.player_account(p.pk), 500_000 * REAL)
        self.firm = company_services.found_company(self.boss.pk, "industrial", "Siderúrgica", 0).detail["company"]
        self.mill = company_services.found_company(self.third.pk, "industrial", "Moinho", 0).detail["company"]
        for owner, company in ((self.boss, self.firm), (self.third, self.mill)):
            self.assertTrue(production.set_production(owner.pk, company, "flour").ok)
            self.assertTrue(company_services.fund_company(owner.pk, company, 5_000_000).ok)
        self.assertTrue(stock.credit_stock(self.firm, "wheat", 400, origin="t", key="seed", reference_kind="t", reference_id="1").ok)
        self.today = competence_day_of(game_clock.now())
        self.seller, self.buyer = {"kind": "company", "id": self.firm}, {"kind": "company", "id": self.mill}

    def proposal(self, **over):
        p = {"type": "supply", "role": "seller", "proposer": self.seller, "counterparty": self.buyer,
             "terms": {"product": "wheat", "quantity": 100, "unit_price_cents": 1_000}, "frequency": "daily",
             "starts_on": self.today + 1, "ends_on": self.today + 3, "penalty_cents": 5_000}
        p.update(over)
        return p

    def active(self, **over):
        res = services.propose(self.boss.pk, self.proposal(**over))
        self.assertTrue(res.ok, res)
        self.assertTrue(services.accept(self.third.pk, res.detail["contract"], self.buyer).ok)
        return res.detail["contract"]

    def assertClean(self):
        for report in (audit_contracts(), audit_market(), audit_ledger()):
            self.assertTrue(report.ok, report.findings)

    def due(self):
        return services.run_due(self.today + 1, game_clock.now())

    def test_a_double_acceptance_activates_once_and_the_principal_is_paid_once(self):
        loan = {"type": "loan", "role": "lender", "proposer": {"kind": "player", "id": self.third.pk},
                "counterparty": {"kind": "player", "id": self.worker.pk},
                "terms": {"principal_cents": 100_000, "interest_rate": "0.02", "installments": 2}, "frequency": "daily"}
        cid = services.propose(self.third.pk, loan).detail["contract"]
        party = {"kind": "player", "id": self.worker.pk}
        jobs = run_together(*[lambda: services.accept(self.worker.pk, cid, party) for _ in range(5)])
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertTrue(all(j.result.code in {"NOT_PROPOSED", "ALREADY_ACCEPTED"} for j in jobs if not j.result.ok))
        self.assertEqual(Entry.objects.filter(transaction__key=f"contract:{cid}:disburse").count(), 1)
        self.assertEqual(ContractEvent.objects.filter(contract_id=cid, kind="activated").count(), 1)
        self.assertClean()

    def test_acceptance_versus_withdrawal_has_exactly_one_winner_and_a_coherent_state(self):
        cid = services.propose(self.boss.pk, self.proposal()).detail["contract"]
        jobs = run_together(lambda: services.accept(self.third.pk, cid, self.buyer),
                            lambda: services.withdraw(self.boss.pk, cid, self.seller))
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertIn(Contract.objects.get(pk=cid).status, {"active", "cancelled"})
        self.assertClean()

    def test_the_same_day_executed_by_many_threads_runs_each_occurrence_once(self):
        cid = self.active()
        jobs = run_together(*[self.due for _ in range(5)])
        self.assertEqual(sum(j.result["executions"] for j in jobs), 1, [j.result for j in jobs])
        self.assertEqual(ContractExecution.objects.filter(contract_id=cid).count(), 1)
        self.assertEqual(stock.quantity_of(self.mill, "wheat"), 100)
        self.assertEqual(stock.quantity_of(self.firm, "wheat"), 300)
        self.assertClean()

    def test_two_contracts_competing_for_the_same_stock_never_oversell_it(self):
        a = self.active(terms={"product": "wheat", "quantity": 300, "unit_price_cents": 100})
        b = self.active(terms={"product": "wheat", "quantity": 300, "unit_price_cents": 100})
        jobs = run_together(self.due, self.due)
        done = ContractExecution.objects.filter(contract_id__in=[a, b])
        self.assertEqual(done.count(), 2)
        self.assertEqual(sorted(done.values_list("status", flat=True)), ["failed", "success"])
        self.assertEqual(done.get(status="failed").failure_code, "INSUFFICIENT_STOCK")
        self.assertEqual((stock.quantity_of(self.firm, "wheat"), stock.quantity_of(self.mill, "wheat")), (100, 300))
        self.assertClean()

    def test_voluntary_break_versus_the_daily_execution_leaves_a_coherent_contract(self):
        cid = self.active()
        jobs = run_together(self.due, lambda: services.break_contract(self.third.pk, cid, self.buyer))
        c = Contract.objects.get(pk=cid)
        self.assertEqual(c.status, "broken")
        self.assertIn(ContractExecution.objects.filter(contract=c).count(), (0, 1))     # a execução ganhou a corrida ou não
        self.assertEqual(Entry.objects.filter(transaction__key=f"contract:{cid}:penalty").count(), 1)
        self.assertClean()

    def test_a_double_break_charges_the_penalty_once(self):
        cid = self.active()
        jobs = run_together(*[lambda: services.break_contract(self.third.pk, cid, self.buyer) for _ in range(4)])
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertTrue(all(j.result.code == "NOT_RUNNING" for j in jobs if not j.result.ok))
        self.assertEqual(Entry.objects.filter(transaction__key=f"contract:{cid}:penalty").count(), 1)
        self.assertClean()
