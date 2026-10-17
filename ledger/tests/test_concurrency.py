"""
Concorrência (design/24 §24.5.3). Em PostgreSQL as transações disputam o saldo com `SELECT ... FOR UPDATE` (contas travadas
em ordem crescente de id). Em SQLite (desenvolvimento) `select_for_update` não faz nada e o próprio banco serializa as
escritas; o teste verifica a PROPRIEDADE (nunca saldo negativo, um só vencedor, conservação), que vale nos dois.
"""
import os
import threading
import time

from django.db import OperationalError, close_old_connections, connection
from django.test import TransactionTestCase

from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import AccountKind, Nature
from ledger.services import HoldUse
from ledger.models import Account, Entry, Hold, Obligation, Transaction


def _retry(fn, attempts=60):
    for _ in range(attempts):
        try:
            return fn()
        except OperationalError:           # SQLite: tabela/banco bloqueado por outra thread; tentar de novo
            time.sleep(0.02)
    raise AssertionError("não conseguiu executar após várias tentativas")


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.a = ledger.get_or_create_account(AccountKind.COMPANY, 1)
        self.b = ledger.get_or_create_account(AccountKind.COMPANY, 2)
        self.c = ledger.get_or_create_account(AccountKind.COMPANY, 3)
        ledger.create_scenario("conc", {})
        ledger.grant_scenario_allocation("conc", self.a.pk, 100)

    def _run(self, jobs):
        barrier = threading.Barrier(len(jobs))
        results = [None] * len(jobs)

        def worker(i, job):
            try:
                barrier.wait(timeout=10)
                results[i] = _retry(job)
            finally:
                close_old_connections()
                connection.close()

        threads = [threading.Thread(target=worker, args=(i, j)) for i, j in enumerate(jobs)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        return results

    def test_two_payments_fighting_for_the_same_balance_only_one_wins(self):
        def pay(dest, key):
            return lambda: ledger.transfer(self.a.pk, dest.pk, 60, Nature.SALE, key=key, reference_kind="t", reference_id=key)
        results = self._run([pay(self.b, "p1"), pay(self.c, "p2")])
        codes = sorted(r.code for r in results)
        self.assertEqual(codes, ["INSUFFICIENT_FUNDS", "OK"])
        self.assertEqual(ledger.balance_of(self.a.pk), 40)
        self.assertEqual(ledger.balance_of(self.b.pk) + ledger.balance_of(self.c.pk), 60)
        self.assertTrue(audit_ledger().ok, audit_ledger().findings)

    def test_same_key_same_payload_in_parallel_returns_the_original_transaction_to_everyone(self):
        """Contrato: nenhuma requisição concorrente com a mesma chave e o mesmo conteúdo recebe conflito ou erro."""
        def pay():
            return ledger.transfer(self.a.pk, self.b.pk, 30, Nature.SALE, key="dup", reference_kind="t", reference_id=1)
        results = self._run([pay] * 6)
        self.assertTrue(all(r is not None and r.ok for r in results), [(r.code, r.detail) if r else None for r in results])
        self.assertEqual(len({r.detail["transaction_id"] for r in results}), 1)           # todas veem a MESMA transação
        self.assertEqual(len({tuple(r.detail["seqs"]) for r in results}), 1)
        self.assertEqual(sum(1 for r in results if not r.detail["already_posted"]), 1)    # exatamente uma criou
        self.assertEqual(ledger.balance_of(self.b.pk), 30)
        self.assertEqual(Entry.objects.filter(nature="sale").count(), 1)
        self.assertEqual(Transaction.objects.filter(key="dup").count(), 1)

    def test_same_key_different_payloads_in_parallel_one_wins_the_rest_conflict(self):
        def pay(amount):
            return lambda: ledger.transfer(self.a.pk, self.b.pk, amount, Nature.SALE, key="dup", reference_kind="t",
                                           reference_id=1)
        results = self._run([pay(10), pay(11), pay(12), pay(13)])
        self.assertEqual(sorted(r.code for r in results), ["IDEMPOTENCY_CONFLICT"] * 3 + ["OK"])
        winner = next(r for r in results if r.ok)
        self.assertEqual(ledger.balance_of(self.b.pk), winner.detail["amount"])
        self.assertEqual(Entry.objects.filter(nature="sale").count(), 1)

    def test_parallel_replays_that_consume_a_hold_consume_it_once(self):
        h = ledger.hold(self.a.pk, 50, key="h", reference_kind="t", reference_id=1).detail["hold_id"]

        def pay():
            return ledger.transfer(self.a.pk, self.b.pk, 50, Nature.SALE, key="dup", reference_kind="t", reference_id=1,
                                   uses=[HoldUse(h, 50)])
        results = self._run([pay] * 4)
        self.assertTrue(all(r.ok for r in results), [(r.code, r.detail) for r in results])
        self.assertEqual(Hold.objects.get(pk=h).status, "consumed")
        self.assertEqual(ledger.balance_of(self.b.pk), 50)

    def test_parallel_hold_obligation_and_request_with_the_same_key_return_the_original(self):
        from ledger import obligations

        def hold():
            return ledger.hold(self.a.pk, 10, key="hk", reference_kind="t", reference_id=1)

        def obligation():
            return obligations.open_obligation(self.a.pk, self.b.pk, 10, Nature.GOV_TRANSFER, key="ok", reference_kind="t",
                                               reference_id=1, competence_day=1)
        for job, ident in ((hold, "hold_id"), (obligation, "obligation_id")):
            results = self._run([job] * 4)
            self.assertTrue(all(r.ok for r in results), [(r.code, r.detail) for r in results])
            self.assertEqual(len({r.detail[ident] for r in results}), 1)
            self.assertEqual(sum(1 for r in results if not r.detail["already_posted"]), 1)
        self.assertEqual(Hold.objects.filter(key="hk").count(), 1)
        self.assertEqual(Obligation.objects.filter(key="ok").count(), 1)

    def test_opposite_direction_payments_do_not_deadlock_and_conserve(self):
        ledger.create_scenario("conc2", {})
        ledger.grant_scenario_allocation("conc2", self.b.pk, 100)
        jobs = [lambda i=i: ledger.transfer(self.a.pk, self.b.pk, 10, Nature.SALE, key=f"ab{i}", reference_kind="t", reference_id=i)
                for i in range(5)]
        jobs += [lambda i=i: ledger.transfer(self.b.pk, self.a.pk, 10, Nature.SALE, key=f"ba{i}", reference_kind="t", reference_id=i)
                 for i in range(5)]
        results = self._run(jobs)
        self.assertTrue(all(r is not None and r.ok for r in results), results)
        self.assertEqual(ledger.balance_of(self.a.pk) + ledger.balance_of(self.b.pk), 200)
        self.assertEqual(sum(a.balance for a in Account.objects.all()), 0)
        self.assertTrue(audit_ledger().ok, audit_ledger().findings)

    def test_concurrent_holds_cannot_oversubscribe(self):
        def hold(key):
            return lambda: ledger.hold(self.a.pk, 70, key=key, reference_kind="t", reference_id=key)
        results = self._run([hold("h1"), hold("h2")])
        self.assertEqual(sorted(r.code for r in results), ["INSUFFICIENT_AVAILABLE", "OK"])
        self.assertEqual(ledger.reserved_of(self.a.pk), 70)

    def test_two_different_keys_consuming_the_same_hold_only_one_succeeds(self):
        h = ledger.hold(self.a.pk, 50, key="h", reference_kind="t", reference_id=1).detail["hold_id"]

        def use(key):
            return lambda: ledger.transfer(self.a.pk, self.b.pk, 40, Nature.SALE, key=key, reference_kind="t",
                                           reference_id=key, uses=[HoldUse(h, 40)])
        results = self._run([use("u1"), use("u2")])
        self.assertEqual(sorted(r.code for r in results), ["HOLD_INSUFFICIENT", "OK"])
        hold = Hold.objects.get(pk=h)
        self.assertEqual((hold.amount, hold.status), (10, "active"))
        self.assertEqual((ledger.balance_of(self.a.pk), ledger.balance_of(self.b.pk)), (60, 40))
        self.assertTrue(audit_ledger().ok, audit_ledger().findings)

    def test_hold_and_payment_fighting_for_the_same_balance_never_oversubscribe(self):
        jobs = [lambda: ledger.hold(self.a.pk, 70, key="h", reference_kind="t", reference_id=1),
                lambda: ledger.transfer(self.a.pk, self.b.pk, 60, Nature.SALE, key="p", reference_kind="t", reference_id=1)]
        results = self._run(jobs)
        self.assertEqual(sum(1 for r in results if r.ok), 1, [(r.code, r.detail.get("account")) for r in results])
        self.assertGreaterEqual(ledger.available_of(self.a.pk), 0)               # nunca reservado + gasto > saldo
        self.assertTrue(audit_ledger().ok, audit_ledger().findings)

    def test_two_settlements_of_the_same_debtor_never_pay_more_than_owed(self):
        from ledger import obligations
        obligations.open_obligation(self.a.pk, self.b.pk, 80, Nature.GOV_TRANSFER, key="o", reference_kind="t",
                                    reference_id=1, competence_day=1)
        jobs = [lambda i=i: obligations.settle_obligations(self.a.pk, batch_key=f"s{i}") for i in range(3)]
        results = self._run(jobs)
        self.assertTrue(all(r.ok for r in results), [(r.code, r.detail) for r in results])
        ob = Obligation.objects.get()
        self.assertEqual((ob.amount_paid, ob.status), (80, "paid"))
        self.assertEqual((ledger.balance_of(self.a.pk), ledger.balance_of(self.b.pk)), (20, 80))
        self.assertTrue(audit_ledger().ok, audit_ledger().findings)


class DatabaseUnderTestTests(TransactionTestCase):
    def test_runs_on_the_expected_database(self):
        """`POLIS_EXPECT_DB=postgresql` só passa se a suíte estiver de fato rodando em PostgreSQL (evita declarar cobertura falsa)."""
        expected = os.environ.get("POLIS_EXPECT_DB")
        if not expected:
            self.skipTest("POLIS_EXPECT_DB não definido")
        self.assertEqual(connection.vendor, expected)
