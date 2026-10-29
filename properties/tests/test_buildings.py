"""Prédios comerciais e industrial (G5, GD 2026-10-29): empresa de N estrelas precisa de prédio de nível ≥ N; uma empresa por prédio; industrial único sem nível."""
from unittest import mock

from django.db import IntegrityError, transaction

from companies import gates, production
from companies.models import Company, ProductionLine
from geography.constants import Occupation
from geography.models import Lot
from properties import params, services, sites
from properties.models import Building, CompanyLocation

from .test_sites import SitesBase


class BuildingLocationBase(SitesBase):
    require_building = True
    def setUp(self):
        super().setUp()
        self.lot_counter = {"commercial": 0, "industrial": 0}

    def building_for(self, company, kind):
        """Lote da categoria do prédio, da empresa, com o prédio pronto (a obra em si é testada em test_site)."""
        k = params.BUILDING_TYPES[kind]
        category = params.FAMILY_USE[k.family].value
        n = self.lot_counter[category]
        self.lot_counter[category] += 1
        lot = self.own(self.lot(category, n), company)
        Building.objects.create(lot=lot, kind=k.key, family=k.family.value, level=k.level, units=k.units, qol_bonus=k.qol_bonus, completed_at=self.clk.now())
        Lot.objects.filter(pk=lot.pk).update(occupation=Occupation.OCCUPIED.value)
        return lot

    def stars(self, company, n):
        Company.objects.filter(pk=company).update(stars=n)


class CommercialLevelTests(BuildingLocationBase):
    def setUp(self):
        super().setUp()
        self.retail = self.found(self.boss, "retail", "Loja", 0)

    def test_the_company_needs_a_building_level_at_least_its_stars(self):
        self.stars(self.retail, 3)
        low = self.building_for(self.retail, "commercial_2")
        res = self.locate(self.retail, low)
        self.assertEqual((res.code, res.detail["level"], res.detail["stars"]), ("BUILDING_LEVEL_TOO_LOW", 2, 3))
        self.assertEqual(CompanyLocation.objects.count(), 0)
        exact = self.building_for(self.retail, "commercial_3")
        self.assertTrue(self.locate(self.retail, exact).ok)

    def test_a_higher_level_building_is_fine(self):
        self.stars(self.retail, 1)
        lot = self.building_for(self.retail, "commercial_5")
        self.assertTrue(self.locate(self.retail, lot).ok)
        self.assertEqual(sites.location_view(self.retail)["building"], {"kind": "commercial_5", "family": "commercial", "level": 5})

    def test_each_level_is_the_boundary_for_the_same_stars(self):
        for stars in range(1, 6):
            self.stars(self.retail, stars)
            for level in range(1, 6):
                refusal = sites.building_refusal(Company.objects.get(pk=self.retail), Building(kind=f"commercial_{level}", family="commercial", level=level), 1)
                self.assertEqual(refusal is None, level >= stars, (stars, level))

    def test_services_follow_the_same_commercial_rule(self):
        services_co = self.found(self.boss, "services", "Serv", 0)
        self.stars(services_co, 2)
        self.assertEqual(self.locate(services_co, self.building_for(services_co, "commercial_1")).code, "BUILDING_LEVEL_TOO_LOW")
        self.assertTrue(self.locate(services_co, self.building_for(services_co, "commercial_2")).ok)

    def test_without_a_building_the_location_is_refused_when_required_and_allowed_when_not(self):
        self.audit_properties_at_end = False                      # a localização feita com o requisito desligado é achado quando ele volta a valer (de propósito)
        lot = self.own(self.lot("commercial", 0), self.retail)
        res = self.locate(self.retail, lot)
        self.assertEqual((res.code, res.detail["family"]), ("BUILDING_REQUIRED", "commercial"))
        with mock.patch.object(params, "REQUIRE_BUILDING_FOR_LOCATION", False):
            self.assertTrue(self.locate(self.retail, lot).ok)
            self.assertEqual(self.audit_codes(), set())
        self.assertIn("LOCATED_COMPANY_WITHOUT_BUILDING", self.audit_codes())

    def test_the_use_is_still_checked_before_the_building_requirement(self):
        wrong = self.own(self.lot("residential", 2), self.retail)
        self.assertEqual(self.locate(self.retail, wrong).code, "LOT_USE_NOT_ALLOWED")

    def test_a_building_of_another_family_is_refused(self):
        lot = self.building_for(self.retail, "commercial_1")
        industrial = self.found(self.boss, "industrial", "Fab", 0)
        other = self.own(self.lot("industrial", 1), industrial)
        self.assertEqual(sites.location_refusal(self.boss.pk, {"company": industrial, "lot": lot.pk}).code, "LOT_NOT_OWNED_BY_COMPANY")
        house = self.built(company=self.retail)
        self.assertEqual(self.locate(self.retail, Lot.objects.get(pk=house.lot_id)).code, "LOT_HAS_BUILDING")
        self.assertIsNotNone(other)

    def test_one_company_per_building_by_rule_and_by_the_database(self):
        lot = self.building_for(self.retail, "commercial_1")
        self.assertTrue(self.locate(self.retail, lot).ok)
        self.assertEqual(self.locate(self.retail, lot).code, "ALREADY_LOCATED_HERE")
        other = self.found(self.boss, "retail", "Outra", 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CompanyLocation.objects.create(company_id=other, lot_id=lot.pk, since=0)

    def test_stars_allowed_tells_the_stars_progression_whether_the_building_holds(self):
        self.stars(self.retail, 2)
        self.assertIsNone(sites.stars_allowed(self.retail, 5))                                        # sem local: não há o que checar
        lot = self.building_for(self.retail, "commercial_3")
        self.assertTrue(self.locate(self.retail, lot).ok)
        self.assertIsNone(sites.stars_allowed(self.retail, 3))
        res = sites.stars_allowed(self.retail, 4)
        self.assertEqual((res.code, res.detail["level"], res.detail["stars"]), ("BUILDING_LEVEL_TOO_LOW", 3, 4))

    def test_selling_the_building_ends_the_location(self):
        lot = self.building_for(self.retail, "commercial_1")
        self.assertTrue(self.locate(self.retail, lot).ok)
        li = services.list_property(self.boss.pk, lot.pk, self.company_ref(self.retail), 9_000).detail["listing"]
        res = services.buy_property(self.worker.pk, li, self.player_ref(self.worker))
        self.assertTrue(res.ok, res)
        self.assertEqual(CompanyLocation.objects.count(), 0)
        self.assertEqual(Lot.objects.get(pk=lot.pk).occupation, Occupation.OCCUPIED.value)               # o prédio continua ocupando o lote

    def test_leaving_a_building_keeps_the_lot_occupied_by_the_building(self):
        lot = self.building_for(self.retail, "commercial_1")
        self.assertTrue(self.locate(self.retail, lot).ok)
        self.assertTrue(self.locate(self.retail, None).ok)
        self.assertEqual(Lot.objects.get(pk=lot.pk).occupation, Occupation.OCCUPIED.value)


class IndustrialBuildingTests(BuildingLocationBase):
    def setUp(self):
        super().setUp()
        self.factory = self.found(self.boss, "industrial", "Fab", 0)

    def test_the_industrial_building_has_no_level_any_star_fits(self):
        for stars in (1, 5):
            self.stars(self.factory, stars)
            refusal = sites.building_refusal(Company.objects.get(pk=self.factory), Building(kind="industrial", family="industrial", level=None), 1)
            self.assertIsNone(refusal, stars)
        lot = self.building_for(self.factory, "industrial")
        self.assertTrue(self.locate(self.factory, lot).ok)

    def test_an_industrial_company_cannot_use_a_commercial_building_nor_the_reverse(self):
        lot = self.building_for(self.factory, "commercial_5")
        self.assertEqual(self.locate(self.factory, lot).code, "LOT_HAS_BUILDING")
        retail = self.found(self.boss, "retail", "Loja", 0)
        ind = self.building_for(retail, "industrial")
        self.assertEqual(self.locate(retail, ind).code, "LOT_HAS_BUILDING")

    def test_matrix_construction_and_financial_do_not_use_buildings(self):
        lot = self.own(self.rural(0), self.matrix)
        self.assertTrue(self.locate(self.matrix, lot).ok)                                              # a Matriz segue só com o lote rural
        for n, ctype in enumerate(("construction", "financial")):
            company = self.found(self.boss, ctype, f"X{ctype}", 0)
            self.assertEqual(self.locate(company, self.own(self.lot("industrial", n), company)).code, "COMPANY_TYPE_NOT_LOCATED")


class OperationGateTests(BuildingLocationBase):
    """`REQUIRE_LOCATION_TO_OPERATE`: desligado por padrão; ligado, vender e produzir exigem empresa localizada no prédio certo."""

    def on(self):
        patcher = mock.patch.object(params, "REQUIRE_LOCATION_TO_OPERATE", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_it_is_off_by_default_and_nothing_is_required(self):
        self.assertFalse(params.REQUIRE_LOCATION_TO_OPERATE)
        retail = self.found(self.boss, "retail", "Loja", 0)
        self.assertIsNone(gates.operation_refusal(Company.objects.get(pk=retail)))

    def test_retail_must_be_located_in_a_building_of_enough_level(self):
        from companies import retail as retail_ops
        self.on()
        self.audit_properties_at_end = False                      # a estrela sobe sem o prédio acompanhar: é o achado que a auditoria deve dar (testado em AuditBuildingTests)
        company = self.found(self.boss, "retail", "Loja", 0)
        self.assertEqual(retail_ops.sale_refusal(company, "zzz", 1).code, "COMPANY_NOT_LOCATED")
        self.stars(company, 2)
        lot = self.building_for(company, "commercial_2")
        self.assertTrue(self.locate(company, lot).ok)
        self.assertEqual(retail_ops.sale_refusal(company, "zzz", 1).code, "UNKNOWN_PRODUCT")           # passou da porta
        Company.objects.filter(pk=company).update(stars=3)                                              # subiu de estrela: o prédio não segura
        self.assertEqual(retail_ops.sale_refusal(company, "zzz", 1).code, "BUILDING_LEVEL_TOO_LOW")

    def test_industrial_work_is_blocked_without_the_building(self):
        self.on()
        factory = self.found(self.boss, "industrial", "Fab", 0)
        from catalog import services as catalog
        ProductionLine.objects.update_or_create(company_id=factory, defaults={"product": catalog.get_product("cement"), "setup_until": None})
        job = type("J", (), {})()
        job.company_id, job.company = factory, Company.objects.get(pk=factory)
        self.assertEqual(production.work_refusal(job, self.clk.now()), "COMPANY_NOT_LOCATED")
        lot = self.building_for(factory, "industrial")
        self.assertTrue(self.locate(factory, lot).ok)
        self.assertNotEqual(production.work_refusal(job, self.clk.now()), "COMPANY_NOT_LOCATED")

    def test_the_matrix_and_other_types_are_not_gated_by_this_rule(self):
        self.on()
        for ctype in ("matrix", "construction", "financial"):
            company = self.found(self.boss, ctype, f"G{ctype}", 0)
            self.assertIsNone(gates.operation_refusal(Company.objects.get(pk=company)), ctype)

    def test_a_duplicate_gate_is_an_error(self):
        with self.assertRaises(ValueError):
            gates.register_operation_gate(sites.PROVIDER_NAME, lambda c: None)


class AuditBuildingTests(BuildingLocationBase):
    def test_the_audit_flags_a_located_company_whose_building_cannot_hold_it(self):
        retail = self.found(self.boss, "retail", "Loja", 0)
        lot = self.building_for(retail, "commercial_1")
        self.assertTrue(self.locate(retail, lot).ok)
        self.assertEqual(self.audit_codes(), set())
        self.stars(retail, 4)                                                                           # estrela subiu sem o prédio acompanhar (P1.04f usaria stars_allowed)
        self.assertIn("LOCATED_COMPANY_BUILDING_LEVEL_TOO_LOW", self.audit_codes())
        self.stars(retail, 1)
        Building.objects.filter(lot=lot).delete()
        self.assertIn("LOCATED_COMPANY_WITHOUT_BUILDING", self.audit_codes())
        Lot.objects.filter(pk=lot.pk).update(occupation=Occupation.OCCUPIED.value)
        CompanyLocation.objects.all().delete()

    def test_the_audit_flags_a_building_that_does_not_match_its_type(self):
        retail = self.found(self.boss, "retail", "Loja", 0)
        lot = self.building_for(retail, "commercial_2")
        Building.objects.filter(lot=lot).update(level=4)
        self.assertIn("BUILDING_DOES_NOT_MATCH_TYPE", self.audit_codes())
        Building.objects.filter(lot=lot).update(level=2)

    def test_the_database_refuses_a_malformed_building(self):
        retail = self.found(self.boss, "retail", "Loja", 0)
        lot = self.own(self.lot("commercial", 0), retail)
        bad = [dict(family="commercial", level=None, units=0), dict(family="commercial", level=2, units=3), dict(family="industrial", level=1, units=0),
               dict(family="residential", level=None, units=0), dict(family="residential", level=2, units=1)]
        for fields in bad:
            with self.assertRaises(IntegrityError, msg=str(fields)), transaction.atomic():
                Building.objects.create(lot=lot, kind="x", qol_bonus=0, completed_at=0, **fields)
