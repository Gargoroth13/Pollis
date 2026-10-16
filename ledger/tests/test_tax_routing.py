from decimal import Decimal

from ledger import services as ledger
from ledger.constants import Nature
from ledger.models import Entry

from .base import LedgerTestCase


class TaxRoutingTests(LedgerTestCase):
    def test_default_destination_is_union(self):
        r = ledger.route_tax(("city", 5))
        self.assertTrue(r.ok)
        self.assertEqual(r.detail["account_id"], ledger.union_account().pk)
        self.assertEqual(r.detail["destination"], "union")

    def test_registered_resolver_routes_to_retention(self):
        ret = ledger.open_retention("militia_action", "action:1")
        ledger.register_tax_resolver("militia", lambda territory, at: ret.pk if territory == ("city", 5) else None)
        self.assertEqual(ledger.route_tax(("city", 5)).detail["account_id"], ret.pk)
        self.assertEqual(ledger.route_tax(("city", 6)).detail["account_id"], ledger.union_account().pk)

    def test_ambiguity_refuses_and_never_picks_by_arrival(self):
        r1, r2 = ledger.open_retention("a", "a:1"), ledger.open_retention("b", "b:1")
        ledger.register_tax_resolver("zeta", lambda t, at: r1.pk)
        ledger.register_tax_resolver("alpha", lambda t, at: r2.pk)
        res = ledger.route_tax(("city", 1))
        self.assertEqual(res.code, "TAX_ROUTE_AMBIGUOUS")
        # mesma resposta de dois resolvedores NÃO é ambiguidade
        ledger.unregister_tax_resolver("zeta")
        ledger.register_tax_resolver("beta", lambda t, at: r2.pk)
        self.assertTrue(ledger.route_tax(("city", 1)).ok)

    def test_resolver_must_return_open_retention(self):
        a = self.company(1)
        ledger.register_tax_resolver("bad", lambda t, at: a.pk)
        self.assertEqual(ledger.route_tax(None).code, "TAX_ROUTE_INVALID")

    def test_duplicate_resolver_name_rejected(self):
        ledger.register_tax_resolver("x", lambda t, at: None)
        with self.assertRaises(ValueError):
            ledger.register_tax_resolver("x", lambda t, at: None)

    def test_taxed_payment_splits_net_and_tax_in_one_transaction(self):
        buyer, seller = self.company(1), self.company(2)
        self.fund(buyer, 10_000)
        res = ledger.post_taxed_payment(buyer.pk, seller.pk, 1000, nature=Nature.SALE, tax_rate=Decimal("0.1"), key="s1",
                                        reference_kind="sale", reference_id=1)
        self.assertTrue(res.ok, res)
        self.assertEqual((res.detail["gross"], res.detail["tax"], res.detail["net"]), (1000, 100, 900))
        self.assertEqual((self.bal(buyer), self.bal(seller), self.bal(ledger.union_account())), (9000, 900, 100))
        self.assertEqual(len(res.detail["seqs"]), 2)
        self.assertEqual(Entry.objects.filter(transaction__key="s1", nature="tax_sales").count(), 1)

    def test_tax_rounds_once_and_net_is_remainder(self):
        buyer, seller = self.company(1), self.company(2)
        self.fund(buyer, 10_000)
        res = ledger.post_taxed_payment(buyer.pk, seller.pk, 1015, nature=Nature.SALE, tax_rate=Decimal("0.1"), key="s",
                                        reference_kind="sale", reference_id=1)
        self.assertEqual((res.detail["tax"], res.detail["net"]), (102, 913))
        self.assertEqual(res.detail["tax"] + res.detail["net"], 1015)

    def test_tax_routed_to_retention_during_action_goes_one_place_only(self):
        buyer, seller = self.company(1), self.company(2)
        self.fund(buyer, 1000)
        ret = ledger.open_retention("militia_action", "action:9")
        ledger.register_tax_resolver("militia", lambda t, at: ret.pk)
        ledger.post_taxed_payment(buyer.pk, seller.pk, 1000, nature=Nature.SALE, tax_rate=Decimal("0.2"), key="s",
                                  reference_kind="sale", reference_id=1, territory=("city", 3))
        self.assertEqual((self.bal(ret), self.bal(ledger.union_account()), self.bal(seller)), (200, 0, 800))

    def test_union_buyer_with_union_destination_has_no_self_entry(self):
        union, seller = ledger.union_account(), self.company(2)
        self.fund(union, 1000)
        res = ledger.post_taxed_payment(union.pk, seller.pk, 1000, nature=Nature.SALE, tax_rate=Decimal("0.1"), key="s",
                                        reference_kind="sale", reference_id=1)
        self.assertTrue(res.ok, res)
        self.assertEqual(len(res.detail["seqs"]), 1)                                    # só o líquido ao vendedor
        self.assertEqual((self.bal(union), self.bal(seller)), (100, 900))
        e = Entry.objects.get(pk=res.detail["seqs"][0])
        self.assertTrue(e.explained["self_compensated"])
        self.assertEqual(e.explained["tax"], 100)                                      # compensação só no Explained
        self.assertFalse(Entry.objects.filter(from_account=union, to_account=union).exists())

    def test_union_buyer_with_retention_destination_pays_tax_to_retention(self):
        union, seller = ledger.union_account(), self.company(2)
        self.fund(union, 1000)
        ret = ledger.open_retention("m", "a:1")
        ledger.register_tax_resolver("m", lambda t, at: ret.pk)
        ledger.post_taxed_payment(union.pk, seller.pk, 1000, nature=Nature.SALE, tax_rate=Decimal("0.1"), key="s",
                                  reference_kind="sale", reference_id=1)
        self.assertEqual((self.bal(union), self.bal(seller), self.bal(ret)), (0, 900, 100))

    def test_invalid_rates_and_nature(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        for rate in (Decimal("-0.1"), Decimal("1.1"), 0.1):
            self.assertEqual(ledger.post_taxed_payment(a.pk, b.pk, 10, nature=Nature.SALE, tax_rate=rate, key="k",
                                                       reference_kind="s", reference_id=1).code, "TAX_RATE_INVALID")
        self.assertEqual(ledger.post_taxed_payment(a.pk, b.pk, 10, nature=Nature.SALE, tax_rate=Decimal("0.1"), key="k",
                                                   tax_nature=Nature.SALE, reference_kind="s", reference_id=1).code, "NATURE_INVALID")

    def test_ambiguous_route_aborts_payment_without_moving_money(self):
        a, b = self.company(1), self.company(2)
        self.fund(a, 100)
        r1, r2 = ledger.open_retention("a", "a:1"), ledger.open_retention("b", "b:1")
        ledger.register_tax_resolver("x", lambda t, at: r1.pk)
        ledger.register_tax_resolver("y", lambda t, at: r2.pk)
        res = ledger.post_taxed_payment(a.pk, b.pk, 100, nature=Nature.SALE, tax_rate=Decimal("0.1"), key="k",
                                        reference_kind="s", reference_id=1)
        self.assertEqual(res.code, "TAX_ROUTE_AMBIGUOUS")
        self.assertEqual((self.bal(a), self.bal(b)), (100, 0))

    def test_full_tax_union_self_compensated_moves_nothing(self):
        union, seller = ledger.union_account(), self.company(2)
        self.fund(union, 100)
        res = ledger.post_taxed_payment(union.pk, seller.pk, 100, nature=Nature.SALE, tax_rate=Decimal("1"), key="k",
                                        reference_kind="s", reference_id=1)
        self.assertTrue(res.ok)
        self.assertEqual(res.detail["seqs"], [])
        self.assertEqual(self.bal(union), 100)
