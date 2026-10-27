"""Localização de empresas e terreno da Matriz (10 §29; 02 §2.1; 08 §8, §9, §12): lote próprio, uso exigido pelo zoneamento, terreno pelos depósitos."""
from contextlib import contextmanager
from decimal import Decimal as D

from catalog.constants import Sector
from companies import production
from companies import services as company_services
from companies.constants import CompanyType
from companies.models import ProductionLine
from geography import zoning
from geography.constants import Category, Occupation
from geography.models import Lot, ResourceDeposit
from ledger import services as ledger
from ledger.tests.base import fund_account
from players import registry
from properties import params, services, sites
from properties.audit import audit_properties
from properties.models import CompanyLocation, LotTitle

from .base import PropertiesBase


class SitesBase(PropertiesBase):
    def setUp(self):
        super().setUp()
        fund_account(ledger.player_account(self.boss.pk), 50_000_000)          # fundar empresas e arrematar lotes custam dinheiro de verdade
        self.matrix = self.found(self.boss, "matrix", "Mina Alfa", 0)

    def rural(self, n=0, deposits=()):
        """Lote rural SEM depósito natural (o gerador sorteia alguns): os depósitos de cada teste são explícitos."""
        lot = self.lot("rural", n)
        ResourceDeposit.objects.filter(lot=lot).delete()
        for resource in deposits:
            ResourceDeposit.objects.create(lot=lot, resource=resource, richness="0.500")
        return lot

    def own(self, lot, company, price=1_000):
        """A empresa arremata o lote no leilão (o Dono a financia antes)."""
        self.assertTrue(company_services.fund_company(self.boss.pk, company, (price + lot.pk) * 2).ok)
        self.sold_to(self.boss, lot, price=price + lot.pk, party=self.company_ref(company))
        return lot

    def locate(self, company, lot, player=None):
        return sites.set_company_location((player or self.boss).pk, {"company": company, "lot": lot.pk if lot is not None else None})

    def audit_codes(self):
        return {f["code"] for f in audit_properties().findings}

    def row(self):
        return CompanyLocation.objects.get()


class LocationTests(SitesBase):
    def test_the_lot_view_shows_which_company_operates_there(self):
        lot = self.own(self.rural(0, ["iron"]), self.matrix)
        self.assertIsNone(services.lot_view(lot.pk)["company"])
        self.assertTrue(self.locate(self.matrix, lot).ok)
        self.assertEqual(services.lot_view(lot.pk)["company"], self.matrix)
        self.assertTrue(self.locate(self.matrix, None).ok)
        self.assertIsNone(services.lot_view(lot.pk)["company"])

    def test_the_company_locates_on_its_own_lot_with_the_use_its_type_requires(self):
        lot = self.own(self.rural(0, ["iron"]), self.matrix)
        res = self.locate(self.matrix, lot)
        self.assertTrue(res.ok, res)
        row = self.row()
        self.assertEqual((row.company_id, row.lot_id, row.since), (self.matrix, lot.pk, self.clk.now()))
        self.assertEqual(Lot.objects.get(pk=lot.pk).occupation, Occupation.OCCUPIED.value)
        self.assertEqual(sites.location_view(self.matrix)["deposit_products"], ["iron"])

    def test_each_type_uses_the_lot_category_the_design_gives_it(self):
        cases = {"matrix": "rural", "industrial": "industrial", "retail": "commercial", "services": "commercial"}
        for n, (ctype, category) in enumerate(cases.items()):
            company = self.found(self.boss, ctype, f"E{n}", 0)
            wrong = self.own(self.lot("residential", n + 1), company)
            self.assertEqual(self.locate(company, wrong).code, "LOT_USE_NOT_ALLOWED", ctype)
            right = self.own(self.lot(category, {"matrix": 5, "industrial": 1, "retail": 1, "services": 2}[ctype]), company)
            self.assertTrue(self.locate(company, right).ok, ctype)
        self.assertEqual(CompanyLocation.objects.count(), 4)

    def test_construction_and_financial_companies_have_no_location_in_the_design(self):
        for n, ctype in enumerate(("construction", "financial")):
            company = self.found(self.boss, ctype, f"X{ctype}", 0)
            lot = self.own(self.lot("commercial", 3 + n), company)
            self.assertEqual(self.locate(company, lot).code, "COMPANY_TYPE_NOT_LOCATED", ctype)
        self.assertEqual(CompanyLocation.objects.count(), 0)

    def test_refusals(self):
        lot = self.rural(0)
        L = lambda company=None, lot_id=None, player=None: sites.set_company_location(
            (player or self.boss).pk, {"company": company or self.matrix, "lot": lot_id if lot_id is not None else lot.pk})
        self.assertEqual(sites.set_company_location(10 ** 9, {"company": self.matrix, "lot": lot.pk}).code, "PLAYER_NOT_FOUND")
        self.assertEqual(sites.set_company_location(self.boss.pk, {"company": self.matrix}).code, "INVALID_PARAMS")
        self.assertEqual(sites.set_company_location(self.boss.pk, {"company": "x", "lot": 1}).code, "INVALID_PARAMS")
        self.assertEqual(L(company=10 ** 9).code, "COMPANY_NOT_FOUND")
        self.assertEqual(L(player=self.third).code, "NOT_OWNER")
        self.assertEqual(L(lot_id=10 ** 9).code, "LOT_NOT_FOUND")
        self.assertEqual(L().code, "LOT_NOT_OWNED_BY_COMPANY")                       # lote do governo
        self.assertEqual(sites.set_company_location(self.boss.pk, {"company": self.matrix, "lot": None}).code, "NOT_LOCATED")
        self.assertEqual(CompanyLocation.objects.count(), 0)

    def test_the_lot_must_belong_to_the_company_not_to_its_owner_or_to_another_company(self):
        lot = self.rural(0)
        self.sold_to(self.boss, lot, price=2_000, party=self.player_ref(self.boss))
        self.assertEqual(self.locate(self.matrix, lot).code, "LOT_NOT_OWNED_BY_COMPANY")
        other = self.found(self.boss, "matrix", "Outra", 0)
        lot2 = self.own(self.rural(1), other)
        self.assertEqual(self.locate(self.matrix, lot2).code, "LOT_NOT_OWNED_BY_COMPANY")

    def test_one_company_per_lot_and_one_lot_per_company_moving_frees_the_old_one(self):
        a, b = self.own(self.rural(0), self.matrix), self.own(self.rural(1), self.matrix)
        self.assertTrue(self.locate(self.matrix, a).ok)
        self.assertEqual(self.locate(self.matrix, a).code, "ALREADY_LOCATED_HERE")
        other = self.found(self.boss, "matrix", "Outra", 0)
        self.assertEqual(sites.location_refusal(self.boss.pk, {"company": other, "lot": a.pk}).code, "LOT_NOT_OWNED_BY_COMPANY")
        res = self.locate(self.matrix, b)                                           # muda de lote
        self.assertEqual((res.ok, res.detail["left"]), (True, a.pk))
        self.assertEqual(self.row().lot_id, b.pk)
        self.assertEqual([Lot.objects.get(pk=x.pk).occupation for x in (a, b)], ["empty", "occupied"])

    def test_leaving_the_lot_frees_it(self):
        lot = self.own(self.rural(0), self.matrix)
        self.assertTrue(self.locate(self.matrix, lot).ok)
        res = self.locate(self.matrix, None)
        self.assertEqual((res.ok, res.detail["left"]), (True, lot.pk))
        self.assertEqual((CompanyLocation.objects.count(), Lot.objects.get(pk=lot.pk).occupation), (0, "empty"))

    def test_a_lot_with_a_residential_building_or_for_sale_or_under_construction_is_not_available(self):
        house = self.built(company=self.build)
        self.assertEqual(sites.location_refusal(self.boss.pk, {"company": self.build, "lot": house.lot_id}).code, "COMPANY_TYPE_NOT_LOCATED")
        retail = self.found(self.boss, "retail", "Loja", 0)
        lot = self.own(self.lot("commercial", 0), retail)
        listing = services.list_property(self.boss.pk, lot.pk, self.company_ref(retail), 9_000).detail["listing"]
        self.assertEqual(self.locate(retail, lot).code, "LOT_RESERVED")
        self.assertTrue(services.unlist_property(self.boss.pk, listing, self.company_ref(retail)).ok)
        self.assertTrue(self.locate(retail, lot).ok)

    def test_a_residential_building_blocks_the_lot_even_where_zoning_allows_the_use(self):
        retail = self.found(self.boss, "retail", "Loja", 0)
        self.assertTrue(company_services.fund_company(self.boss.pk, retail, 10_000).ok)
        house = self.built(company=retail)
        with self._zoning_allows(Category.COMMERCIAL):
            self.assertEqual(self.locate(retail, Lot.objects.get(pk=house.lot_id)).code, "LOT_HAS_BUILDING")

    @contextmanager
    def _zoning_allows(self, use):
        zoning.register_zoning_override("test_mix", lambda lot, u: True if u is use else None)
        try:
            yield
        finally:
            zoning.unregister_zoning_override("test_mix")

    def test_zoning_decides_and_a_law_override_is_respected(self):
        retail = self.found(self.boss, "retail", "Loja", 0)
        lot = self.own(self.lot("residential", 3), retail)
        self.assertEqual(self.locate(retail, lot).code, "LOT_USE_NOT_ALLOWED")
        with self._zoning_allows(Category.COMMERCIAL):
            self.assertTrue(self.locate(retail, lot).ok)

    def test_the_registry_exposes_the_same_refusals(self):
        lot = self.own(self.rural(0), self.matrix)
        target = {"company": self.matrix, "lot": lot.pk}
        self.assertTrue(registry.check_action(self.boss.pk, "set_company_location", target).available)
        self.assertEqual(registry.check_action(self.third.pk, "set_company_location", target).code, "NOT_OWNER")
        self.assertEqual(registry.check_action(self.boss.pk, "set_company_location", {"company": self.matrix}).code, "INVALID_PARAMS")
        res = registry.execute_action(self.boss.pk, "set_company_location", target)
        self.assertTrue(res.ok, res)
        self.assertEqual(registry.check_action(self.boss.pk, "set_company_location", target).code, "ALREADY_LOCATED_HERE")


class SaleEndsLocationTests(SitesBase):
    def test_selling_the_lot_ends_the_location_and_frees_the_lot(self):
        lot = self.own(self.rural(0, ["iron"]), self.matrix)
        self.assertTrue(self.locate(self.matrix, lot).ok)
        li = services.list_property(self.boss.pk, lot.pk, self.company_ref(self.matrix), 9_000)
        self.assertEqual(li.code, "OK")
        res = services.buy_property(self.third.pk, li.detail["listing"], self.player_ref(self.third))
        self.assertTrue(res.ok, res)
        self.assertEqual(res.detail["company_location_dropped"], self.matrix)
        self.assertEqual((CompanyLocation.objects.count(), Lot.objects.get(pk=lot.pk).occupation), (0, "empty"))
        self.assertEqual(sites.terrain_categories(self.matrix), None)

    def test_a_sale_of_another_lot_leaves_the_location_alone(self):
        a, b = self.own(self.rural(0), self.matrix), self.own(self.rural(1), self.matrix)
        self.assertTrue(self.locate(self.matrix, a).ok)
        li = services.list_property(self.boss.pk, b.pk, self.company_ref(self.matrix), 9_000).detail["listing"]
        res = services.buy_property(self.third.pk, li, self.player_ref(self.third))
        self.assertNotIn("company_location_dropped", res.detail)
        self.assertEqual(self.row().lot_id, a.pk)


class TerrainTests(SitesBase):
    def located(self, deposits):
        lot = self.own(self.rural(0, deposits), self.matrix)
        self.assertTrue(self.locate(self.matrix, lot).ok)
        return lot

    def test_a_matrix_without_a_lot_has_no_terrain(self):
        self.assertEqual(production.set_production(self.boss.pk, self.matrix, "iron").code, "MATRIX_SITE_UNDEFINED")

    def produce(self, key):
        return production.set_production(self.boss.pk, self.matrix, key)

    def test_a_rural_lot_without_deposit_sustains_agro_and_common_extractive_products_provisional_rule_a(self):
        self.located([])
        self.assertEqual(sites.terrain_categories(self.matrix), frozenset({Sector.AGRO, Sector.EXTRACTIVE}))
        res = self.produce("wood")                                                  # extrativismo comum, sem depósito
        self.assertTrue(res.ok, res)
        view = sites.location_view(self.matrix)
        self.assertTrue(view["terrain_defined"])
        self.assertEqual((view["terrain"]["rule"], view["terrain"]["provisional"]), ("G12-A-PROV", True))

    def test_no_deposit_never_sustains_oil_or_minerals(self):
        self.located([])
        terrain = sites.terrain_of(self.matrix_lot())
        for key in ("oil", "iron", "gold", "diamond"):
            self.assertNotIn(key, terrain.products, key)
            self.assertEqual(self.produce(key).code, "PRODUCT_OUTSIDE_TERRAIN_CATEGORY" if key != "oil" else "PRODUCT_NOT_IN_TERRAIN", key)
        for key in ("wheat", "meat", "wood", "sand", "rubber"):
            self.assertIn(key, terrain.products, key)

    def matrix_lot(self):
        return CompanyLocation.objects.get(company_id=self.matrix).lot_id

    def test_a_mineral_deposit_adds_that_mineral_and_keeps_the_common_products_by_default(self):
        self.located(["iron", "coal"])
        self.assertEqual(sites.terrain_categories(self.matrix), frozenset({Sector.MINING, Sector.AGRO, Sector.EXTRACTIVE}))
        self.assertEqual(self.produce("gold").code, "PRODUCT_NOT_IN_TERRAIN")             # mineral de OUTRO depósito: nunca
        self.assertEqual(self.produce("oil").code, "PRODUCT_NOT_IN_TERRAIN")
        self.assertTrue(self.produce("iron").ok)

    def test_oil_deposit_adds_oil_as_extractive_never_mining(self):
        self.located(["oil"])
        terrain = sites.terrain_of(self.matrix_lot())
        self.assertIn("oil", terrain.products)
        self.assertNotIn(Sector.MINING, terrain.categories)
        self.assertEqual(self.produce("iron").code, "PRODUCT_OUTSIDE_TERRAIN_CATEGORY")
        self.assertTrue(self.produce("oil").ok)

    def test_with_the_provisional_switch_off_a_deposit_lot_sustains_only_its_deposits(self):
        from unittest import mock
        self.located(["iron"])
        with mock.patch.object(params, "DEPOSIT_LOTS_ALSO_COMMON", False):
            self.assertEqual(sites.terrain_categories(self.matrix), frozenset({Sector.MINING}))
            self.assertEqual(self.produce("wheat").code, "PRODUCT_OUTSIDE_TERRAIN_CATEGORY")
            self.assertFalse(sites.terrain_of(self.matrix_lot()).why["common_allowed"])
            self.assertTrue(self.produce("iron").ok)

    def test_the_switch_never_affects_a_lot_without_deposit(self):
        from unittest import mock
        self.located([])
        with mock.patch.object(params, "DEPOSIT_LOTS_ALSO_COMMON", False):
            self.assertIn("wheat", sites.terrain_of(self.matrix_lot()).products)

    def test_the_terrain_is_replaceable_in_a_single_point_without_touching_the_consumers(self):
        from unittest import mock
        self.located([])
        fake = sites.Terrain(products=frozenset({"stone"}), common=frozenset(), deposits=frozenset(), rule="TEST-B", why={"rule": "TEST-B"})
        with mock.patch.object(sites, "terrain_of", return_value=fake):
            self.assertEqual(sites.terrain_products(self.matrix), frozenset({"stone"}))
            self.assertEqual(self.produce("wheat").code, "PRODUCT_OUTSIDE_TERRAIN_CATEGORY")
            self.assertEqual(self.produce("wood").code, "PRODUCT_NOT_IN_TERRAIN")             # mesma categoria (Extrativismo), fora do terreno
            self.assertTrue(self.produce("stone").ok)

    def test_the_terrain_provider_may_still_report_an_undefined_type_to_production(self):
        """A recusa `TERRAIN_TYPE_UNDEFINED` do `companies.production` continua para provedores que não saibam o tipo (ex.: a opção B sem dado)."""
        self.located([])
        fake = sites.Terrain(products=frozenset(), common=frozenset(), deposits=frozenset(), rule="TEST-B", why={})
        from unittest import mock
        with mock.patch.object(sites, "terrain_of", return_value=fake):
            self.assertEqual(self.produce("wheat").code, "TERRAIN_TYPE_UNDEFINED")

    def test_every_resource_is_the_product_of_the_matching_sector_so_the_deposit_key_is_the_product_key(self):
        from catalog import services as catalog
        from geography.constants import RESOURCE_KIND, Resource, ResourceKind
        for r in Resource:
            expected = Sector.EXTRACTIVE if RESOURCE_KIND[r] is ResourceKind.EXTRACTIVE else Sector.MINING
            self.assertEqual(catalog.producer_sector_of(r.value), expected, r.value)

    def test_other_company_types_have_no_terrain(self):
        retail = self.found(self.boss, "retail", "Loja", 0)
        lot = self.own(self.lot("commercial", 0), retail)
        self.assertTrue(self.locate(retail, lot).ok)
        self.assertIsNone(sites.terrain_categories(retail))
        self.assertIsNone(sites.terrain_products(retail))

    def energy_of(self, player):
        from players.models import Player
        return Player.objects.get(pk=player.pk).energy

    def test_the_work_of_a_matrix_checks_the_terrain_and_stops_when_it_is_lost(self):
        self.located(["iron"])
        self.assertTrue(production.set_production(self.boss.pk, self.matrix, "iron").ok)
        miner = self.new_player("miner")
        self.hire(miner, company=self.matrix, salary=1_000)
        first = self.hook(miner)
        self.assertGreaterEqual(first["produced"], 0)
        self.assertNotIn("COMPANY_SITE_INVALID", first["limited_by"])
        lot_id = self.row().lot_id
        li = services.list_property(self.boss.pk, lot_id, self.company_ref(self.matrix), 9_000).detail["listing"]
        self.assertTrue(services.buy_property(self.third.pk, li, self.player_ref(self.third)).ok)        # perde o terreno
        self.set_state(miner, energy=D(100), nutrition=D(100), health=D(100), burnout=D(0), hospitalized_until=None, health_critical=False)
        blocked = registry.execute_action(miner.pk, "work", None)
        self.assertEqual((blocked.ok, blocked.code, blocked.detail["reasons"]), (False, "COMPANY_SITE_INVALID", ["COMPANY_SITE_INVALID"]))
        self.assertEqual(self.energy_of(miner), D(100))                                   # bloqueado ANTES de gastar Energia


class AuditTests(SitesBase):
    audit_properties_at_end = False

    def prepared(self):
        lot = self.own(self.rural(0, ["iron"]), self.matrix)
        self.assertTrue(self.locate(self.matrix, lot).ok)
        return lot

    def test_clean_with_locations_and_after_a_sale(self):
        self.prepared()
        self.assertEqual(self.audit_codes(), set())
        self.assertEqual(audit_properties().stats["company_locations"], 1)

    def test_the_lot_owner_must_be_the_company(self):
        lot = self.prepared()
        LotTitle.objects.filter(lot_id=lot.pk).update(owner_kind="player", owner_id=self.third.pk)
        self.assertIn("LOCATION_LOT_NOT_OWNED_BY_COMPANY", self.audit_codes())

    def test_a_located_lot_must_be_occupied(self):
        lot = self.prepared()
        Lot.objects.filter(pk=lot.pk).update(occupation="empty")
        self.assertIn("LOCATION_LOT_NOT_OCCUPIED", self.audit_codes())

    def test_a_non_locatable_company_type_is_found(self):
        lot = self.prepared()
        from companies.models import Company
        Company.objects.filter(pk=self.matrix).update(type=CompanyType.FINANCIAL.value)
        self.assertIn("LOCATED_COMPANY_TYPE_NOT_LOCATABLE", self.audit_codes())

    def test_a_residential_building_on_a_located_lot_is_found(self):
        lot = self.prepared()
        from properties.models import Building
        Building.objects.create(lot=lot, kind="low_density_simple", units=1, qol_bonus=0, completed_at=0)
        self.assertIn("LOCATION_LOT_HAS_BUILDING", self.audit_codes())
