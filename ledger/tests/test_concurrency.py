"""
Concorrência (design/24 §24.5.3). Em PostgreSQL as transações disputam o saldo com `SELECT ... FOR UPDATE` (contas travadas
em ordem crescente de id). Em SQLite (desenvolvimento) `select_for_update` não faz nada e o próprio banco serializa as
escritas; o teste verifica a PROPRIEDADE (nunca saldo negativo, um só vencedor, conservação), que vale nos dois.
"""
import threading
import time

from django.db import OperationalError, close_old_connections, connection
from django.test import TransactionTestCase

from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import AccountKind, Nature
from ledger.models import Account, Entry


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

    def test_same_idempotency_key_in_parallel_posts_once(self):
        def pay():
            return ledger.transfer(self.a.pk, self.b.pk, 30, Nature.SALE, key="dup", reference_kind="t", reference_id=1)
        results = self._run([pay, pay, pay])
        self.assertTrue(all(r.ok or r.code == "IDEMPOTENCY_CONFLICT" for r in results), results)
        self.assertGreaterEqual(sum(1 for r in results if r.ok), 1)
        self.assertEqual(ledger.balance_of(self.b.pk), 30)
        self.assertEqual(Entry.objects.filter(nature="sale").count(), 1)

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
