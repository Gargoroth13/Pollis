"""
Concorrência dos Imóveis: lances simultâneos, encerramento repetido, vencedor gastando enquanto o leilão fecha, compra disputada,
compra × retirada do anúncio, anúncio × início de obra. Vale em PostgreSQL e em SQLite (o banco serializa); em PG nada mascara deadlock.
"""
import unittest

from django.db import connection
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
from properties import housing, rent, services
from properties.audit import audit_properties
from properties.models import ActiveResidence, Auction, AuctionBid, Building, Listing, RentListing, Tenancy, TitleEvent, Unit
from contracts import services as contract_services
from contracts.audit import audit_contracts
from contracts.models import Contract
from geography.constants import Occupation
from ledger.money import competence_day_of
from properties import params

REAL = 100
ON_PG = connection.vendor == "postgresql"
CROSS_ROW = unittest.skipUnless(ON_PG, "invariante entre linhas de tabelas diferentes: só o SELECT ... FOR UPDATE do lote a garante (PostgreSQL); em SQLite não há trava de linha")


class ConcurrencyBase(TransactionTestCase):
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


class PropertiesConcurrencyTests(ConcurrencyBase):
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


class RentConcurrencyTests(ConcurrencyBase):
    """Aluguel e moradia: a unidade tem no máximo um contrato em curso e um morador; a venda do imóvel cede os contratos sem corrida."""

    def house(self, owner):
        """Imóvel pronto (com unidades) no primeiro lote livre, de propriedade do jogador `owner`."""
        lot = self.lots.pop(0)
        self.own(lot, "player", owner.pk, owner)
        k = params.BUILDING_TYPES["high_density_simple"]
        b = Building.objects.create(lot=lot, kind=k.key, units=k.units, qol_bonus=k.qol_bonus, completed_at=game_clock.now())
        housing.create_units(b)
        Lot.objects.filter(pk=lot.pk).update(occupation=Occupation.OCCUPIED.value)
        return b

    def day(self, plus):
        return competence_day_of(game_clock.now()) + plus

    def list_unit(self, owner, building, index=1):
        unit = Unit.objects.get(building=building, index=index)
        res = rent.list_rent(owner.pk, {"unit": unit.pk, "owner": self.player_ref(owner), "amount": 1_000, "frequency": "daily"})
        self.assertTrue(res.ok, res)
        return unit, res.detail["rent_listing"]

    def rent_args(self, tenant, listing):
        return {"listing": listing, "tenant": self.player_ref(tenant), "starts_on": self.day(1), "ends_on": self.day(3)}

    def assertAllClean(self):
        self.assertClean()
        report = audit_contracts()
        self.assertTrue(report.ok, report.findings)

    def test_two_tenants_for_one_listing_make_exactly_one_lease(self):
        b = self.house(self.third)
        unit, li = self.list_unit(self.third, b)
        jobs = run_together(lambda: rent.rent_unit(self.worker.pk, self.rent_args(self.worker, li)),
                            lambda: rent.rent_unit(self.fourth.pk, self.rent_args(self.fourth, li)))
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertEqual(next(j.result.code for j in jobs if not j.result.ok), "RENT_LISTING_NOT_OPEN")
        self.assertEqual((Tenancy.objects.count(), Contract.objects.filter(type="rent", status="active").count()), (1, 1))
        self.assertAllClean()

    def test_the_same_tenant_renting_twice_at_once_makes_one_lease(self):
        b = self.house(self.third)
        unit, li = self.list_unit(self.third, b)
        jobs = run_together(*[lambda: rent.rent_unit(self.worker.pk, self.rent_args(self.worker, li)) for _ in range(3)])
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertEqual(Tenancy.objects.count(), 1)
        self.assertAllClean()

    def test_two_direct_proposals_accepted_at_once_lease_the_unit_once(self):
        b = self.house(self.third)
        unit = Unit.objects.get(building=b, index=1)
        ids = []
        for tenant in (self.worker, self.fourth):
            res = contract_services.propose(self.third.pk, {
                "type": "rent", "role": "landlord", "proposer": self.player_ref(self.third), "counterparty": self.player_ref(tenant),
                "terms": {"lot": b.lot_id, "unit": 1, "amount_cents": 500}, "frequency": "daily", "starts_on": self.day(1),
                "ends_on": self.day(2)})
            self.assertTrue(res.ok, res)
            ids.append((tenant, res.detail["contract"]))
        jobs = run_together(*[(lambda t=t, c=c: contract_services.accept(t.pk, c, self.player_ref(t))) for t, c in ids])
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertEqual(next(j.result.code for j in jobs if not j.result.ok), "UNIT_LEASED")
        self.assertEqual(Tenancy.objects.filter(unit=unit).count(), 1)
        self.assertAllClean()

    @CROSS_ROW
    def test_selling_the_house_versus_accepting_a_lease_never_leaves_a_lease_with_the_old_owner(self):
        b = self.house(self.third)
        res = contract_services.propose(self.third.pk, {
            "type": "rent", "role": "landlord", "proposer": self.player_ref(self.third), "counterparty": self.player_ref(self.worker),
            "terms": {"lot": b.lot_id, "unit": 1, "amount_cents": 500}, "frequency": "daily", "starts_on": self.day(1), "ends_on": self.day(2)})
        cid = res.detail["contract"]
        li = services.list_property(self.third.pk, b.lot_id, self.player_ref(self.third), 9_000).detail["listing"]
        jobs = run_together(lambda: services.buy_property(self.fourth.pk, li, self.player_ref(self.fourth)),
                            lambda: contract_services.accept(self.worker.pk, cid, self.player_ref(self.worker)))
        self.assertTrue(jobs[0].result.ok, jobs[0].result)
        c = Contract.objects.get(pk=cid)
        if jobs[1].result.ok:                       # aceite antes da venda: o contrato foi cedido ao comprador
            self.assertEqual((c.status, c.party_a_id), ("active", self.fourth.pk))
            self.assertEqual(jobs[0].result.detail["leases_ceded"], [cid])
        else:                                      # aceite depois da venda: o locador deixou de ser o dono
            self.assertEqual(jobs[1].result.code, "LANDLORD_NOT_OWNER")
            self.assertEqual(c.status, "proposed")
            self.assertEqual(Tenancy.objects.count(), 0)
        self.assertAllClean()

    @CROSS_ROW
    def test_selling_the_house_versus_the_owner_moving_in_leaves_no_resident_owner_behind(self):
        b = self.house(self.third)
        unit = Unit.objects.get(building=b, index=1)
        li = services.list_property(self.third.pk, b.lot_id, self.player_ref(self.third), 9_000).detail["listing"]
        jobs = run_together(lambda: services.buy_property(self.fourth.pk, li, self.player_ref(self.fourth)),
                            lambda: housing.set_residence(self.third.pk, unit.pk))
        self.assertTrue(jobs[0].result.ok, jobs[0].result)
        self.assertFalse(ActiveResidence.objects.filter(player=self.third).exists())      # o ex-dono não pode ficar morando
        self.assertAllClean()

    @CROSS_ROW
    def test_listing_for_rent_versus_the_owner_moving_in_never_does_both(self):
        b = self.house(self.third)
        unit = Unit.objects.get(building=b, index=1)
        jobs = run_together(lambda: rent.list_rent(self.third.pk, {"unit": unit.pk, "owner": self.player_ref(self.third), "amount": 100,
                                                                   "frequency": "daily"}),
                            lambda: housing.set_residence(self.third.pk, unit.pk))
        both = RentListing.objects.filter(unit=unit, status="open").exists() and ActiveResidence.objects.filter(unit=unit).exists()
        self.assertFalse(both, [j.result for j in jobs])
        self.assertAllClean()

    def test_two_players_moving_into_one_owned_unit_at_once_leave_one_resident(self):
        b = self.house(self.third)
        unit = Unit.objects.get(building=b, index=1)
        jobs = run_together(*[lambda: housing.set_residence(self.third.pk, unit.pk) for _ in range(3)])
        self.assertEqual(ActiveResidence.objects.filter(unit=unit).count(), 1)
        self.assertAllClean()


class SitesConcurrencyTests(ConcurrencyBase):
    """Localização de empresas: uma empresa, um lote; a venda do lote encerra a localização sem corrida."""

    def matrix_with_lots(self, n=2):
        from properties import sites
        self.sites = sites
        company = company_services.found_company(self.boss.pk, "matrix", "Mina", 0).detail["company"]
        self.assertTrue(company_services.fund_company(self.boss.pk, company, 2_000_000).ok)
        rural = list(Lot.objects.filter(category="rural").order_by("pk"))[:n]
        for lot in rural:
            self.own(lot, "company", company, self.boss)
        return company, rural

    def test_one_company_located_on_two_lots_at_once_keeps_exactly_one_location(self):
        company, (a, b) = self.matrix_with_lots()
        jobs = run_together(lambda: self.sites.set_company_location(self.boss.pk, {"company": company, "lot": a.pk}),
                            lambda: self.sites.set_company_location(self.boss.pk, {"company": company, "lot": b.pk}))
        self.assertTrue(all(j.result.ok for j in jobs), [j.result for j in jobs])
        from properties.models import CompanyLocation
        self.assertEqual(CompanyLocation.objects.filter(company_id=company).count(), 1)
        occupied = Lot.objects.filter(pk__in=[a.pk, b.pk], occupation="occupied").values_list("pk", flat=True)
        self.assertEqual(list(occupied), [CompanyLocation.objects.get().lot_id])
        self.assertClean()

    def test_the_same_location_requested_many_times_at_once_succeeds_once(self):
        company, (a, _) = self.matrix_with_lots()
        jobs = run_together(*[lambda: self.sites.set_company_location(self.boss.pk, {"company": company, "lot": a.pk}) for _ in range(4)])
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 1, [j.result for j in jobs])
        self.assertEqual({j.result.code for j in jobs if not j.result.ok}, {"ALREADY_LOCATED_HERE"})
        self.assertClean()

    @CROSS_ROW
    def test_selling_the_lot_versus_locating_on_it_leaves_no_location_of_a_non_owner(self):
        company, (a, _) = self.matrix_with_lots()
        li = services.list_property(self.boss.pk, a.pk, self.company_ref(company), 9_000).detail["listing"]
        jobs = run_together(lambda: services.buy_property(self.third.pk, li, self.player_ref(self.third)),
                            lambda: self.sites.set_company_location(self.boss.pk, {"company": company, "lot": a.pk}))
        from properties.models import CompanyLocation
        self.assertEqual(CompanyLocation.objects.filter(lot=a).count(), 0)           # com o lote vendido, ninguém fica localizado nele
        self.assertEqual(Lot.objects.get(pk=a.pk).occupation, "empty")
        self.assertClean()
