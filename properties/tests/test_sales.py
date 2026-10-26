"""Venda entre proprietários (10 §8): anúncio, compra, preço do dono, SALE sem imposto, empresas, recusas, idempotência."""
from ledger import services as ledger
from ledger.constants import Nature
from ledger.models import Entry
from players import registry
from properties import services
from properties.models import Listing, TitleEvent

from .base import PropertiesBase


class SalesBase(PropertiesBase):
    def setUp(self):
        super().setUp()
        self.lot_ = self.lot()
        self.sold_to(self.worker, self.lot_, price=2_000)          # o worker é o proprietário (comprou no leilão)

    def list_it(self, price=50_000, owner=None, lot=None, actor=None):
        return services.list_property((actor or self.worker).pk, (lot or self.lot_).pk, owner or self.player_ref(self.worker), price)

    def listing(self, price=50_000):
        res = self.list_it(price)
        self.assertTrue(res.ok, res)
        return res.detail["listing"]

    def buy(self, buyer=None, listing=None, party=None):
        buyer = buyer or self.third
        return services.buy_property(buyer.pk, listing, party or self.player_ref(buyer))


class ListingTests(SalesBase):
    def test_the_owner_lists_at_his_own_price(self):
        res = self.list_it(123_456)
        self.assertTrue(res.ok, res)
        li = Listing.objects.get()
        self.assertEqual((li.status, li.price_cents, li.seller_kind, li.seller_id, li.lot_id), ("open", 123_456, "player", self.worker.pk, self.lot_.pk))
        self.assertEqual(services.lot_view(self.lot_.pk)["open_listing"], {"id": li.pk, "price_cents": 123_456})

    def test_only_the_owner_lists_and_only_once(self):
        self.assertEqual(self.list_it(actor=self.third, owner=self.player_ref(self.third)).code, "NOT_LOT_OWNER")
        self.assertEqual(self.list_it(actor=self.third).code, "NOT_PARTY_REPRESENTATIVE")
        self.assertEqual(self.list_it(price=0).code, "INVALID_PARAMS")
        self.assertEqual(self.list_it(price="1").code, "INVALID_PARAMS")
        self.assertEqual(self.list_it(lot=type(self.lot_)(pk=10 ** 9)).code, "LOT_NOT_FOUND")
        self.assertEqual(services.list_property(10 ** 9, self.lot_.pk, self.player_ref(self.worker), 100).code, "PLAYER_NOT_FOUND")
        self.assertEqual(self.list_it(owner={"kind": "government", "id": 1}).code, "INVALID_PARTY")
        self.assertTrue(self.list_it().ok)
        self.assertEqual(self.list_it().code, "ALREADY_LISTED")
        self.assertEqual(Listing.objects.count(), 1)

    def test_a_government_lot_cannot_be_listed(self):
        res = services.list_property(self.worker.pk, self.lot(n=1).pk, self.player_ref(self.worker), 100)
        self.assertEqual(res.code, "NOT_LOT_OWNER")

    def test_the_owner_withdraws_and_may_list_again(self):
        li = self.listing()
        self.assertEqual(services.unlist_property(self.third.pk, li, self.player_ref(self.third)).code, "NOT_SELLER")
        self.assertEqual(services.unlist_property(self.worker.pk, li, self.player_ref(self.third)).code, "NOT_PARTY_REPRESENTATIVE")
        self.assertTrue(services.unlist_property(self.worker.pk, li, self.player_ref(self.worker)).ok)
        self.assertEqual(Listing.objects.get().status, "cancelled")
        self.assertEqual(services.unlist_property(self.worker.pk, li, self.player_ref(self.worker)).code, "LISTING_NOT_OPEN")
        self.assertEqual(self.buy(listing=li).code, "LISTING_NOT_OPEN")
        self.assertTrue(self.list_it(60_000).ok)


class PurchaseTests(SalesBase):
    def test_the_buyer_pays_the_owners_price_without_tax_and_receives_the_property(self):
        li = self.listing(50_000)
        buyer_before, seller_before = self.money(self.third), self.money(self.worker)
        circulation = ledger_metrics_circulation()
        res = self.buy(listing=li)
        self.assertTrue(res.ok, res)
        self.assertEqual((self.money(self.third), self.money(self.worker)), (buyer_before - 50_000, seller_before + 50_000))
        self.assertEqual(ledger_metrics_circulation(), circulation)
        entry = Entry.objects.get(nature=Nature.SALE.value, category="property")
        self.assertEqual((entry.amount, entry.operation), (50_000, "sale"))
        self.assertFalse(Entry.objects.filter(nature=Nature.TAX_SALES.value).exists())            # 24 §24.7: venda de imóvel sem imposto
        self.assertEqual(services.owner_of_lot(self.lot_.pk), (services.OwnerKind.PLAYER, self.third.pk))
        self.assertEqual([(e.sequence, e.reason, e.to_id, e.price_cents) for e in TitleEvent.objects.order_by("sequence")],
                         [(1, "auction", self.worker.pk, 2_000), (2, "sale", self.third.pk, 50_000)])
        li_row = Listing.objects.get()
        self.assertEqual((li_row.status, li_row.buyer_id, li_row.ledger_key), ("sold", self.third.pk, f"listing:{li}:sale"))

    def test_a_company_buys_and_sells_through_its_owner(self):
        li = self.listing(40_000)
        cash = self.money_of("company", self.build)
        res = services.buy_property(self.boss.pk, li, self.company_ref(self.build))
        self.assertTrue(res.ok, res)
        self.assertEqual(self.money_of("company", self.build), cash - 40_000)
        self.assertEqual(services.owner_of_lot(self.lot_.pk), (services.OwnerKind.COMPANY, self.build))
        li2 = services.list_property(self.boss.pk, self.lot_.pk, self.company_ref(self.build), 45_000)
        self.assertTrue(li2.ok, li2)
        self.assertEqual(services.unlist_property(self.worker.pk, li2.detail["listing"], self.company_ref(self.build)).code, "NOT_OWNER")
        res = services.buy_property(self.worker.pk, li2.detail["listing"], self.player_ref(self.worker))
        self.assertTrue(res.ok, res)
        self.assertEqual(services.owner_of_lot(self.lot_.pk), (services.OwnerKind.PLAYER, self.worker.pk))

    def test_refusals(self):
        li = self.listing(50_000)
        self.assertEqual(self.buy(self.worker, li).code, "SELF_PURCHASE")
        self.assertEqual(self.buy(listing=10 ** 9).code, "LISTING_NOT_FOUND")
        self.assertEqual(self.buy(listing="x").code, "INVALID_PARAMS")
        self.assertEqual(services.buy_property(10 ** 9, li, self.player_ref(self.third)).code, "PLAYER_NOT_FOUND")
        self.assertEqual(services.buy_property(self.third.pk, li, self.player_ref(self.boss)).code, "NOT_PARTY_REPRESENTATIVE")
        self.assertEqual(services.buy_property(self.third.pk, li, self.company_ref(self.build)).code, "NOT_OWNER")
        self.assertEqual(services.buy_property(self.third.pk, li, {"kind": "x", "id": 1}).code, "INVALID_PARTY")
        poor = self.new_player("p9")
        res = self.buy(poor, li)
        self.assertEqual((res.code, res.detail["price"]), ("INSUFFICIENT_FUNDS", 50_000))
        self.assertEqual(Listing.objects.get().status, "open")
        self.assertEqual(TitleEvent.objects.count(), 1)

    def test_a_sold_listing_cannot_be_bought_twice(self):
        li = self.listing()
        self.assertTrue(self.buy(listing=li).ok)
        before = Entry.objects.filter(nature=Nature.SALE.value).count()
        self.assertEqual(self.buy(self.boss, li).code, "LISTING_NOT_OPEN")
        self.assertEqual(Entry.objects.filter(nature=Nature.SALE.value).count(), before)

    def test_laws_can_bar_a_buyer(self):
        services.register_eligibility("test_law", lambda kind, entity, lot: services._refuse("NOT_ELIGIBLE") if entity == self.third.pk else None)
        self.addCleanup(services.unregister_eligibility, "test_law")
        li = self.listing()
        self.assertEqual(self.buy(listing=li).code, "NOT_ELIGIBLE")
        self.assertTrue(self.buy(self.boss, li).ok)

    def test_an_active_construction_blocks_listing_and_sale(self):
        """10 §28: a obra em andamento fica no lote do dono; ele não pode anunciá-lo (nem vendê-lo) até concluir."""
        lot = self.lot(n=1)
        self.sold_to(self.boss, lot, price=3_000, party=self.company_ref(self.build))
        li = services.list_property(self.boss.pk, lot.pk, self.company_ref(self.build), 10_000)
        self.assertTrue(li.ok, li)
        self.assertEqual(services.unlist_property(self.boss.pk, li.detail["listing"], self.company_ref(self.build)).ok, True)
        from companies import construction
        self.assertTrue(construction.start_construction(self.boss.pk, self.build, "low_density_simple", lot.pk).ok)
        self.assertEqual(services.list_property(self.boss.pk, lot.pk, self.company_ref(self.build), 10_000).code, "LOT_HAS_ACTIVE_SITE")

    def test_the_registry_path_is_the_same_for_every_player(self):
        li = self.listing(50_000)
        target = {"listing": li, "party": self.player_ref(self.third)}
        self.assertTrue(registry.check_action(self.third.pk, "buy_property", target).available)
        self.assertEqual(registry.check_action(self.worker.pk, "buy_property", {"listing": li, "party": self.player_ref(self.worker)}).code,
                         "SELF_PURCHASE")
        self.assertEqual(registry.check_action(self.third.pk, "buy_property", {"listing": li}).code, "INVALID_PARAMS")
        res = registry.execute_action(self.third.pk, "buy_property", target)
        self.assertTrue(res.ok, res)
        listing = registry.execute_action(self.third.pk, "list_property", {"lot": self.lot_.pk, "owner": self.player_ref(self.third), "price": 70_000})
        self.assertTrue(listing.ok, listing)
        self.assertTrue(registry.execute_action(self.third.pk, "unlist_property",
                                                {"listing": listing.detail["listing"], "party": self.player_ref(self.third)}).ok)


def ledger_metrics_circulation() -> int:
    from ledger.audit import ledger_metrics
    return ledger_metrics()["in_circulation"]
