"""
Concorrência dos Imóveis: lances simultâneos, encerramento repetido, vencedor gastando enquanto o leilão fecha, compra disputada,
compra × retirada do anúncio, anúncio × início de obra. Vale em PostgreSQL e em SQLite (o banco serializa); em PG nada mascara deadlock.
"""
from django.test import TransactionTestCase

from accounts.models import Usuario
from catalog.loader import sync_catalog
from companies import construction
from companies import services as company_services
from core import clock as game_clock
from core.models import WorldClock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.models import Lot
from geography.tests.base import SMALL
from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import Nature
from ledger.models import Entry
from ledger.tests.base import fund_account, install_test_role
from ledger.tests.test_scenario_concurrency import run_together
from players.services import create_player
from properties import services
from properties.audit import audit_properties
from properties.models import Auction, AuctionBid, Listing, TitleEvent

REAL = 100


class PropertiesConcurrencyTests(TransactionTestCase):
    def setUp(self):
        install_test_role(self)
        generate_world(get_scenario(**SMALL))
        sync_catalog()
        WorldClock.load()
        self.boss, self.third, self.worker, self.fourth = (create_player(Usuario.objects.create_user(f"q{n}")) for n in (1, 2, 3, 4))
        for p in (self.boss, self.third, self.worker, self.fourth):
            fund_account(ledger.player_account(p.pk), 500_000 * REAL)
        self.build = company_services.found_company(self.boss.pk, "construction", "Construtora", 0).detail["company"]
        self.assertTrue(company_services.fund_company(self.boss.pk, self.build, 5_000_000).ok)
        self.lots = list(Lot.objects.filter(category="residential").order_by("pk"))

    # --- cenários -------------------------------------------------------------------------------------------------------
    def player_ref(self, p):
        return {"kind": "player", "id": p.pk}

    def company_ref(self, c):
        return {"kind": "company", "id": c}

    def ended_auction(self, lot, bidder_kind, bidder_id, actor, amount):
        """Leilão que JÁ passou do fim, com um lance (montado com o relógio no passado para não depender de espera)."""
        now = game_clock.now()
        a = Auction.objects.create(lot=lot, min_bid_cents=amount, starts_at=now - 10_000, base_ends_at=now - 100, ends_at=now - 100,
                                   top_bid_cents=amount, top_bidder_kind=bidder_kind, top_bidder_id=bidder_id, bids=1)
        AuctionBid.objects.create(auction=a, sequence=1, bidder_kind=bidder_kind, bidder_id=bidder_id, amount_cents=amount,
                                  at=now - 5_000, extended=False, acted_by=actor.pk)
        return a

    def own(self, lot, kind, entity, actor, price=1_000):
        a = self.ended_auction(lot, kind, entity, actor, price)
        res = services.close_auction(a.pk)
        self.assertEqual(res.detail["status"], "sold", res)
        return a

    def open_one(self, lot, min_bid=1_000):
        res = services.open_auction(lot.pk, min_bid, duration_seconds=100_000)
        self.assertTrue(res.ok, res)
        return res.detail["auction"]

    def assertClean(self):
        for report in (audit_properties(), audit_ledger()):
            self.assertTrue(report.ok, report.findings)

    # --- leilão ---------------------------------------------------------------------------------------------------------
    def test_two_equal_bids_at_once_have_exactly_one_leader(self):
        a = self.open_one(self.lots[0])
        jobs = run_together(lambda: services.bid(self.third.pk, a, self.player_ref(self.third), 5_000),
                            lambda: services.bid(self.worker.pk, a, self.player_ref(self.worker), 5_000))
        self.assertEqual(sorted(j.result.code for j in jobs), ["BID_TOO_LOW", "OK"], [j.result for j in jobs])
        auction = Auction.objects.get(pk=a)
        self.assertEqual((auction.bids, auction.top_bid_cents, AuctionBid.objects.count()), (1, 5_000, 1))
        self.assertClean()

    def test_many_bidders_leave_a_strictly_increasing_history_and_the_highest_leads(self):
        a = self.open_one(self.lots[0])
        people = [self.third, self.worker, self.fourth]
        jobs = run_together(*[(lambda p=p, k=k: services.bid(p.pk, a, self.player_ref(p), 2_000 + 100 * k)) for k, p in enumerate(people)])
        rows = list(AuctionBid.objects.filter(auction_id=a).order_by("sequence"))
        self.assertEqual([r.sequence for r in rows], list(range(1, len(rows) + 1)))
        self.assertEqual([r.amount_cents for r in rows], sorted({r.amount_cents for r in rows}))
        self.assertEqual(Auction.objects.get(pk=a).top_bid_cents, rows[-1].amount_cents)
        self.assertEqual(sum(1 for j in jobs if j.result.ok), len(rows))
        self.assertClean()

    def test_the_same_bidder_twice_at_once_leads_once(self):
        a = self.open_one(self.lots[0])
        jobs = run_together(*[lambda: services.bid(self.third.pk, a, self.player_ref(self.third), 3_000) for _ in range(4)])
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertTrue(all(j.result.code in {"ALREADY_TOP_BIDDER", "BID_TOO_LOW"} for j in jobs if not j.result.ok))
        self.assertEqual(AuctionBid.objects.count(), 1)
        self.assertClean()

    def test_closing_the_same_auction_many_times_charges_and_transfers_once(self):
        a = self.ended_auction(self.lots[0], "player", self.third.pk, self.third, 7_000)
        jobs = run_together(*[lambda: services.close_auction(a.pk) for _ in range(5)])
        self.assertEqual(sum(1 for j in jobs if j.result.ok and j.result.detail["closed"]), 1, [j.result for j in jobs])
        self.assertEqual(Entry.objects.filter(nature=Nature.AUCTION_PAYMENT.value).count(), 1)
        self.assertEqual(TitleEvent.objects.count(), 1)
        self.assertEqual(Auction.objects.get(pk=a.pk).status, "sold")
        self.assertClean()

    def test_the_tick_and_a_direct_close_do_not_double_close(self):
        a = self.ended_auction(self.lots[0], "player", self.third.pk, self.third, 7_000)
        jobs = run_together(services.close_due, lambda: services.close_auction(a.pk), services.close_due)
        self.assertEqual(Entry.objects.filter(nature=Nature.AUCTION_PAYMENT.value).count(), 1)
        self.assertEqual(TitleEvent.objects.count(), 1)
        self.assertClean()

    def test_the_winner_spending_while_the_auction_closes_never_overdraws_and_never_half_sells(self):
        player = self.fourth
        a = self.ended_auction(self.lots[0], "player", player.pk, player, 50_000 * REAL)
        account = ledger.player_account(player.pk).pk
        sink = ledger.player_account(self.boss.pk).pk
        spend = lambda: ledger.transfer(account, sink, 480_000 * REAL, Nature.DONATION, key="spend:1", reference_kind="t", reference_id="1")
        jobs = run_together(lambda: services.close_auction(a.pk), spend)
        self.assertGreaterEqual(ledger.balance_of(account), 0)
        status = Auction.objects.get(pk=a.pk).status
        paid = Entry.objects.filter(nature=Nature.AUCTION_PAYMENT.value).count()
        self.assertIn((status, paid, TitleEvent.objects.count()), {("sold", 1, 1), ("invalidated", 0, 0)})   # nunca meio-vendido
        self.assertClean()

    def test_several_due_auctions_are_each_closed_exactly_once_by_parallel_ticks(self):
        auctions = [self.ended_auction(self.lots[i], "player", p.pk, p, 1_000 + i) for i, p in enumerate((self.third, self.worker, self.fourth))]
        run_together(services.close_due, services.close_due, services.close_due)
        self.assertEqual(sorted(Auction.objects.values_list("status", flat=True)), ["sold"] * 3)
        self.assertEqual(Entry.objects.filter(nature=Nature.AUCTION_PAYMENT.value).count(), 3)
        self.assertEqual(TitleEvent.objects.count(), 3)
        self.assertEqual(len(auctions), 3)
        self.assertClean()

    # --- venda ----------------------------------------------------------------------------------------------------------
    def listed(self, price=20_000 * REAL):
        lot = self.lots[0]
        self.own(lot, "player", self.third.pk, self.third)
        res = services.list_property(self.third.pk, lot.pk, self.player_ref(self.third), price)
        self.assertTrue(res.ok, res)
        return lot, res.detail["listing"]

    def test_two_buyers_for_one_listing_have_exactly_one_purchase(self):
        lot, li = self.listed()
        jobs = run_together(lambda: services.buy_property(self.worker.pk, li, self.player_ref(self.worker)),
                            lambda: services.buy_property(self.fourth.pk, li, self.player_ref(self.fourth)))
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertEqual(next(j.result.code for j in jobs if not j.result.ok), "LISTING_NOT_OPEN")
        self.assertEqual(Entry.objects.filter(transaction__key=f"listing:{li}:sale").count(), 1)
        self.assertEqual(TitleEvent.objects.filter(lot=lot).count(), 2)
        self.assertClean()

    def test_buying_versus_withdrawing_the_listing_has_one_coherent_outcome(self):
        lot, li = self.listed()
        jobs = run_together(lambda: services.buy_property(self.worker.pk, li, self.player_ref(self.worker)),
                            lambda: services.unlist_property(self.third.pk, li, self.player_ref(self.third)))
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        status = Listing.objects.get(pk=li).status
        self.assertIn(status, {"sold", "cancelled"})
        self.assertEqual(TitleEvent.objects.filter(lot=lot).count(), 2 if status == "sold" else 1)
        self.assertClean()

    def test_listing_versus_starting_a_construction_on_the_same_lot_never_does_both(self):
        lot = self.lots[0]
        self.own(lot, "company", self.build, self.boss)
        jobs = run_together(lambda: services.list_property(self.boss.pk, lot.pk, self.company_ref(self.build), 9_000),
                            lambda: construction.start_construction(self.boss.pk, self.build, "low_density_simple", lot.pk))
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertIn(next(j.result.code for j in jobs if not j.result.ok), {"LOT_HAS_ACTIVE_SITE", "LOT_RESERVED"})
        self.assertClean()

    def test_two_listings_of_the_same_lot_at_once_leave_one_open(self):
        lot = self.lots[0]
        self.own(lot, "player", self.third.pk, self.third)
        jobs = run_together(*[lambda: services.list_property(self.third.pk, lot.pk, self.player_ref(self.third), 9_000) for _ in range(3)])
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertEqual(Listing.objects.filter(status="open").count(), 1)
        self.assertClean()
