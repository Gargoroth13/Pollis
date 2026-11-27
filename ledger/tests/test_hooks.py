"""Ganchos de fim de operação do ledger: uma vez por operação completa, com o estado final, dentro da transação."""
from django.db import transaction

from ledger import hooks, obligations, services as ledger
from ledger.constants import Nature
from ledger.models import Obligation

from .base import LedgerTestCase


class OperationHookTests(LedgerTestCase):
    def setUp(self):
        super().setUp()
        self.calls = []
        hooks.register_operation_hook("probe", lambda ids, at: self.calls.append((sorted(ids), at)))
        self.addCleanup(hooks.unregister_operation_hook, "probe")

    def test_a_transfer_fires_once_with_both_accounts_and_the_operation_instant(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 1_000)
        self.calls.clear()
        self.assertTrue(ledger.transfer(a.pk, b.pk, 300, Nature.SALE, key="k", reference_kind="t", reference_id=1, at=777).ok)
        self.assertEqual(self.calls, [(sorted([a.pk, b.pk]), 777)])

    def test_multi_leg_operation_fires_once_after_all_legs(self):
        a, b, c = self.company(1), self.company(2), self.company(3)
        self.fund(a, 1_000)
        self.calls.clear()
        seen = []
        hooks.register_operation_hook("final", lambda ids, at: seen.append([ledger.balance_of(i) for i in sorted(ids)]))
        self.addCleanup(hooks.unregister_operation_hook, "final")
        res = ledger.post_transaction([ledger.Leg(a.pk, b.pk, 300, Nature.SALE), ledger.Leg(a.pk, c.pk, 200, Nature.SALE)],
                                      key="m", reference_kind="t", reference_id=1)
        self.assertTrue(res.ok)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(seen, [[500, 300, 200]])                                # estado FINAL de todas as pernas

    def test_not_fired_for_refusals_replays_or_holds(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        self.calls.clear()
        self.assertFalse(ledger.transfer(a.pk, b.pk, 500, Nature.SALE, key="x", reference_kind="t", reference_id=1).ok)
        self.assertTrue(ledger.hold(a.pk, 50, key="h", reference_kind="t", reference_id=1).ok)
        self.assertEqual(self.calls, [])
        ledger.transfer(a.pk, b.pk, 10, Nature.SALE, key="y", reference_kind="t", reference_id=1)
        ledger.transfer(a.pk, b.pk, 10, Nature.SALE, key="y", reference_kind="t", reference_id=1)
        self.assertEqual(len(self.calls), 1)

    def test_nested_operations_fire_once_when_the_outermost_ends_with_final_obligation_state(self):
        debtor, creditor = self.company(1), self.company(2)
        res = obligations.open_obligation(debtor.pk, creditor.pk, 1_000, Nature.WAGE, key="o", reference_kind="t", reference_id=1)
        ob = Obligation.objects.get(pk=res.detail["obligation_id"])
        self.fund(debtor, 400)
        self.calls.clear()
        states = []
        hooks.register_operation_hook("state", lambda ids, at: states.append(
            (ledger.balance_of(creditor.pk), Obligation.objects.get(pk=ob.pk).amount_paid)))
        self.addCleanup(hooks.unregister_operation_hook, "state")
        self.assertTrue(obligations.settle_obligations(debtor.pk, batch_key="s").ok)
        self.assertEqual(len(self.calls), 1)                                     # a quitação posta transação E atualiza a obrigação
        self.assertEqual(states, [(400, 400)])                                   # no fim: saldo E obrigação já atualizados

    def test_obligation_open_and_cancel_fire_for_both_parties(self):
        debtor, creditor = self.company(1), self.company(2)
        res = obligations.open_obligation(debtor.pk, creditor.pk, 1_000, Nature.WAGE, key="o", reference_kind="t", reference_id=1)
        self.assertEqual(self.calls[-1][0], sorted([debtor.pk, creditor.pk]))
        self.calls.clear()
        self.assertTrue(obligations.cancel_obligation(res.detail["obligation_id"], "x").ok)
        self.assertEqual([c[0] for c in self.calls], [sorted([debtor.pk, creditor.pk])])

    def test_hook_runs_inside_the_transaction_and_an_error_undoes_the_operation(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 500)

        def boom(ids, at):
            raise RuntimeError("falha do gancho")
        hooks.register_operation_hook("boom", boom)
        self.addCleanup(hooks.unregister_operation_hook, "boom")
        with self.assertRaises(RuntimeError):
            ledger.transfer(a.pk, b.pk, 100, Nature.SALE, key="k", reference_kind="t", reference_id=1)
        hooks.unregister_operation_hook("boom")
        self.assertEqual((ledger.balance_of(a.pk), ledger.balance_of(b.pk)), (500, 0))      # nada foi gravado

    def test_exception_inside_an_operation_clears_the_scope(self):
        with self.assertRaises(ValueError):
            with hooks.operation():
                hooks.touch(1, 5)
                raise ValueError
        self.assertEqual(self.calls, [])
        with hooks.operation():                                                   # escopo limpo: nada vaza para a próxima
            hooks.touch(2, 6)
        self.assertEqual(self.calls, [([2], 6)])

    def test_touch_outside_an_operation_fires_immediately(self):
        hooks.touch(9, 3)
        self.assertEqual(self.calls, [([9], 3)])

    def test_registration_rules_and_deterministic_order(self):
        with self.assertRaises(ValueError):
            hooks.register_operation_hook("probe", lambda i, a: None)
        order = []
        for n in ("c", "a", "b"):
            hooks.register_operation_hook(n, lambda i, a, n=n: order.append(n))
            self.addCleanup(hooks.unregister_operation_hook, n)
        with hooks.operation():
            hooks.touch(1, 1)
        self.assertEqual(order, ["a", "b", "c"])

    def test_rolled_back_outer_transaction_leaves_no_trace_from_hook_effects(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 500)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                ledger.transfer(a.pk, b.pk, 100, Nature.SALE, key="k", reference_kind="t", reference_id=1)
                raise RuntimeError
        self.assertEqual(ledger.balance_of(b.pk), 0)
