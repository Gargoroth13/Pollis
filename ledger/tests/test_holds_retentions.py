from ledger import services as ledger
from ledger.constants import Nature
from ledger.models import Hold
from ledger.services import HoldUse

from .base import LedgerTestCase


class HoldTests(LedgerTestCase):
    def test_hold_reduces_available_not_gross(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 1000)
        h = ledger.hold(a.pk, 400, key="h1", reference_kind="contract", reference_id=1)
        self.assertTrue(h.ok)
        self.assertEqual((ledger.balance_of(a.pk), ledger.reserved_of(a.pk), ledger.available_of(a.pk)), (1000, 400, 600))
        self.assertEqual(self.pay(a, b, 700).code, "INSUFFICIENT_FUNDS")
        self.assertTrue(self.pay(a, b, 600).ok)
        emitted, circ, ret, sink = self.total_supply()
        self.assertEqual(emitted, circ + ret + sink)                    # reservas não entram na fórmula

    def test_hold_cannot_exceed_available_and_is_idempotent(self):
        a = self.company(1)
        self.fund(a, 100)
        self.assertEqual(ledger.hold(a.pk, 101, key="h", reference_kind="c", reference_id=1).code, "INSUFFICIENT_AVAILABLE")
        r1 = ledger.hold(a.pk, 60, key="h", reference_kind="c", reference_id=1)
        r2 = ledger.hold(a.pk, 60, key="h", reference_kind="c", reference_id=1)
        self.assertEqual(r1.detail["hold_id"], r2.detail["hold_id"])
        self.assertTrue(r2.detail["already_posted"])
        self.assertEqual(ledger.hold(a.pk, 61, key="h", reference_kind="c", reference_id=1).code, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(ledger.reserved_of(a.pk), 60)
        self.assertEqual(ledger.hold(a.pk, 41, key="h2", reference_kind="c", reference_id=2).code, "INSUFFICIENT_AVAILABLE")

    def test_hold_validation(self):
        a = self.company(1)
        self.fund(a, 100)
        self.assertEqual(ledger.hold(a.pk, 0, key="h", reference_kind="c", reference_id=1).code, "AMOUNT_NOT_POSITIVE")
        self.assertEqual(ledger.hold(99999, 5, key="h", reference_kind="c", reference_id=1).code, "ACCOUNT_NOT_FOUND")
        self.assertEqual(ledger.hold(ledger.sink_account().pk, 5, key="h", reference_kind="c", reference_id=1).code, "SINK_NOT_SPENDABLE")
        self.assertEqual(ledger.hold(a.pk, 5, key="h", reference_kind="", reference_id=1).code, "REFERENCE_REQUIRED")

    def test_release_is_idempotent_and_frees_funds(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        h = ledger.hold(a.pk, 100, key="h", reference_kind="c", reference_id=1).detail["hold_id"]
        self.assertEqual(self.pay(a, b, 1).code, "INSUFFICIENT_FUNDS")
        self.assertEqual(ledger.release_hold(h).detail["released"], 100)
        self.assertEqual(ledger.release_hold(h).detail["released"], 0)
        self.assertTrue(self.pay(a, b, 100).ok)
        self.assertEqual(ledger.release_hold(99999).code, "HOLD_NOT_FOUND")

    def test_consuming_hold_pays_the_reserved_amount(self):
        union, supplier = ledger.union_account(), self.company(2)
        self.fund(union, 1000)
        h = ledger.hold(union.pk, 600, key="h", reference_kind="contract", reference_id=1).detail["hold_id"]
        # entrega 1 consome 250 da reserva (fluxo B do 19): sem a reserva o disponível (400) não cobriria 650
        res = ledger.transfer(union.pk, supplier.pk, 250, Nature.PUBLIC_WORKS_PAYMENT, key="d1", reference_kind="delivery",
                              reference_id=1, uses=[HoldUse(h, 250)])
        self.assertTrue(res.ok, res)
        hold = Hold.objects.get(pk=h)
        self.assertEqual((hold.amount, hold.status), (350, "active"))
        self.assertEqual(ledger.available_of(union.pk), 400)
        res = ledger.transfer(union.pk, supplier.pk, 350, Nature.PUBLIC_WORKS_PAYMENT, key="d2", reference_kind="delivery",
                              reference_id=2, uses=[HoldUse(h, 350)])
        self.assertTrue(res.ok)
        self.assertEqual(Hold.objects.get(pk=h).status, "consumed")
        self.assertEqual((self.bal(union), self.bal(supplier)), (400, 600))

    def test_consuming_more_than_hold_or_wrong_account_refused_atomically(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        self.fund(b, 100)
        h = ledger.hold(a.pk, 50, key="h", reference_kind="c", reference_id=1).detail["hold_id"]
        res = ledger.transfer(a.pk, b.pk, 60, Nature.SALE, key="x", reference_kind="d", reference_id=1, uses=[HoldUse(h, 60)])
        self.assertEqual(res.code, "HOLD_INSUFFICIENT")
        res = ledger.transfer(b.pk, a.pk, 10, Nature.SALE, key="y", reference_kind="d", reference_id=1, uses=[HoldUse(h, 10)])
        self.assertEqual(res.code, "HOLD_ACCOUNT_MISMATCH")
        self.assertEqual(Hold.objects.get(pk=h).amount, 50)          # nada consumido nas recusas
        self.assertEqual(ledger.balance_of(a.pk), 100)

    def test_consumed_hold_cannot_be_reused_and_replay_is_idempotent(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        h = ledger.hold(a.pk, 50, key="h", reference_kind="c", reference_id=1).detail["hold_id"]

        def go(key="d"):
            return ledger.transfer(a.pk, b.pk, 50, Nature.SALE, key=key, reference_kind="d", reference_id=1, uses=[HoldUse(h, 50)])
        self.assertTrue(go().ok)
        self.assertTrue(go().detail["already_posted"])               # replay não consome de novo
        self.assertEqual(go("d2").code, "HOLD_NOT_FOUND")
        self.assertEqual(self.bal(b), 50)


class RetentionTests(LedgerTestCase):
    def test_retention_value_is_never_on_both_sides(self):
        bank, supplier, union = self.company(1), self.company(2), ledger.union_account()
        self.fund(bank, 1000)
        ret = ledger.open_retention("special_requisition", "contract:7")
        self.assertEqual(ledger.open_retention("special_requisition", "contract:7").pk, ret.pk)
        r = ledger.retain(bank.pk, ret.pk, 1000, key="c7", reference_kind="contract", reference_id=7)
        self.assertTrue(r.ok)
        self.assertEqual((self.bal(bank), self.bal(ret), self.bal(supplier)), (0, 1000, 0))
        emitted, circ, retained, sink = self.total_supply()
        self.assertEqual((emitted, circ, retained), (1000, 0, 1000))
        # liberação ao destino ESCOLHIDO por quem chama (líquido ao fornecedor, imposto à União)
        self.assertTrue(ledger.release_retention(ret.pk, supplier.pk, amount=900, key="rel1", reference_kind="contract", reference_id=7).ok)
        self.assertTrue(ledger.release_retention(ret.pk, union.pk, key="rel2", reference_kind="contract", reference_id=7).ok)
        self.assertEqual((self.bal(ret), self.bal(supplier), self.bal(union)), (0, 900, 100))
        self.assertEqual(ledger.release_retention(ret.pk, supplier.pk, key="rel3", reference_kind="contract", reference_id=7).code,
                         "RETENTION_EMPTY")

    def test_refund_on_failure(self):
        bank = self.company(1)
        self.fund(bank, 300)
        ret = ledger.open_retention("special_requisition", "contract:8")
        ledger.retain(bank.pk, ret.pk, 300, key="c8", reference_kind="contract", reference_id=8)
        r = ledger.release_retention(ret.pk, bank.pk, refund=True, key="ref", reference_kind="contract", reference_id=8)
        self.assertTrue(r.ok)
        self.assertEqual(self.bal(bank), 300)

    def test_retain_without_funds_refused(self):
        bank = self.company(1)
        self.fund(bank, 10)
        ret = ledger.open_retention("x", "c:1")
        res = ledger.retain(bank.pk, ret.pk, 11, key="k", reference_kind="c", reference_id=1)
        self.assertEqual(res.code, "INSUFFICIENT_FUNDS")
        self.assertEqual(self.bal(ret), 0)

    def test_destination_missing_or_closed_refused(self):
        bank, other = self.company(1), self.company(2)
        self.fund(bank, 100)
        ret = ledger.open_retention("x", "c:2")
        ledger.retain(bank.pk, ret.pk, 100, key="k", reference_kind="c", reference_id=2)
        self.assertEqual(ledger.release_retention(ret.pk, 99999, key="r", reference_kind="c", reference_id=2).code, "ACCOUNT_NOT_FOUND")
        ledger.close_account(other.pk)
        self.assertEqual(ledger.release_retention(ret.pk, other.pk, key="r2", reference_kind="c", reference_id=2).code, "ACCOUNT_CLOSED")
        self.assertEqual(self.bal(ret), 100)

    def test_retention_cannot_be_used_as_normal_account(self):
        bank = self.company(1)
        self.fund(bank, 100)
        ret = ledger.open_retention("x", "c:3")
        self.assertEqual(ledger.transfer(bank.pk, ret.pk, 10, Nature.SALE, key="k", reference_kind="c", reference_id=1).code,
                         "NATURE_ACCOUNT_MISMATCH")
        ledger.retain(bank.pk, ret.pk, 10, key="k2", reference_kind="c", reference_id=1)
        self.assertEqual(ledger.transfer(ret.pk, bank.pk, 10, Nature.SALE, key="k3", reference_kind="c", reference_id=1).code,
                         "NATURE_ACCOUNT_MISMATCH")

    def test_retention_account_closes_only_when_empty(self):
        bank = self.company(1)
        self.fund(bank, 10)
        ret = ledger.open_retention("x", "c:4")
        ledger.retain(bank.pk, ret.pk, 10, key="k", reference_kind="c", reference_id=1)
        self.assertEqual(ledger.close_account(ret.pk).code, "ACCOUNT_NOT_EMPTY")
        ledger.release_retention(ret.pk, bank.pk, refund=True, key="r", reference_kind="c", reference_id=1)
        self.assertTrue(ledger.close_account(ret.pk).ok)
