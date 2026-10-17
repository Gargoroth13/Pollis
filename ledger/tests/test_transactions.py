import random
from decimal import Decimal
from unittest import mock

from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import MAX_AMOUNT, AccountKind, Nature
from ledger.models import Account, Entry, Hold, LedgerImmutableError, Transaction
from ledger.services import HoldUse, Leg, post_transaction

from .base import LedgerTestCase


class AccountTests(LedgerTestCase):
    def test_get_or_create_is_idempotent_and_singletons(self):
        a1, a2 = self.company(1), self.company(1)
        self.assertEqual(a1.pk, a2.pk)
        self.assertEqual(ledger.union_account().pk, ledger.union_account().pk)
        self.assertEqual(ledger.sink_account().kind, "sink")
        self.assertEqual(ledger.issuance_account().kind, "issuance")

    def test_invalid_owners(self):
        for kind, oid, ref in ((AccountKind.UNION, 3, ""), (AccountKind.COMPANY, 0, ""), (AccountKind.COMPANY, 5, "x"),
                               (AccountKind.RETENTION, 0, ""), (AccountKind.PLAYER, 999999, ""),
                               (AccountKind.STATE, 999999, ""), (AccountKind.MUNICIPALITY, 999999, "")):
            with self.assertRaises(ledger.LedgerRefusal, msg=(kind, oid, ref)):
                ledger.get_or_create_account(kind, oid, ref)

    def test_close_requires_empty_and_never_deletes(self):
        a = self.company(1)
        self.fund(a, 100)
        self.assertEqual(ledger.close_account(a.pk).code, "ACCOUNT_NOT_EMPTY")
        self.pay(a, self.company(2), 100)
        self.assertTrue(ledger.close_account(a.pk).ok)
        self.assertEqual(self.pay(self.company(2), a, 10).code, "ACCOUNT_CLOSED")
        self.assertEqual(ledger.close_account(ledger.union_account().pk).code, "ACCOUNT_NOT_CLOSABLE")
        self.assertEqual(ledger.close_account(987654).code, "ACCOUNT_NOT_FOUND")
        self.assertTrue(Account.objects.filter(pk=a.pk).exists())


class TransferTests(LedgerTestCase):
    def test_normal_transfer_records_everything(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 1000)
        res = self.pay(a, b, 250, category="shop", operation="buy", explained={"why": "test"})
        self.assertTrue(res.ok, res)
        self.assertEqual((self.bal(a), self.bal(b)), (750, 250))
        e = Entry.objects.get(pk=res.detail["seqs"][0])
        self.assertEqual((e.from_balance_before, e.from_balance_after, e.to_balance_before, e.to_balance_after),
                         (1000, 750, 0, 250))
        self.assertEqual((e.nature, e.category, e.operation, e.reference_kind, e.at), ("sale", "shop", "buy", "test", self.clk.now()))
        self.assertEqual(e.explained, {"why": "test"})

    def test_conservation_after_each_operation(self):
        a, b, c = self.company(1), self.company(2), self.company(3)
        self.fund(a, 1000)
        for args in ((a, b, 300), (b, c, 100), (c, a, 50)):
            self.assertTrue(self.pay(*args).ok)
            self.assertEqual(sum(x.balance for x in Account.objects.all()), 0)
            emitted, circ, ret, sink = self.total_supply()
            self.assertEqual(emitted, circ + ret + sink)

    def test_amount_limits(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 10)
        self.assertEqual(self.pay(a, b, 0).code, "AMOUNT_NOT_POSITIVE")
        self.assertEqual(self.pay(a, b, -1).code, "AMOUNT_NOT_POSITIVE")
        self.assertEqual(self.pay(a, b, 1.5).code, "AMOUNT_NOT_IN_CENTAVOS")
        self.assertEqual(self.pay(a, b, Decimal("1")).code, "AMOUNT_NOT_IN_CENTAVOS")
        self.assertEqual(self.pay(a, b, MAX_AMOUNT + 1).code, "AMOUNT_TOO_LARGE")
        self.assertTrue(self.pay(a, b, 1).ok)                 # 1 centavo é válido
        self.assertEqual(self.pay(a, b, 10).code, "INSUFFICIENT_FUNDS")

    def test_max_amount_balance_cap(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, MAX_AMOUNT)
        self.fund(b, 1)
        self.assertEqual(self.pay(a, b, MAX_AMOUNT).code, "AMOUNT_TOO_LARGE")      # saldo de b passaria do teto

    def test_insufficient_funds_has_explained(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        res = self.pay(a, b, 150)
        self.assertEqual(res.code, "INSUFFICIENT_FUNDS")
        self.assertEqual((res.detail["gross"], res.detail["available"], res.detail["shortfall"]), (100, 100, 50))
        self.assertIn("steps", res.detail["explained"])
        self.assertEqual(Entry.objects.filter(nature="sale").count(), 0)

    def test_same_account_and_unknown_and_closed(self):
        a = self.company(1)
        self.fund(a, 10)
        self.assertEqual(ledger.transfer(a.pk, a.pk, 1, Nature.SALE, key="s", reference_kind="t", reference_id=1).code, "SAME_ACCOUNT")
        self.assertEqual(ledger.transfer(a.pk, 99999, 1, Nature.SALE, key="s2", reference_kind="t", reference_id=1).code, "ACCOUNT_NOT_FOUND")
        self.assertEqual(Entry.objects.filter(nature="sale").count(), 0)

    def test_reference_key_and_nature_required(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 10)
        self.assertEqual(ledger.transfer(a.pk, b.pk, 1, Nature.SALE, key="", reference_kind="t", reference_id=1).code, "KEY_REQUIRED")
        self.assertEqual(ledger.transfer(a.pk, b.pk, 1, Nature.SALE, key="k", reference_kind="", reference_id=1).code, "REFERENCE_REQUIRED")
        self.assertEqual(ledger.transfer(a.pk, b.pk, 1, Nature.SALE, key="k", reference_kind="t", reference_id="").code, "REFERENCE_REQUIRED")
        self.assertEqual(ledger.transfer(a.pk, b.pk, 1, "bogus", key="k", reference_kind="t", reference_id=1).code, "NATURE_INVALID")
        self.assertEqual(post_transaction([], key="k", reference_kind="t", reference_id=1).code, "EMPTY_TRANSACTION")

    def test_remuneration_natures_cannot_use_transfer(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        for n in (Nature.WAGE, Nature.MILITARY_PAY, Nature.OWNER_SALARY, Nature.POLITICAL_SALARY):
            self.assertEqual(self.pay(a, b, 10, nature=n).code, "NATURE_REQUIRES_PAYROLL")


class IdempotencyAndAtomicityTests(LedgerTestCase):
    def test_same_key_same_payload_returns_original(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        def go():
            return ledger.transfer(a.pk, b.pk, 30, Nature.SALE, key="same", reference_kind="t", reference_id=1)
        r1, r2 = go(), go()
        self.assertTrue(r1.ok and r2.ok, (r1, r2))
        self.assertTrue(r2.detail["already_posted"])
        self.assertEqual(r1.detail["seqs"], r2.detail["seqs"])
        self.assertEqual(self.bal(b), 30)

    def test_same_key_different_payload_conflicts(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        self.pay(a, b, 30, key="same")
        self.assertEqual(self.pay(a, b, 31, key="same").code, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(self.bal(b), 30)

    def test_failure_in_second_leg_leaves_nothing(self):
        a, b, c = self.company(1), self.company(2), self.company(3)
        self.fund(a, 100)
        res = post_transaction([Leg(a.pk, b.pk, 60, Nature.SALE), Leg(a.pk, c.pk, 60, Nature.SALE)], key="two",
                               reference_kind="t", reference_id=1)
        self.assertEqual(res.code, "INSUFFICIENT_FUNDS")
        self.assertEqual((self.bal(a), self.bal(b), self.bal(c)), (100, 0, 0))
        self.assertFalse(Transaction.objects.filter(key="two").exists())
        self.assertEqual(Entry.objects.filter(nature="sale").count(), 0)

    def test_multi_leg_sees_running_balance(self):
        a, b, c = self.company(1), self.company(2), self.company(3)
        self.fund(a, 100)
        res = post_transaction([Leg(a.pk, b.pk, 100, Nature.SALE), Leg(b.pk, c.pk, 100, Nature.SALE)], key="chain",
                               reference_kind="t", reference_id=1)
        self.assertTrue(res.ok, res)
        self.assertEqual((self.bal(a), self.bal(b), self.bal(c)), (0, 0, 100))


class IdempotencyRaceTests(LedgerTestCase):
    """
    O caminho da corrida SEM threads: a checagem inicial e a reconferência depois do travamento "não veem" a transação que
    outra requisição já gravou; a violação da chave única na gravação deve resultar na transação ORIGINAL (mesmo conteúdo)
    ou em IDEMPOTENCY_CONFLICT (conteúdo diferente) — nunca em erro, nem em gravação duplicada, nem em reserva consumida.
    """

    def setUp(self):
        super().setUp()
        self.a, self.b = self.company(1), self.company(2)
        self.fund(self.a, 1000)

    def blind_first_lookups(self, n=2):
        calls = {"n": 0}
        real = ledger._existing_transaction

        def lookup(key):
            calls["n"] += 1
            return None if calls["n"] <= n else real(key)
        return mock.patch.object(ledger, "_existing_transaction", side_effect=lookup), calls

    def go(self, amount=100, key="race", **kw):
        return ledger.transfer(self.a.pk, self.b.pk, amount, Nature.SALE, key=key, reference_kind="t", reference_id=1, **kw)

    def test_lost_race_with_same_payload_returns_the_original(self):
        first = self.go()
        patch, calls = self.blind_first_lookups()
        with patch:
            second = self.go()
        self.assertGreaterEqual(calls["n"], 3)                       # passou pela releitura depois da violação
        self.assertTrue(second.ok, second)
        self.assertTrue(second.detail["already_posted"])
        self.assertEqual((second.detail["transaction_id"], second.detail["seqs"]), (first.detail["transaction_id"], first.detail["seqs"]))
        self.assertEqual((self.bal(self.b), Entry.objects.filter(nature="sale").count()), (100, 1))

    def test_lost_race_with_different_payload_is_a_conflict(self):
        self.go()
        patch, _ = self.blind_first_lookups()
        with patch:
            second = self.go(amount=101)
        self.assertEqual(second.code, "IDEMPOTENCY_CONFLICT")
        self.assertEqual((self.bal(self.b), Entry.objects.filter(nature="sale").count()), (100, 1))

    def test_losing_the_race_rolls_back_what_the_attempt_had_done_including_holds(self):
        h = ledger.hold(self.a.pk, 100, key="h", reference_kind="t", reference_id=1).detail["hold_id"]
        first = self.go(uses=[HoldUse(h, 40)])
        patch, _ = self.blind_first_lookups()
        with patch:
            second = self.go(uses=[HoldUse(h, 40)])
        self.assertTrue(second.ok and second.detail["already_posted"])
        self.assertEqual(second.detail["transaction_id"], first.detail["transaction_id"])
        self.assertEqual(Hold.objects.get(pk=h).amount, 60)           # consumido UMA vez

    def test_winner_check_after_locking_accounts_catches_the_race_before_writing(self):
        first = self.go()
        patch, calls = self.blind_first_lookups(n=1)                  # só a primeira checagem é cega
        with patch:
            second = self.go()
        self.assertEqual(calls["n"], 2)                                # a reconferência já achou o vencedor
        self.assertTrue(second.ok and second.detail["already_posted"])
        self.assertEqual(second.detail["transaction_id"], first.detail["transaction_id"])

    def test_same_contract_for_hold_obligation_and_remuneration_request(self):
        from ledger import obligations
        h1 = ledger.hold(self.a.pk, 10, key="hk", reference_kind="t", reference_id=1)
        o1 = obligations.open_obligation(self.a.pk, self.b.pk, 10, Nature.GOV_TRANSFER, key="ok", reference_kind="t",
                                         reference_id=1, competence_day=1)

        def blind(manager):
            real, calls = manager.filter, {"n": 0}

            def filt(*args, **kw):
                if "key" in kw and calls["n"] == 0:
                    calls["n"] += 1
                    return real(pk__in=[])
                return real(*args, **kw)
            return mock.patch.object(manager, "filter", side_effect=filt)
        with blind(Hold.objects):
            h2 = ledger.hold(self.a.pk, 10, key="hk", reference_kind="t", reference_id=1)
            h3 = ledger.hold(self.a.pk, 11, key="hk", reference_kind="t", reference_id=1)
        self.assertTrue(h2.ok and h2.detail["already_posted"] and h2.detail["hold_id"] == h1.detail["hold_id"])
        self.assertEqual(h3.code, "IDEMPOTENCY_CONFLICT")
        from ledger.models import Obligation
        with blind(Obligation.objects):
            o2 = obligations.open_obligation(self.a.pk, self.b.pk, 10, Nature.GOV_TRANSFER, key="ok", reference_kind="t",
                                             reference_id=1, competence_day=1)
        self.assertTrue(o2.ok and o2.detail["already_posted"] and o2.detail["obligation_id"] == o1.detail["obligation_id"])
        self.assertEqual(Hold.objects.filter(key="hk").count(), 1)


class CompetenceDayTests(LedgerTestCase):
    """O dia de competência EFETIVO entra no payload canônico, mas o reenvio de uma requisição sem dia continua idempotente."""

    def test_effective_day_is_stored_when_none_informed_and_entries_agree(self):
        from ledger.money import competence_day_of
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        res = ledger.transfer(a.pk, b.pk, 10, Nature.SALE, key="k", reference_kind="t", reference_id=1)
        tx = Transaction.objects.get(pk=res.detail["transaction_id"])
        self.assertIsNone(tx.payload["request"]["competence_day"])
        self.assertEqual(tx.payload["competence_day"], competence_day_of(self.clk.now()))
        self.assertEqual({e.competence_day for e in tx.entries.all()}, {tx.payload["competence_day"]})

    def test_replay_on_a_later_day_returns_the_original_and_keeps_its_day(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        first = ledger.transfer(a.pk, b.pk, 10, Nature.SALE, key="k", reference_kind="t", reference_id=1)
        day = Transaction.objects.get(pk=first.detail["transaction_id"]).payload["competence_day"]
        self.clk.advance(days=3)
        again = ledger.transfer(a.pk, b.pk, 10, Nature.SALE, key="k", reference_kind="t", reference_id=1)
        self.assertTrue(again.ok and again.detail["already_posted"])
        self.assertEqual(again.detail["transaction_id"], first.detail["transaction_id"])
        self.assertEqual(Entry.objects.get(pk=again.detail["seqs"][0]).competence_day, day)

    def test_explicit_day_is_part_of_the_request(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        leg = [Leg(a.pk, b.pk, 10, Nature.SALE)]
        r1 = post_transaction(leg, key="k", reference_kind="t", reference_id=1, competence_day=500)
        self.assertTrue(r1.ok)
        self.assertTrue(post_transaction(leg, key="k", reference_kind="t", reference_id=1, competence_day=500).detail["already_posted"])
        self.assertEqual(post_transaction(leg, key="k", reference_kind="t", reference_id=1, competence_day=501).code,
                         "IDEMPOTENCY_CONFLICT")
        self.assertEqual(post_transaction(leg, key="k", reference_kind="t", reference_id=1).code, "IDEMPOTENCY_CONFLICT")
        tx = Transaction.objects.get(key="k")
        self.assertEqual((tx.payload["request"]["competence_day"], tx.payload["competence_day"]), (500, 500))


class RouteTests(LedgerTestCase):
    def test_sink_only_receives(self):
        a = self.company(1)
        sink = ledger.sink_account()
        self.fund(a, 100)
        ok = ledger.transfer(a.pk, sink.pk, 40, Nature.CAMPAIGN_COST, key="c", reference_kind="t", reference_id=1)
        self.assertTrue(ok.ok)
        self.assertEqual(self.bal(sink), 40)
        self.assertEqual(ledger.transfer(sink.pk, a.pk, 1, Nature.SALE, key="c2", reference_kind="t", reference_id=1).code,
                         "SINK_NOT_SPENDABLE")
        self.assertEqual(ledger.transfer(a.pk, sink.pk, 1, Nature.SALE, key="c3", reference_kind="t", reference_id=1).code,
                         "NATURE_ACCOUNT_MISMATCH")
        self.assertEqual(ledger.transfer(a.pk, self.company(2).pk, 1, Nature.CAMPAIGN_COST, key="c4", reference_kind="t",
                                         reference_id=1).code, "NATURE_ACCOUNT_MISMATCH")
        emitted, circ, ret, snk = self.total_supply()
        self.assertEqual((emitted, circ, snk), (100, 60, 40))

    def test_issuance_only_by_scenario_grant(self):
        a = self.company(1)
        iss = ledger.issuance_account()
        for nature in (Nature.SALE, Nature.SUBSIDY, Nature.GOV_TRANSFER, Nature.REVERSAL):
            self.assertEqual(ledger.transfer(iss.pk, a.pk, 5, nature, key=f"i{nature.value}", reference_kind="t",
                                             reference_id=1).code, "ISSUANCE_NOT_ALLOWED")
        self.assertEqual(ledger.transfer(a.pk, iss.pk, 5, Nature.SALE, key="back", reference_kind="t", reference_id=1).code,
                         "ISSUANCE_NOT_ALLOWED")
        self.assertEqual(ledger.transfer(a.pk, self.company(2).pk, 5, Nature.SCENARIO_GRANT, key="g", reference_kind="t",
                                         reference_id=1).code, "ISSUANCE_NOT_ALLOWED")
        self.assertEqual(Entry.objects.count(), 0)

    def test_grant_to_non_operational_account_refused(self):
        ledger.create_scenario("g", {"x": 0})
        sink = ledger.sink_account()
        self.assertEqual(ledger.grant_scenario_allocation("g", sink.pk, 10).code, "NATURE_ACCOUNT_MISMATCH")
        ret = ledger.open_retention("test", "c:1")
        self.assertEqual(ledger.grant_scenario_allocation("g", ret.pk, 10).code, "NATURE_ACCOUNT_MISMATCH")


class ImmutabilityAndReversalTests(LedgerTestCase):
    def test_entries_cannot_be_changed_or_deleted(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        self.pay(a, b, 10)
        e = Entry.objects.filter(nature="sale").first()
        e.amount = 99
        with self.assertRaises(LedgerImmutableError):
            e.save()
        with self.assertRaises(LedgerImmutableError):
            e.delete()
        with self.assertRaises(LedgerImmutableError):
            Entry.objects.all().update(amount=1)
        with self.assertRaises(LedgerImmutableError):
            Entry.objects.all().delete()
        tx = Transaction.objects.first()
        with self.assertRaises(LedgerImmutableError):
            tx.delete()
        tx.actor = "x"
        with self.assertRaises(LedgerImmutableError):
            tx.save()

    def test_transaction_cannot_be_changed_in_bulk_through_the_orm(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        self.pay(a, b, 10)
        before = list(Transaction.objects.values_list("pk", "key", "payload_hash", "actor", "at"))
        with self.assertRaises(LedgerImmutableError):
            Transaction.objects.all().update(actor="x")
        with self.assertRaises(LedgerImmutableError):
            Transaction.objects.filter(pk__gt=0).update(payload_hash="0" * 64)
        txs = list(Transaction.objects.all())
        for t in txs:
            t.actor = "tampered"
        with self.assertRaises(LedgerImmutableError):
            Transaction.objects.bulk_update(txs, ["actor"])
        with self.assertRaises(LedgerImmutableError):
            Transaction.objects.update_or_create(key=txs[0].key, defaults={"actor": "x"})
        with self.assertRaises(LedgerImmutableError):
            Transaction.objects.all().delete()
        with self.assertRaises(LedgerImmutableError):
            Transaction.objects.all()._raw_delete(Transaction.objects.db)
        with self.assertRaises(LedgerImmutableError):
            Transaction.objects.bulk_create([Transaction(key=txs[0].key, payload_hash="x", at=1)], update_conflicts=True,
                                            update_fields=["actor"], unique_fields=["key"])
        self.assertEqual(list(Transaction.objects.values_list("pk", "key", "payload_hash", "actor", "at")), before)

    def test_entry_cannot_be_changed_in_bulk_through_the_orm(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        self.pay(a, b, 10)
        before = list(Entry.objects.values_list("seq", "amount", "nature", "from_account", "to_account"))
        entries = list(Entry.objects.all())
        for e in entries:
            e.amount = 1
        with self.assertRaises(LedgerImmutableError):
            Entry.objects.bulk_update(entries, ["amount"])
        with self.assertRaises(LedgerImmutableError):
            Entry.objects.update_or_create(seq=entries[0].seq, defaults={"amount": 1})
        with self.assertRaises(LedgerImmutableError):
            Entry.objects.all()._raw_delete(Entry.objects.db)
        with self.assertRaises(LedgerImmutableError):
            Entry.objects.bulk_create(entries[:1], update_conflicts=True, update_fields=["amount"], unique_fields=["seq"])
        self.assertEqual(list(Entry.objects.values_list("seq", "amount", "nature", "from_account", "to_account")), before)

    def test_reversal_mirrors_and_points_to_original(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        seq = self.pay(a, b, 40).detail["seqs"][0]
        res = ledger.reverse(seq, "erro de lançamento", key="rev1")
        self.assertTrue(res.ok, res)
        self.assertEqual((self.bal(a), self.bal(b)), (100, 0))
        rev = Entry.objects.get(pk=res.detail["seqs"][0])
        self.assertEqual((rev.reverses_id, rev.nature, rev.from_account_id, rev.to_account_id), (seq, "reversal", b.pk, a.pk))
        self.assertTrue(Entry.objects.filter(pk=seq).exists())             # o original permanece
        self.assertEqual(ledger.reverse(seq, "de novo", key="rev2").code, "REVERSAL_NOT_POSSIBLE")
        self.assertEqual(ledger.reverse(seq, "", key="rev3").code, "REASON_REQUIRED")
        self.assertEqual(ledger.reverse(999999, "x", key="rev4").code, "ENTRY_NOT_FOUND")

    def test_reversal_refused_when_it_would_overdraw(self):
        a, b, c = self.company(1), self.company(2), self.company(3)
        self.fund(a, 100)
        seq = self.pay(a, b, 100).detail["seqs"][0]
        self.pay(b, c, 100)
        res = ledger.reverse(seq, "tarde demais", key="rev")
        self.assertEqual((res.code, res.detail["why"]), ("REVERSAL_NOT_POSSIBLE", "insufficient_funds"))

    def test_reversal_never_of_grant_sink_or_remuneration(self):
        a = self.company(1)
        grant_seq = self.fund(a, 100).detail["seqs"][0]
        self.assertEqual(ledger.reverse(grant_seq, "x", key="r1").code, "REVERSAL_NOT_POSSIBLE")
        seq = ledger.transfer(a.pk, ledger.sink_account().pk, 10, Nature.CAMPAIGN_COST, key="s", reference_kind="t",
                              reference_id=1).detail["seqs"][0]
        self.assertEqual(ledger.reverse(seq, "x", key="r2").code, "REVERSAL_NOT_POSSIBLE")
        self.assertEqual(self.bal(ledger.sink_account()), 10)


class TransactionInstanceImmutabilityTests(LedgerTestCase):
    audit_at_end = False          # o teste cria de propósito uma transação sem lançamentos (a auditoria a apontaria)

    def test_new_instances_can_be_created_but_saved_ones_cannot_be_saved_again(self):
        t = Transaction.objects.create(key="manual", payload_hash="x", at=1)
        with self.assertRaises(LedgerImmutableError):
            t.save()
        with self.assertRaises(LedgerImmutableError):
            t.save(update_fields=["actor"])


class RandomSequenceConservationTests(LedgerTestCase):
    """Teste de propriedade: sequências aleatórias de operações nunca criam nem destroem dinheiro além do documentado."""

    def test_random_operations_preserve_invariants(self):
        rng = random.Random(7)
        accounts = [self.company(i) for i in range(1, 7)]
        for a in accounts[:3]:
            self.fund(a, rng.randint(1, 10_000))
        retention = ledger.open_retention("test", "rand:1")
        sink = ledger.sink_account()
        union = ledger.union_account()
        pool = accounts + [union]
        holds = []
        for step in range(400):
            op = rng.choice(["pay", "pay", "pay", "taxed", "retain", "release", "sink", "hold", "release_hold", "reverse"])
            a, b = rng.sample(pool, 2)
            amount = rng.randint(1, 3000)
            if op == "pay":
                ledger.transfer(a.pk, b.pk, amount, Nature.SALE, key=f"r{step}", reference_kind="rand", reference_id=step)
            elif op == "taxed":
                ledger.post_taxed_payment(a.pk, b.pk, amount, nature=Nature.SALE, tax_rate=Decimal("0.0725"), key=f"r{step}",
                                          reference_kind="rand", reference_id=step)
            elif op == "retain":
                ledger.retain(a.pk, retention.pk, amount, key=f"r{step}", reference_kind="rand", reference_id=step)
            elif op == "release":
                ledger.release_retention(retention.pk, b.pk, key=f"r{step}", reference_kind="rand", reference_id=step,
                                         amount=amount)
            elif op == "sink":
                ledger.transfer(a.pk, sink.pk, amount, Nature.CAMPAIGN_COST, key=f"r{step}", reference_kind="rand", reference_id=step)
            elif op == "hold":
                r = ledger.hold(a.pk, amount, key=f"r{step}", reference_kind="rand", reference_id=step)
                if r.ok:
                    holds.append(r.detail["hold_id"])
            elif op == "release_hold" and holds:
                ledger.release_hold(holds.pop(rng.randrange(len(holds))))
            elif op == "reverse":
                last = Entry.objects.filter(nature__in=["sale"]).order_by("-seq").first()
                if last:
                    ledger.reverse(last.pk, "rand", key=f"r{step}")
            self.assertEqual(sum(x.balance for x in Account.objects.all()), 0, f"passo {step} {op}")
            emitted, circ, ret, snk = self.total_supply()
            self.assertEqual(emitted, circ + ret + snk, f"passo {step} {op}")
            self.assertFalse(Account.objects.filter(balance__lt=0).exclude(kind="issuance").exists())
        self.assertTrue(audit_ledger().ok, audit_ledger().findings)
        self.assertGreater(Entry.objects.count(), 50)
