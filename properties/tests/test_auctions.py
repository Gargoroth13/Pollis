"""Leilão público (10 §4): abertura, lances, extensão, encerramento, pagamento ao Município, invalidação, idempotência, tick."""
from decimal import Decimal

from core import ticks
from ledger import services as ledger
from ledger.audit import audit_ledger, ledger_metrics
from ledger.constants import Nature
from ledger.models import Entry
from players import registry
from properties import params, services
from properties.models import Auction, AuctionBid, LotTitle, PropertiesImmutableError, TitleEvent

from .base import PropertiesBase


class OpenTests(PropertiesBase):
    def test_a_government_lot_goes_to_auction_with_the_minimum_bid_and_the_duration(self):
        lot = self.lot()
        now = self.clk.now()
        res = services.open_auction(lot.pk, 2_000, duration_seconds=3_600)
        self.assertTrue(res.ok, res)
        a = Auction.objects.get()
        self.assertEqual((a.status, a.min_bid_cents, a.starts_at, a.ends_at, a.base_ends_at, a.top_bid_cents, a.bids),
                         ("open", 2_000, now, now + 3_600, now + 3_600, None, 0))

    def test_the_default_duration_is_the_provisional_parameter(self):
        self.assertTrue(services.open_auction(self.lot().pk, 100).ok)
        a = Auction.objects.get()
        self.assertEqual(a.ends_at - a.starts_at, params.AUCTION_DURATION_SECONDS)

    def test_refusals(self):
        lot = self.lot()
        self.assertEqual(services.open_auction("x", 100).code, "INVALID_PARAMS")
        self.assertEqual(services.open_auction(lot.pk, 0).code, "INVALID_PARAMS")
        self.assertEqual(services.open_auction(lot.pk, True).code, "INVALID_PARAMS")
        self.assertEqual(services.open_auction(lot.pk, 100, duration_seconds=0).code, "INVALID_PARAMS")
        self.assertEqual(services.open_auction(10 ** 9, 100).code, "LOT_NOT_FOUND")
        self.assertEqual(services.open_auction(self.lot("institutional").pk, 100).code, "LOT_NOT_AUCTIONABLE")
        special = self.lot(n=3)
        type(special).objects.filter(pk=special.pk).update(category="special")
        self.assertEqual(services.open_auction(special.pk, 100).code, "LOT_NOT_AUCTIONABLE")
        for category in ("residential", "commercial", "industrial", "rural"):
            self.assertTrue(services.open_auction(self.lot(category).pk, 100).ok, category)

    def test_one_open_auction_per_lot_and_an_occupied_lot_is_not_auctioned(self):
        lot = self.lot()
        self.assertTrue(services.open_auction(lot.pk, 100).ok)
        self.assertEqual(services.open_auction(lot.pk, 100).code, "AUCTION_OPEN")
        other = self.lot(n=1)
        type(other).objects.filter(pk=other.pk).update(occupation="occupied")
        self.assertEqual(services.open_auction(other.pk, 100).code, "LOT_OCCUPIED")

    def test_a_lot_with_a_private_owner_is_not_auctioned(self):
        lot = self.lot()
        self.sold_to(self.worker, lot)
        self.assertEqual(services.open_auction(lot.pk, 100).code, "LOT_NOT_GOVERNMENT_OWNED")


class BidTests(PropertiesBase):
    def test_the_first_bid_must_reach_the_minimum_and_each_next_must_exceed_the_top(self):
        a = self.auction(min_bid=1_000)
        self.assertEqual(self.bid(self.worker, a, 999).code, "BID_TOO_LOW")
        res = self.bid(self.worker, a, 1_000)
        self.assertTrue(res.ok, res)
        self.assertEqual((res.detail["bid"], res.detail["amount"], res.detail["extended"]), (1, 1_000, False))
        self.assertEqual(self.bid(self.third, a, 1_000).code, "BID_TOO_LOW")                 # igualar não basta
        self.assertTrue(self.bid(self.third, a, 1_000 + params.MIN_BID_INCREMENT_CENTS).ok)
        view = services.auction_view(a)
        self.assertEqual((view["top_bid_cents"], view["top_bidder"], view["bids"]), (1_001, ["player", self.third.pk], 2))
        self.assertEqual([h["amount_cents"] for h in view["history"]], [1_000, 1_001])

    def test_the_top_bidder_cannot_outbid_himself(self):
        a = self.auction()
        self.assertTrue(self.bid(self.worker, a, 1_000).ok)
        self.assertEqual(self.bid(self.worker, a, 5_000).code, "ALREADY_TOP_BIDDER")
        self.assertEqual(Auction.objects.get().bids, 1)

    def test_funds_are_checked_at_bid_time_without_reserving_them(self):
        a = self.auction()
        available = self.money(self.worker)
        res = self.bid(self.worker, a, available + 1)
        self.assertEqual((res.code, res.detail["available"]), ("INSUFFICIENT_FUNDS", available))
        self.assertTrue(self.bid(self.worker, a, available).ok)
        self.assertEqual(self.money(self.worker), available)                      # nada reservado nem cobrado agora
        self.assertEqual(self.municipality(self.lot()), 0)

    def test_invalid_states_and_permissions(self):
        a = self.auction()
        self.assertEqual(services.bid(10 ** 9, a, self.player_ref(self.worker), 1_000).code, "PLAYER_NOT_FOUND")
        self.assertEqual(services.bid(self.worker.pk, "x", self.player_ref(self.worker), 1_000).code, "INVALID_PARAMS")
        self.assertEqual(services.bid(self.worker.pk, a, self.player_ref(self.worker), 0).code, "INVALID_PARAMS")
        self.assertEqual(services.bid(self.worker.pk, a, {"kind": "government", "id": 1}, 1_000).code, "INVALID_PARTY")
        self.assertEqual(services.bid(self.worker.pk, a, {"kind": "player"}, 1_000).code, "INVALID_PARTY")
        self.assertEqual(services.bid(self.worker.pk, 10 ** 9, self.player_ref(self.worker), 1_000).code, "AUCTION_NOT_FOUND")
        self.assertEqual(services.bid(self.worker.pk, a, self.player_ref(self.third), 1_000).code, "NOT_PARTY_REPRESENTATIVE")
        self.assertEqual(services.bid(self.worker.pk, a, self.company_ref(self.build), 1_000).code, "NOT_OWNER")
        self.assertEqual(services.bid(self.boss.pk, a, self.company_ref(10 ** 9), 1_000).code, "COMPANY_NOT_FOUND")

    def test_a_company_bids_through_its_owner_and_pays_from_the_company_account(self):
        a = self.auction()
        res = services.bid(self.boss.pk, a, self.company_ref(self.build), 2_000)
        self.assertTrue(res.ok, res)
        row = AuctionBid.objects.get()
        self.assertEqual((row.bidder_kind, row.bidder_id, row.acted_by), ("company", self.build, self.boss.pk))
        self.assertEqual(services.bid(self.boss.pk, a, self.company_ref(self.build), 3_000).code, "ALREADY_TOP_BIDDER")
        cash = self.money_of("company", self.firm)
        res = services.bid(self.boss.pk, a, self.company_ref(self.firm), cash + 1)           # a empresa não gasta o caixa do Dono
        self.assertEqual((res.code, res.detail["available"]), ("INSUFFICIENT_FUNDS", cash))

    def test_closed_auctions_and_ended_auctions_take_no_bids(self):
        a = self.auction(duration=3_600)
        self.pass_time(3_600)                                                        # exatamente no encerramento: acabou
        self.assertEqual(self.bid(self.worker, a, 1_000).code, "AUCTION_ENDED")
        services.close_auction(a)
        self.assertEqual(self.bid(self.worker, a, 1_000).code, "AUCTION_NOT_OPEN")

    def test_eligibility_rules_registered_by_laws_can_bar_a_bidder(self):
        refusal = lambda kind, entity, lot: (services._refuse("NOT_ELIGIBLE", why="lei") if entity == self.third.pk else None)
        services.register_eligibility("test_law", refusal)
        self.addCleanup(services.unregister_eligibility, "test_law")
        with self.assertRaises(ValueError):
            services.register_eligibility("test_law", refusal)
        a = self.auction()
        self.assertEqual(self.bid(self.third, a, 1_000).code, "NOT_ELIGIBLE")
        self.assertTrue(self.bid(self.worker, a, 1_000).ok)

    def test_the_bid_history_is_immutable(self):
        a = self.auction()
        self.assertTrue(self.bid(self.worker, a, 1_000).ok)
        row = AuctionBid.objects.get()
        row.amount_cents = 1
        with self.assertRaises(PropertiesImmutableError):
            row.save()
        with self.assertRaises(PropertiesImmutableError):
            row.delete()


class ExtensionTests(PropertiesBase):
    """10 §4.3: um lance perto do fim estende o leilão (parâmetros [PROV]: janela 10 min, extensão 10 min)."""

    def test_a_bid_before_the_window_does_not_extend(self):
        a = self.auction(duration=3_600)
        self.pass_time(3_600 - params.EXTENSION_WINDOW_SECONDS - 1)
        res = self.bid(self.worker, a, 1_000)
        self.assertEqual((res.detail["extended"], Auction.objects.get().ends_at - Auction.objects.get().base_ends_at), (False, 0))

    def test_a_bid_inside_the_window_adds_the_extension_each_time(self):
        a = self.auction(duration=3_600)
        base = Auction.objects.get().base_ends_at
        self.pass_time(3_600 - 60)
        res = self.bid(self.worker, a, 1_000)
        self.assertEqual((res.detail["extended"], res.detail["ends_at"]), (True, base + params.EXTENSION_SECONDS))
        self.pass_time(params.EXTENSION_SECONDS - 60)                                 # de novo na janela do novo fim
        res = self.bid(self.third, a, 2_000)
        self.assertEqual((res.detail["extended"], res.detail["ends_at"]), (True, base + 2 * params.EXTENSION_SECONDS))
        auction = Auction.objects.get()
        self.assertEqual(auction.extensions, 2)
        self.assertEqual([b.extended for b in AuctionBid.objects.order_by("sequence")], [True, True])
        self.pass_time(61)                                                            # passou do fim ORIGINAL: ainda aceita lance
        self.assertTrue(self.bid(self.worker, a, 3_000).ok)

    def test_an_extended_auction_is_not_closed_at_the_original_time(self):
        a = self.auction(duration=3_600)
        base = Auction.objects.get().base_ends_at
        self.pass_time(3_600 - 60)
        self.assertTrue(self.bid(self.worker, a, 1_000).ok)
        self.clk.set(base + 1)
        self.assertEqual(services.close_due(), 0)
        self.assertEqual(Auction.objects.get().status, "open")
        self.clk.set(base + params.EXTENSION_SECONDS)
        self.assertEqual(services.close_due(), 1)
        self.assertEqual(Auction.objects.get().status, "sold")


class CloseTests(PropertiesBase):
    def test_the_winner_pays_the_municipality_of_the_lot_and_receives_the_title(self):
        lot = self.lot()
        a = self.auction(lot, min_bid=1_000)
        self.assertTrue(self.bid(self.worker, a, 1_000).ok)
        self.assertTrue(self.bid(self.third, a, 4_000).ok)
        before = (self.money(self.third), self.money(self.worker), self.municipality(lot))
        circulation = ledger_metrics()["in_circulation"]
        self.pass_time(3_601)
        res = services.close_auction(a)
        self.assertEqual((res.code, res.detail["status"], res.detail["winner"], res.detail["price_cents"]), ("OK", "sold", ["player", self.third.pk], 4_000))
        self.assertEqual((self.money(self.third), self.money(self.worker), self.municipality(lot)),
                         (before[0] - 4_000, before[1], before[2] + 4_000))              # só o vencedor paga; o Município recebe
        self.assertEqual(ledger_metrics()["in_circulation"], circulation)                                 # nada se cria nem se perde
        entry = Entry.objects.get(nature=Nature.AUCTION_PAYMENT.value)
        self.assertEqual((entry.amount, entry.category), (4_000, "auction"))
        self.assertEqual(services.owner_of_lot(lot.pk), (services.OwnerKind.PLAYER, self.third.pk))
        event = TitleEvent.objects.get()
        self.assertEqual((event.sequence, event.reason, event.from_kind, event.from_id, event.price_cents, event.ledger_key),
                         (1, "auction", "government", None, 4_000, f"auction:{a}:payment"))
        a_row = Auction.objects.get()
        self.assertEqual((a_row.status, a_row.closed_at, a_row.ledger_key), ("sold", self.clk.now(), f"auction:{a}:payment"))
        self.assertTrue(audit_ledger().ok)

    def test_the_municipality_is_the_city_of_the_lots_neighborhood(self):
        lot = self.lot(n=5)                                                              # algum lote de outra cidade, se houver
        self.sold_to(self.worker, lot, price=3_000)
        entry = Entry.objects.get(nature=Nature.AUCTION_PAYMENT.value)
        self.assertEqual((entry.to_account.kind, entry.to_account.owner_id), ("municipality", lot.neighborhood.city_id))

    def test_a_company_winner_pays_with_the_company_money(self):
        lot = self.lot()
        before_company, before_boss = self.money_of("company", self.build), self.money(self.boss)
        self.sold_to(self.boss, lot, price=7_000, party=self.company_ref(self.build))
        self.assertEqual((self.money_of("company", self.build), self.money(self.boss)), (before_company - 7_000, before_boss))
        self.assertEqual(services.owner_of_lot(lot.pk), (services.OwnerKind.COMPANY, self.build))

    def test_no_bids_means_unsold_and_the_lot_can_be_auctioned_again(self):
        lot = self.lot()
        a = self.auction(lot)
        self.pass_time(3_601)
        res = services.close_auction(a)
        self.assertEqual((res.detail["closed"], res.detail["status"]), (True, "unsold"))
        self.assertEqual(Entry.objects.filter(nature=Nature.AUCTION_PAYMENT.value).count(), 0)
        self.assertEqual(services.owner_of_lot(lot.pk), (services.OwnerKind.GOVERNMENT, None))
        self.assertTrue(services.open_auction(lot.pk, 500).ok)

    def test_a_winner_who_cannot_pay_invalidates_the_sale_without_moving_money(self):
        """10 §4.4: o design exige fundos do vencedor; o que fazer sem eles é lacuna registrada (design/10a). Hoje: invalida."""
        lot = self.lot()
        a = self.auction(lot, min_bid=1_000)
        self.assertTrue(self.bid(self.worker, a, 5_000).ok)
        sink = ledger.player_account(self.boss.pk).pk
        spendable = self.money(self.worker)
        res = ledger.transfer(ledger.player_account(self.worker.pk).pk, sink, spendable - 100, Nature.SALE, key="drain", reference_kind="test",
                              reference_id="1")
        self.assertTrue(res.ok, res)
        self.pass_time(3_601)
        closed = services.close_auction(a)
        self.assertEqual((closed.detail["status"], closed.detail["reason"]), ("invalidated", "INSUFFICIENT_FUNDS"))
        self.assertEqual(Entry.objects.filter(nature=Nature.AUCTION_PAYMENT.value).count(), 0)
        self.assertEqual(services.owner_of_lot(lot.pk), (services.OwnerKind.GOVERNMENT, None))
        self.assertEqual(TitleEvent.objects.count(), 0)
        self.assertEqual(Auction.objects.get().result_note, "INSUFFICIENT_FUNDS")
        self.assertTrue(services.open_auction(lot.pk, 500).ok)                            # o lote pode ser leiloado de novo

    def test_closing_is_idempotent_and_never_early(self):
        lot = self.lot()
        a = self.auction(lot)
        self.assertTrue(self.bid(self.worker, a, 2_000).ok)
        self.assertFalse(services.close_auction(a).detail["closed"])                       # ainda não venceu
        self.pass_time(3_601)
        self.assertTrue(services.close_auction(a).detail["closed"])
        again = services.close_auction(a)
        self.assertEqual((again.ok, again.detail["closed"], again.detail["status"]), (True, False, "sold"))
        self.assertEqual(services.close_due(), 0)
        self.assertEqual((Entry.objects.filter(nature=Nature.AUCTION_PAYMENT.value).count(), TitleEvent.objects.count()), (1, 1))
        self.assertEqual(services.close_auction(10 ** 9).code, "AUCTION_NOT_FOUND")

    def test_the_world_tick_closes_every_due_auction_and_only_the_due_ones(self):
        lots = [self.lot(n=i) for i in range(3)]
        due_a, due_b = self.auction(lots[0], duration=1_800), self.auction(lots[1], duration=2_400)
        later = self.auction(lots[2], duration=7_200)
        self.assertTrue(self.bid(self.worker, due_a, 1_000).ok)
        self.assertTrue(self.bid(self.third, due_b, 1_000).ok)
        self.assertTrue(self.bid(self.worker, later, 1_000).ok)
        self.pass_time(2_500)
        ticks.advance_world()
        self.assertEqual(dict(Auction.objects.values_list("pk", "status")), {due_a: "sold", due_b: "sold", later: "open"})
        ticks.advance_world()                                                               # reprocessar não repete nada
        self.assertEqual(Entry.objects.filter(nature=Nature.AUCTION_PAYMENT.value).count(), 2)

    def test_a_lot_won_by_auction_keeps_a_chain_of_titles_through_later_sales(self):
        lot = self.lot()
        self.sold_to(self.worker, lot, price=2_000)
        view = services.lot_view(lot.pk)
        self.assertEqual((view["owner"], [h["reason"] for h in view["history"]]), (["player", self.worker.pk], ["auction"]))
        self.assertIsNone(services.lot_view(10 ** 9))


class RegistryTests(PropertiesBase):
    def test_bots_and_humans_use_the_same_registry_path(self):
        a = self.auction()
        target = {"auction": a, "bidder": self.player_ref(self.worker), "amount": 1_500}
        check = registry.check_action(self.worker.pk, "bid_auction", target)
        self.assertTrue(check.available, check)
        self.assertEqual(registry.check_action(self.worker.pk, "bid_auction", {**target, "amount": 1}).code, "BID_TOO_LOW")
        self.assertEqual(registry.check_action(self.worker.pk, "bid_auction", {"auction": a}).code, "INVALID_PARAMS")
        res = registry.execute_action(self.worker.pk, "bid_auction", target)
        self.assertTrue(res.ok, res)
        self.assertEqual(registry.check_action(self.worker.pk, "bid_auction", {**target, "amount": 9_999}).code, "ALREADY_TOP_BIDDER")
        self.assertEqual(registry.execute_action(self.worker.pk, "bid_auction", {**target, "amount": 9_999}).code, "ALREADY_TOP_BIDDER")
