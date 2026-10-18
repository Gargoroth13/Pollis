from decimal import Decimal

from ledger import obligations, services as ledger
from ledger.constants import Nature
from ledger.models import Entry, Obligation

from .base import LedgerTestCase


class ObligationTests(LedgerTestCase):
    def setUp(self):
        super().setUp()
        self.payer, self.p1, self.p2 = self.company(1), self.company(2), self.company(3)

    def open(self, creditor, amount, day, key, **kw):
        return obligations.open_obligation(self.payer.pk, creditor.pk, amount, Nature.GOV_TRANSFER, key=key,
                                           reference_kind="t", reference_id=key, competence_day=day, **kw)

    def test_open_is_not_money(self):
        self.fund(self.payer, 100)
        self.assertTrue(self.open(self.p1, 500, 10, "o1").ok)
        emitted, circ, _, _ = self.total_supply()
        self.assertEqual((emitted, circ), (100, 100))                         # nada circulou
        self.assertEqual(ledger.pending_total(self.payer.pk), 500)
        self.assertEqual(self.bal(self.payer), 100)

    def test_idempotent_open_and_conflict(self):
        a = self.open(self.p1, 500, 10, "o1")
        b = self.open(self.p1, 500, 10, "o1")
        self.assertEqual(a.detail["obligation_id"], b.detail["obligation_id"])
        self.assertTrue(b.detail["already_posted"])
        self.assertEqual(self.open(self.p1, 501, 10, "o1").code, "IDEMPOTENCY_CONFLICT")
        self.assertEqual(Obligation.objects.count(), 1)

    def test_same_key_with_different_tax_rate_or_territory_conflicts(self):
        base = dict(key="t", reference_kind="t", reference_id=1, competence_day=5)
        first = obligations.open_obligation(self.payer.pk, self.p1.pk, 500, Nature.GOV_TRANSFER, tax_rate=Decimal("0.1"),
                                            tax_territory="city:3", **base)
        self.assertTrue(first.ok)
        again = obligations.open_obligation(self.payer.pk, self.p1.pk, 500, Nature.GOV_TRANSFER, tax_rate=Decimal("0.1"),
                                            tax_territory="city:3", **base)
        self.assertTrue(again.ok and again.detail["already_posted"])
        self.assertEqual(again.detail["obligation_id"], first.detail["obligation_id"])
        # mesma alíquota escrita de outro jeito é a MESMA alíquota
        for same in (Decimal("0.10"), "0.1", Decimal("0.100000")):
            r = obligations.open_obligation(self.payer.pk, self.p1.pk, 500, Nature.GOV_TRANSFER, tax_rate=same,
                                            tax_territory="city:3", **base)
            self.assertTrue(r.ok and r.detail["already_posted"], same)
        other_rate = obligations.open_obligation(self.payer.pk, self.p1.pk, 500, Nature.GOV_TRANSFER, tax_rate=Decimal("0.2"),
                                                 tax_territory="city:3", **base)
        self.assertEqual(other_rate.code, "IDEMPOTENCY_CONFLICT")
        other_territory = obligations.open_obligation(self.payer.pk, self.p1.pk, 500, Nature.GOV_TRANSFER,
                                                      tax_rate=Decimal("0.1"), tax_territory="city:4", **base)
        self.assertEqual(other_territory.code, "IDEMPOTENCY_CONFLICT")
        no_territory = obligations.open_obligation(self.payer.pk, self.p1.pk, 500, Nature.GOV_TRANSFER,
                                                   tax_rate=Decimal("0.1"), tax_territory="", **base)
        self.assertEqual(no_territory.code, "IDEMPOTENCY_CONFLICT")
        no_tax = obligations.open_obligation(self.payer.pk, self.p1.pk, 500, Nature.GOV_TRANSFER, **base)
        self.assertEqual(no_tax.code, "IDEMPOTENCY_CONFLICT")
        ob = Obligation.objects.get()
        self.assertEqual((ob.tax_rate, ob.tax_territory), (Decimal("0.1"), "city:3"))      # a original não mudou

    def test_stored_tax_fields_must_be_exact_and_well_formed(self):
        base = dict(key="t", reference_kind="t", reference_id=1)
        for rate in (Decimal("0.1234567"), "abc", 0.1, True, None, Decimal("NaN"), Decimal("-0.1"), 2):
            res = obligations.open_obligation(self.payer.pk, self.p1.pk, 5, Nature.GOV_TRANSFER, tax_rate=rate, **base)
            self.assertEqual(res.code, "TAX_RATE_INVALID", rate)
        for territory in ("city", "city:", ":3", "city:x", "ci ty:3", 7):
            res = obligations.open_obligation(self.payer.pk, self.p1.pk, 5, Nature.GOV_TRANSFER, tax_territory=territory, **base)
            self.assertEqual(res.code, "TAX_TERRITORY_INVALID", territory)
        self.assertEqual(Obligation.objects.count(), 0)

    def test_open_validation(self):
        self.assertEqual(self.open(self.p1, 0, 10, "o").code, "AMOUNT_NOT_POSITIVE")
        self.assertEqual(self.open(self.p1, 1.5, 10, "o").code, "AMOUNT_NOT_IN_CENTAVOS")
        self.assertEqual(obligations.open_obligation(self.payer.pk, self.payer.pk, 5, Nature.GOV_TRANSFER, key="o",
                                                     reference_kind="t", reference_id=1).code, "SAME_ACCOUNT")
        self.assertEqual(obligations.open_obligation(self.payer.pk, ledger.sink_account().pk, 5, Nature.GOV_TRANSFER, key="o",
                                                     reference_kind="t", reference_id=1).code, "NATURE_ACCOUNT_MISMATCH")
        self.assertEqual(obligations.open_obligation(self.payer.pk, self.p1.pk, 5, Nature.GOV_TRANSFER, key="o",
                                                     reference_kind="", reference_id=1).code, "REFERENCE_REQUIRED")
        self.assertEqual(self.open(self.p1, 5, 10, "o", tax_rate=Decimal("2")).code, "TAX_RATE_INVALID")

    def test_settle_order_oldest_competence_then_id_partial_allowed(self):
        # criadas fora de ordem: a competência manda, depois o id
        self.open(self.p2, 300, 12, "late")
        self.open(self.p1, 200, 10, "old-b")
        self.open(self.p2, 100, 10, "old-a")
        self.fund(self.payer, 350)
        res = obligations.settle_obligations(self.payer.pk, batch_key="b1")
        self.assertTrue(res.ok)
        paid = {r["obligation"]: r["gross"] for r in res.detail["paid"]}
        ids = {o.key: o.pk for o in Obligation.objects.all()}
        self.assertEqual(paid[ids["old-b"]], 200)            # id menor entre os de competência 10 (criado antes de old-a)
        self.assertEqual(paid[ids["old-a"]], 100)
        self.assertEqual(paid.get(ids["late"]), 50)           # o resto vai parcialmente à mais recente
        self.assertEqual(self.bal(self.payer), 0)
        late = Obligation.objects.get(key="late")
        self.assertEqual((late.amount_paid, late.status), (50, "open"))
        self.assertEqual(ledger.pending_total(self.payer.pk), 250)

    def test_settling_never_creates_money_and_resumes_later(self):
        self.open(self.p1, 1000, 1, "o")
        self.fund(self.payer, 400)
        obligations.settle_obligations(self.payer.pk, batch_key="b1")
        self.assertEqual((self.bal(self.p1), self.bal(self.payer)), (400, 0))
        self.assertEqual(obligations.settle_obligations(self.payer.pk, batch_key="b2").detail["paid"], [])
        self.fund(self.payer, 600)
        obligations.settle_obligations(self.payer.pk, batch_key="b3")
        self.assertEqual(self.bal(self.p1), 1000)
        self.assertEqual(Obligation.objects.get().status, "paid")
        emitted, circ, _, _ = self.total_supply()
        self.assertEqual((emitted, circ), (1000, 1000))

    def test_settle_is_idempotent_per_batch(self):
        self.open(self.p1, 100, 1, "o")
        self.fund(self.payer, 1000)
        obligations.settle_obligations(self.payer.pk, batch_key="same")
        again = obligations.settle_obligations(self.payer.pk, batch_key="same")
        self.assertEqual(again.detail["paid"], [])
        self.assertEqual(self.bal(self.p1), 100)

    def test_reserved_funds_are_not_used_to_settle(self):
        self.open(self.p1, 100, 1, "o")
        self.fund(self.payer, 100)
        ledger.hold(self.payer.pk, 70, key="h", reference_kind="c", reference_id=1)
        obligations.settle_obligations(self.payer.pk, batch_key="b")
        self.assertEqual(self.bal(self.p1), 30)

    def test_settle_unknown_debtor_and_key_required(self):
        self.assertEqual(obligations.settle_obligations(99999, batch_key="b").code, "ACCOUNT_NOT_FOUND")
        self.assertEqual(obligations.settle_obligations(self.payer.pk, batch_key="").code, "KEY_REQUIRED")

    def test_cancel_records_reason_and_remaining(self):
        o = self.open(self.p1, 100, 1, "o").detail["obligation_id"]
        self.assertEqual(obligations.cancel_obligation(o, "").code, "REASON_REQUIRED")
        res = obligations.cancel_obligation(o, "regra do sistema de origem")
        self.assertEqual(res.detail["cancelled_remaining"], 100)
        ob = Obligation.objects.get(pk=o)
        self.assertEqual((ob.status, ob.cancel_reason), ("cancelled", "regra do sistema de origem"))
        self.assertEqual(obligations.cancel_obligation(o, "x").code, "OBLIGATION_NOT_OPEN")
        self.assertEqual(obligations.cancel_obligation(99999, "x").code, "OBLIGATION_NOT_FOUND")
        self.fund(self.payer, 100)
        obligations.settle_obligations(self.payer.pk, batch_key="b")
        self.assertEqual(self.bal(self.p1), 0)                       # cancelada não é paga

    def test_partial_settlement_with_tax_closes_exact_total(self):
        income_payer = self.payer
        o = obligations.open_obligation(income_payer.pk, self.p1.pk, 1001, Nature.GOV_TRANSFER, key="t", reference_kind="t",
                                        reference_id=1, competence_day=5, tax_rate=Decimal("0.1"))
        self.assertTrue(o.ok)
        for n, amount in enumerate((333, 333, 700), 1):
            self.fund(income_payer, amount)
            obligations.settle_obligations(income_payer.pk, batch_key=f"b{n}")
        ob = Obligation.objects.get()
        self.assertEqual((ob.status, ob.amount_paid), ("paid", 1001))
        self.assertEqual(ob.tax_paid, 100)                           # round(1001 × 0,1) uma vez; parcelas fecham o resto
        self.assertEqual(self.bal(self.p1), 1001 - 100)
        self.assertEqual(self.bal(ledger.union_account()), 100)
        self.assertEqual(sum(e.amount for e in Entry.objects.filter(nature="tax_income")), 100)

    def test_union_debtor_with_self_compensated_tax(self):
        union = ledger.union_account()
        obligations.open_obligation(union.pk, self.p1.pk, 1000, Nature.GOV_TRANSFER, key="u", reference_kind="t",
                                    reference_id=1, competence_day=1, tax_rate=Decimal("0.1"))
        self.fund(union, 900)           # basta o líquido: o imposto à própria União não sai do caixa
        res = obligations.settle_obligations(union.pk, batch_key="b")
        self.assertEqual(res.detail["total_gross"], 1000)
        self.assertEqual((self.bal(self.p1), self.bal(union)), (900, 0))
        self.assertFalse(Entry.objects.filter(from_account=union, to_account=union).exists())

    def test_pending_summary_for_budget(self):
        self.open(self.p1, 100, 1, "o")
        s = obligations.pending_summary(self.payer.pk)
        self.assertEqual((s["total"], len(s["obligations"])), (100, 1))
