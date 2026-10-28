"""
Concorrência do Orçamento: repasses simultâneos da mesma conta, repasse × compromisso, confirmação repetida e confirmação × edição do plano.
Propriedades valem em PostgreSQL e em SQLite (o banco serializa). A ordem estrita entre linhas de tabelas diferentes só é garantida pelo
`SELECT ... FOR UPDATE` (PostgreSQL): esses testes ficam marcados `CROSS_ROW` e NÃO contam como garantia em SQLite. As travas deste app são a segunda
defesa: a primeira é o ledger (saldo e reservas sob trava) e as restrições únicas do banco.
"""
import unittest

from django.db import connection
from django.test import TransactionTestCase

from accounts.models import Usuario
from budget import authority, plans, transfers
from budget.audit import audit_budget
from budget.constants import Level
from budget.govs import account_of, ensure_accounts
from budget.models import BudgetPlan, GovernmentDecision
from core.clock import ManualClock, use_clock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.models import City, State
from geography.tests.base import SMALL
from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import Nature
from ledger.models import Entry
from ledger.tests.base import fund_account, install_test_role
from ledger.tests.test_scenario_concurrency import run_together
from players.services import create_player
from players.tests.base import T0

ON_PG = connection.vendor == "postgresql"
CROSS_ROW = unittest.skipUnless(ON_PG, "ordem entre linhas de tabelas diferentes: só o SELECT ... FOR UPDATE (PostgreSQL) a garante; em SQLite não há trava de linha")


class BudgetConcurrencyBase(TransactionTestCase):
    def setUp(self):
        install_test_role(self)
        generate_world(get_scenario(**SMALL))
        self.clk = ManualClock(T0)
        cm = use_clock(self.clk)
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.president, self.governor, self.mayor, self.other = (create_player(Usuario.objects.create_user(n)) for n in ("pres", "gov", "mayor", "other"))
        self.state = State.objects.order_by("pk").first()
        self.city = City.objects.filter(state=self.state).order_by("pk").first()
        holders = {(Level.UNION, 0): self.president.pk, (Level.STATE, self.state.pk): self.governor.pk, (Level.MUNICIPALITY, self.city.pk): self.mayor.pk}
        authority.register_office_provider("test", lambda level, ident: holders.get((level, ident)))
        self.addCleanup(authority.unregister_office_provider, "test")
        ensure_accounts()
        self.union, self.st, self.mun = account_of(Level.UNION, 0), account_of(Level.STATE, self.state.pk), account_of(Level.MUNICIPALITY, self.city.pk)

    def to_state(self, amount):
        return {"from": {"level": "union", "id": 0}, "to": {"level": "state", "id": self.state.pk}, "amount": amount}

    def assertClean(self):
        for report in (audit_budget(), audit_ledger()):
            self.assertTrue(report.ok, report.findings)


class TransferConcurrencyTests(BudgetConcurrencyBase):
    def test_two_transfers_that_together_overdraw_let_exactly_one_through(self):
        fund_account(self.union, 1_000)
        jobs = run_together(lambda: transfers.transfer_budget(self.president.pk, self.to_state(700)),
                            lambda: transfers.transfer_budget(self.president.pk, self.to_state(700)))
        self.assertEqual(sorted(j.result.code for j in jobs), ["INSUFFICIENT_FUNDS", "OK"], [j.result for j in jobs])
        self.assertEqual((ledger.balance_of(self.union.pk), ledger.balance_of(self.st.pk)), (300, 700))
        self.assertEqual(GovernmentDecision.objects.count(), 1)           # a recusada não deixa decisão
        self.assertEqual(Entry.objects.filter(nature="gov_transfer").count(), 1)
        self.assertClean()

    def test_transfers_that_fit_together_all_go_through_and_money_is_conserved(self):
        fund_account(self.union, 3_000)
        jobs = run_together(*[(lambda: transfers.transfer_budget(self.president.pk, self.to_state(1_000))) for _ in range(3)])
        self.assertEqual([j.result.code for j in jobs], ["OK"] * 3)
        self.assertEqual((ledger.balance_of(self.union.pk), ledger.balance_of(self.st.pk)), (0, 3_000))
        self.assertEqual(GovernmentDecision.objects.count(), 3)
        self.assertEqual(len({d.ledger_key for d in GovernmentDecision.objects.all()}), 3)
        self.assertClean()

    def test_transfer_versus_new_commitment_never_spends_the_committed_money(self):
        fund_account(self.union, 1_000)
        jobs = run_together(lambda: transfers.transfer_budget(self.president.pk, self.to_state(800)),
                            lambda: ledger.hold(self.union.pk, 800, key="h", reference_kind="test", reference_id="1", at=self.clk.now()))
        transferred = jobs[0].result.ok
        held = jobs[1].result.ok
        self.assertFalse(transferred and held, [j.result for j in jobs])          # 800 + 800 > 1.000: só um dos dois cabe
        self.assertTrue(transferred or held)
        self.assertGreaterEqual(ledger.available_of(self.union.pk), 0)
        self.assertClean()


class PlanConcurrencyTests(BudgetConcurrencyBase):
    def setUp(self):
        super().setUp()
        payer = ledger.player_account(self.other.pk)
        fund_account(payer, 100_000)
        assert ledger.transfer(payer.pk, self.mun.pk, 100_000, Nature.DONATION, key="r", reference_kind="test",
                               reference_id="1", at=self.clk.now()).ok
        self.lines = {"education": 10_000, "health": 10_000, "infrastructure": 10_000}
        self.target = {"city": self.city.pk, "lines": self.lines}

    def test_two_confirmations_at_once_record_one_decision(self):
        self.assertTrue(plans.set_plan(self.mayor.pk, self.target).ok)
        jobs = run_together(lambda: plans.confirm_plan(self.mayor.pk, {"city": self.city.pk}), lambda: plans.confirm_plan(self.mayor.pk, {"city": self.city.pk}))
        self.assertEqual(sorted(j.result.code for j in jobs), ["OK", "PLAN_CONFIRMED"], [j.result for j in jobs])
        self.assertEqual(GovernmentDecision.objects.filter(kind="plan_confirmed").count(), 1)
        self.assertClean()

    def test_editing_versus_confirming_leaves_a_consistent_plan(self):
        """Qualquer ordem vale, mas o plano final e a decisão registrada precisam concordar entre si (a auditoria confere linhas × decisão × total)."""
        outcomes = set()
        for n in range(6):
            BudgetPlan.objects.all().delete()
            GovernmentDecision.objects.all().delete()
            self.assertTrue(plans.set_plan(self.mayor.pk, self.target).ok)
            edit, confirm = run_together(lambda: plans.set_plan(self.mayor.pk, {"city": self.city.pk, "lines": {**self.lines, "administration": 5_000}}),
                                         lambda: plans.confirm_plan(self.mayor.pk, {"city": self.city.pk}))
            outcomes.add((edit.result.code, confirm.result.code))
            plan = BudgetPlan.objects.get()
            self.assertEqual(plan.status, "confirmed" if confirm.result.ok else "draft")
            self.assertIn(edit.result.code, {"OK", "PLAN_CONFIRMED"})
            self.assertClean()
        self.assertTrue(outcomes <= {("OK", "OK"), ("PLAN_CONFIRMED", "OK")}, outcomes)

    @CROSS_ROW
    def test_confirmation_holding_the_account_lock_makes_a_concurrent_edit_wait(self):
        import threading
        import time
        from django.db import transaction
        from ledger.models import Account
        self.assertTrue(plans.set_plan(self.mayor.pk, self.target).ok)
        held, release = threading.Event(), threading.Event()

        def holder():
            from django.db import close_old_connections
            try:
                with transaction.atomic():
                    list(Account.objects.select_for_update().filter(pk=self.mun.pk))
                    held.set()
                    release.wait(10)
            finally:
                close_old_connections()
                connection.close()
        t = threading.Thread(target=holder)
        t.start()
        held.wait(10)
        box = {}

        def edit():
            from django.db import close_old_connections
            try:
                t0 = time.monotonic()
                box["res"] = plans.set_plan(self.mayor.pk, {"city": self.city.pk, "lines": {"education": 1}})
                box["took"] = time.monotonic() - t0
            finally:
                close_old_connections()
                connection.close()
        e = threading.Thread(target=edit)
        e.start()
        time.sleep(1.0)
        self.assertTrue(e.is_alive(), "a edição deveria esperar a trava da conta do Município")
        release.set()
        t.join(10)
        e.join(10)
        self.assertTrue(box["res"].ok)
        self.assertGreaterEqual(box["took"], 0.9)
        self.assertClean()
