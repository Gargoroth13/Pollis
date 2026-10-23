"""Histórico de transações (design/17 §17.2, §17.18): só nasce depois de o dinheiro ter se movido; imutável; idempotente."""
from django.db import IntegrityError, transaction

from ledger import services as ledger
from ledger.audit import ledger_metrics
from ledger.constants import Nature
from market import recording
from market.audit import audit_market
from market.models import MarketImmutableError, MarketTransaction

from .base import MarketBase


class RecordingTests(MarketBase):
    def call(self, key, **over):
        args = dict(product_key="flour", quantity=10, unit_price_cents=1_000, buyer_kind="player", buyer_id=self.third.pk,
                    seller_kind="company", seller_id=self.firm, channel="inter_company", ledger_key=key)
        args.update(over)
        return recording.record_sale(**args)

    def test_a_completed_sale_is_recorded_with_its_real_payment_and_moves_no_money(self):
        money = ledger_metrics()["in_circulation"]
        res = self.sell("flour", 10, 1_000, day=0)
        tx = MarketTransaction.objects.get()
        self.assertEqual((tx.product.key, tx.quantity, tx.unit_price_cents, tx.total_cents, tx.channel, tx.buyer_kind, tx.seller_kind),
                         ("flour", 10, 1_000, 10_000, "inter_company", "player", "company"))
        self.assertEqual((tx.at, tx.competence_day), (self.at(0), self.day0))
        self.assertEqual(res.detail["total_cents"], 10_000)
        self.assertEqual(ledger_metrics()["in_circulation"], money)            # registrar não cria nem move dinheiro
        self.assertTrue(audit_market().ok)

    def test_recording_is_idempotent_by_the_payment_key_and_a_different_content_is_a_conflict(self):
        key = self.pay(10, 1_000, ("player", self.third.pk), ("company", self.firm))
        self.assertTrue(self.call(key).ok)
        again = self.call(key)
        self.assertTrue(again.ok)
        self.assertTrue(again.detail["already_applied"])
        self.assertEqual(MarketTransaction.objects.count(), 1)
        for over in ({"quantity": 5}, {"unit_price_cents": 999}, {"channel": "retail"}, {"product_key": "wheat"}):
            self.assertRefused(self.call(key, **over), "IDEMPOTENCY_CONFLICT")
        self.assertEqual(MarketTransaction.objects.count(), 1)

    def test_a_sale_without_the_real_payment_is_never_recorded(self):
        self.assertRefused(self.call("nope"), "PAYMENT_NOT_FOUND")
        self.assertRefused(self.call(""), "PAYMENT_NOT_FOUND")
        self.assertRefused(self.call(None), "PAYMENT_NOT_FOUND")
        key = self.pay(10, 1_000, ("player", self.third.pk), ("company", self.firm))
        self.assertRefused(self.call(key, quantity=11), "PAYMENT_NOT_FOUND")                      # valor total diferente
        self.assertRefused(self.call(key, buyer_kind="company", buyer_id=self.firm, seller_kind="player",
                                     seller_id=self.third.pk), "PAYMENT_NOT_FOUND")             # sentido contrário
        self.assertRefused(self.call(key, buyer_id=self.other.pk), "PAYMENT_NOT_FOUND")         # outro comprador
        # um lançamento de outra natureza não é venda
        other = ledger.transfer(self.account(("player", self.third.pk)), self.account(("company", self.firm)), 10_000, Nature.DONATION,
                                key="donation:1", reference_kind="test", reference_id="1")
        self.assertTrue(other.ok)
        self.assertRefused(self.call("donation:1"), "PAYMENT_NOT_FOUND")
        self.assertEqual(MarketTransaction.objects.count(), 0)

    def test_invalid_input_is_refused_with_a_code_and_nothing_is_stored(self):
        key = self.pay(10, 1_000, ("player", self.third.pk), ("company", self.firm))
        self.assertRefused(self.call(key, product_key="nothing"), "UNKNOWN_PRODUCT")
        self.assertRefused(self.call(key, product_key=7), "UNKNOWN_PRODUCT")
        for bad in (0, -1, 1.5, True, "10", None, 10 ** 9 + 1):
            self.assertRefused(self.call(key, quantity=bad), "INVALID_QUANTITY")
        for bad in (0, -5, 10.0, True, "1000", None, 10 ** 12 + 1):
            self.assertRefused(self.call(key, unit_price_cents=bad), "INVALID_PRICE")
        self.assertRefused(self.call(key, channel="black_market"), "INVALID_CHANNEL")
        self.assertRefused(self.call(key, buyer_kind="state"), "INVALID_PARTY")
        for bad in (0, -1, "1", None, True):
            self.assertRefused(self.call(key, buyer_id=bad), "INVALID_PARTY")
        self.assertRefused(self.call(key, buyer_kind="company", buyer_id=self.firm), "INVALID_PARTIES")
        self.assertRefused(self.call(key, seller_id=10 ** 9), "PARTY_NOT_FOUND")
        self.assertEqual(MarketTransaction.objects.count(), 0)

    def test_the_history_is_immutable_and_arithmetic_is_enforced_by_the_database(self):
        self.sell("flour", 10, 1_000, day=0)
        tx = MarketTransaction.objects.get()
        tx.quantity = 99
        with self.assertRaises(MarketImmutableError):
            tx.save()
        with self.assertRaises(MarketImmutableError):
            tx.delete()
        for bad in ({"quantity": 3}, {"unit_price_cents": 1}, {"quantity": 0, "total_cents": 0}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                MarketTransaction.objects.filter(pk=tx.pk).update(**bad)

    def test_every_channel_and_party_combination_of_the_systems_that_sell_is_accepted(self):
        for channel in ("retail", "inter_company", "player_market", "contract"):
            self.sell("flour", 1, 500, channel=channel, day=0)
        self.sell("flour", 1, 500, buyer=("company", self.firm), seller=("player", self.third.pk), day=0)
        self.assertEqual(MarketTransaction.objects.count(), 5)

    audit_market_at_end = False

    def test_a_reversed_payment_cannot_be_recorded_and_one_reversed_after_recording_is_flagged_by_the_audit(self):
        key = self.pay(2, 1_000, ("player", self.third.pk), ("company", self.firm))
        from ledger.models import Entry
        entry = Entry.objects.get(transaction__key=key, nature="sale")
        self.assertTrue(self.call(key, quantity=2).ok)
        self.assertTrue(audit_market().ok)
        res = ledger.reverse(entry.pk, "teste", key="rev:1")
        self.assertTrue(res.ok, res)
        self.assertEqual({f["code"] for f in audit_market().findings}, {"SALE_PAYMENT_REVERSED"})
        key2 = self.pay(1, 1_000, ("player", self.third.pk), ("company", self.firm))
        self.assertTrue(ledger.reverse(Entry.objects.get(transaction__key=key2, nature="sale").pk, "teste", key="rev:2").ok)
        self.assertRefused(self.call(key2, quantity=1), "PAYMENT_NOT_FOUND")                 # estornado: não é venda concluída


class TaxedPaymentTests(MarketBase):
    """Pagamento tributado (`ledger.post_taxed_payment`): SALE líquida ao vendedor + TAX_SALES pago pelo comprador somam o total."""

    def taxed(self, qty, price, key, rate="0.05"):
        from decimal import Decimal
        res = ledger.post_taxed_payment(self.account(("player", self.third.pk)), self.account(("company", self.firm)), qty * price,
                                        nature=Nature.SALE, tax_rate=Decimal(rate), key=key, reference_kind="test", reference_id=key)
        self.assertTrue(res.ok, res)
        return res

    def call(self, key, **over):
        args = dict(product_key="flour", quantity=10, unit_price_cents=1_000, buyer_kind="player", buyer_id=self.third.pk,
                    seller_kind="company", seller_id=self.firm, channel="contract", ledger_key=key)
        args.update(over)
        return recording.record_sale(**args)

    def test_a_taxed_payment_is_recorded_by_its_gross_total_and_audited(self):
        self.go(0)
        res = self.taxed(10, 1_000, "tx:1")
        self.assertEqual((res.detail["net"], res.detail["tax"]), (9_500, 500))
        out = self.call("tx:1")
        self.assertTrue(out.ok, out)
        tx = MarketTransaction.objects.get()
        self.assertEqual(tx.total_cents, 10_000)
        self.assertTrue(self.call("tx:1").detail["already_applied"])
        self.assertTrue(audit_market().ok)

    def test_a_taxed_payment_that_does_not_add_up_to_the_total_is_refused(self):
        self.go(0)
        self.taxed(10, 1_000, "tx:2")
        self.assertRefused(self.call("tx:2", unit_price_cents=1_100), "PAYMENT_NOT_FOUND")
        self.assertRefused(self.call("tx:2", unit_price_cents=900), "PAYMENT_NOT_FOUND")
        self.assertEqual(MarketTransaction.objects.count(), 0)

    def test_reversing_only_the_tax_leg_is_flagged_by_the_audit(self):
        from ledger.models import Entry
        self.go(0)
        self.taxed(10, 1_000, "tx:3")
        self.assertTrue(self.call("tx:3").ok)
        tax = Entry.objects.get(transaction__key="tx:3", nature="tax_sales")
        self.assertTrue(ledger.reverse(tax.pk, "teste", key="rev:t").ok)
        self.assertEqual({f["code"] for f in audit_market().findings}, {"SALE_PAYMENT_REVERSED"})
    audit_market_at_end = False
