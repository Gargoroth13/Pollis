"""Moradia (10 §6.1, §14-15; 05 §8): unidades, residência ativa, direito de morar, moradia inicial e QoL do imóvel."""
from decimal import Decimal

from geography.models import Lot
from players import qol, registry
from properties import housing, params, services
from properties.audit import audit_properties
from properties.models import ActiveResidence, Building, Unit

from .base import PropertiesBase

D = Decimal


class HousingBase(PropertiesBase):
    def setUp(self):
        super().setUp()
        self.ensure_qol_provider()
        self.house = self.built(self.worker, kind="high_density_simple")        # o worker é dono de um prédio de 20 unidades
        self.u1, self.u2 = self.unit(self.house, 1), self.unit(self.house, 2)

    def qol_steps(self, player):
        base = qol.qol_base(player, self.clk.now())
        return {s.key: s.amount for s in base.steps}


class UnitTests(HousingBase):
    def test_a_building_has_one_unit_per_capacity_slot_and_the_construction_creates_them(self):
        self.assertEqual(Unit.objects.filter(building=self.house).count(), 20)
        self.assertEqual(list(Unit.objects.filter(building=self.house).values_list("index", flat=True)), list(range(1, 21)))
        small = self.built(self.third, kind="low_density_simple")
        self.assertEqual(Unit.objects.filter(building=small).count(), 1)
        self.assertEqual(services.lot_view(self.house.lot_id)["units"], list(Unit.objects.filter(building=self.house).values_list("pk", flat=True)))

    def test_the_real_construction_flow_creates_the_units(self):
        from companies import construction
        from properties.tests.test_site import SiteBase  # noqa: F401  (o fluxo completo é provado lá; aqui só a contagem)
        lot = self.lot(n=-14)
        self.sold_to(self.boss, lot, price=2_000, party=self.company_ref(self.build))
        self.assertTrue(construction.start_construction(self.boss.pk, self.build, "low_density_simple", lot.pk).ok)
        from companies.models import ConstructionJob
        from decimal import Decimal as Dec
        ConstructionJob.objects.filter(status="active").update(progress=Dec(99))
        self.audit_companies_at_end = False
        self.set_skill(self.mason, "physical", 100)
        for _ in range(60):
            res = self.builder_work()
            if res.detail["hooks"][construction.ACTION_HOOK]["completed"]:
                break
        self.assertEqual(Unit.objects.filter(building__lot=lot).count(), 1)


class ResidenceTests(HousingBase):
    def test_the_initial_housing_is_the_absence_of_a_residence_and_is_neutral(self):
        self.assertEqual(housing.residence_view(self.third.pk), {"housing": "initial", "unit": None, "qol_bonus": "0"})
        self.assertNotIn(housing.PROVIDER_NAME, self.qol_steps(self.third))
        self.assertEqual(ActiveResidence.objects.count(), 0)

    def test_the_owner_moves_into_his_own_unit_and_the_building_adds_to_the_qol_base(self):
        res = housing.set_residence(self.worker.pk, self.u1.pk)
        self.assertTrue(res.ok, res)
        self.assertEqual(self.qol_steps(self.worker)[housing.PROVIDER_NAME], D("0.1"))                 # alta densidade simples: +0,1
        view = housing.residence_view(self.worker.pk)
        self.assertEqual((view["housing"], view["unit"], view["kind"], view["qol_bonus"]), ("unit", self.u1.pk, "high_density_simple", "0.10"))
        base = qol.qol_base(self.worker, self.clk.now())
        self.assertEqual(base.value, D("0.5") + D("0.1"))

    def test_each_building_type_adds_its_own_bonus(self):
        for kind, bonus in (("low_density_luxury", D("0.3")), ("high_density_luxury", D("0.4")), ("low_density_simple", D("0"))):
            house = self.built(self.third, kind=kind)
            self.assertTrue(housing.set_residence(self.third.pk, self.unit(house).pk).ok)
            self.assertEqual(self.qol_steps(self.third).get(housing.PROVIDER_NAME, D("0")), bonus, kind)

    def test_moving_changes_the_unit_and_null_returns_to_the_initial_housing(self):
        self.assertTrue(housing.set_residence(self.worker.pk, self.u1.pk).ok)
        self.assertTrue(housing.set_residence(self.worker.pk, self.u2.pk).ok)
        self.assertEqual(ActiveResidence.objects.get().unit_id, self.u2.pk)                         # uma só residência ativa (10 §15)
        res = housing.set_residence(self.worker.pk, None)
        self.assertEqual((res.ok, res.detail["housing"]), (True, "initial"))
        self.assertEqual(ActiveResidence.objects.count(), 0)
        self.assertNotIn(housing.PROVIDER_NAME, self.qol_steps(self.worker))

    def test_refusals(self):
        self.assertEqual(housing.set_residence(10 ** 9, self.u1.pk).code, "PLAYER_NOT_FOUND")
        self.assertEqual(housing.set_residence(self.worker.pk, "x").code, "INVALID_PARAMS")
        self.assertEqual(housing.set_residence(self.worker.pk, 10 ** 9).code, "UNIT_NOT_FOUND")
        self.assertEqual(housing.set_residence(self.third.pk, self.u1.pk).code, "NOT_ENTITLED_TO_UNIT")          # de outro jogador
        self.assertTrue(housing.set_residence(self.worker.pk, self.u1.pk).ok)
        self.assertEqual(housing.set_residence(self.worker.pk, self.u1.pk).code, "ALREADY_RESIDENT")
        self.assertEqual(housing.set_residence(self.third.pk, self.u1.pk).code, "UNIT_OCCUPIED")          # já tem morador

    def test_a_company_owned_unit_cannot_be_lived_in_by_the_owner_and_government_lots_have_no_units(self):
        built = self.built(company=self.build)
        self.assertEqual(housing.set_residence(self.boss.pk, self.unit(built).pk).code, "NOT_ENTITLED_TO_UNIT")        # empresa não mora
        self.assertEqual(Unit.objects.filter(building__lot=self.lot(n=0)).count(), 0)

    def test_one_resident_per_unit(self):
        self.assertTrue(housing.set_residence(self.worker.pk, self.u1.pk).ok)
        self.assertEqual(housing.residence_refusal(self.third.pk, self.u1.pk).code, "UNIT_OCCUPIED")
        self.assertEqual(ActiveResidence.objects.filter(unit=self.u1).count(), 1)

    def test_the_registry_path_is_the_same_for_every_player(self):
        target = {"unit": self.u1.pk}
        self.assertTrue(registry.check_action(self.worker.pk, "set_residence", target).available)
        self.assertEqual(registry.check_action(self.third.pk, "set_residence", target).code, "NOT_ENTITLED_TO_UNIT")
        self.assertEqual(registry.check_action(self.worker.pk, "set_residence", {"x": 1}).code, "INVALID_PARAMS")
        self.assertTrue(registry.execute_action(self.worker.pk, "set_residence", target).ok)
        self.assertEqual(registry.execute_action(self.worker.pk, "set_residence", target).code, "ALREADY_RESIDENT")
        self.assertTrue(registry.execute_action(self.worker.pk, "set_residence", {"unit": None}).ok)

    def test_the_initial_housing_does_not_consume_unit_capacity(self):
        for p in (self.third, self.boss, self.worker):
            self.assertEqual(housing.residence_view(p.pk)["housing"], "initial")
        self.assertEqual(Unit.objects.count(), 20)
        self.assertEqual(ActiveResidence.objects.count(), 0)


class AuditTests(HousingBase):
    audit_properties_at_end = False

    def findings(self):
        return {f["code"] for f in audit_properties().findings}

    def test_clean(self):
        self.assertTrue(housing.set_residence(self.worker.pk, self.u1.pk).ok)
        self.assertEqual(self.findings(), set())
        self.assertEqual(audit_properties().stats["units"], 20)

    def test_units_not_matching_the_building_are_found(self):
        self.u2.delete()
        self.assertIn("UNITS_DO_NOT_MATCH_BUILDING", self.findings())

    def test_a_resident_without_right_is_found(self):
        ActiveResidence.objects.create(player=self.third, unit=self.u1, since=0)
        self.assertIn("RESIDENT_WITHOUT_RIGHT", self.findings())
