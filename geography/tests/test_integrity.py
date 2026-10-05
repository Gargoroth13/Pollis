from geography.constants import Category
from geography.integrity import check_integrity
from geography.models import City, Lot, Neighborhood, ResourceDeposit, State

from .base import GeoTestCase


class IntegrityTests(GeoTestCase):
    """O mundo gerado é íntegro; e cada tipo de corrupção é detectado com o seu código."""

    def setUp(self):
        super().setUp()
        self.sc = self.world(states=2)

    def codes(self):
        return check_integrity(self.sc).codes

    def test_a_generated_world_is_intact(self):
        r = check_integrity(self.sc)
        self.assertTrue(r.ok, r.violations)
        self.assertGreater(r.stats["lots"], 0)

    def test_empty_world(self):
        for m in (ResourceDeposit, Lot, Neighborhood):
            m.objects.all().delete()
        State.objects.update(capital=None)
        City.objects.all().delete()
        State.objects.all().delete()
        self.assertEqual(check_integrity(self.sc).codes, ["EMPTY_WORLD"])

    def test_missing_lot_breaks_composition_and_index_contiguity(self):
        hood = Neighborhood.objects.filter(zoning="residential").first()
        Lot.objects.filter(neighborhood=hood).order_by("index").first().delete()
        self.assertEqual(self.codes(), ["LOT_INDEX_GAP", "NEIGHBORHOOD_LOT_COMPOSITION_MISMATCH"])

    def test_extra_lot_of_the_wrong_category(self):
        hood = Neighborhood.objects.filter(zoning="residential").first()
        Lot.objects.create(neighborhood=hood, index=99, category="industrial", x=0, y=0)
        self.assertIn("NEIGHBORHOOD_LOT_COMPOSITION_MISMATCH", self.codes())

    def test_state_without_capital(self):
        State.objects.filter(pk=State.objects.first().pk).update(capital=None)
        self.assertEqual(self.codes(), ["STATE_WITHOUT_CAPITAL"])

    def test_capital_belonging_to_another_state(self):
        a, b = State.objects.order_by("id")
        State.objects.filter(pk=a.pk).update(capital=b.capital)
        self.assertEqual(self.codes(), ["CAPITAL_NOT_IN_STATE"])

    def test_state_without_cities(self):
        s = State.objects.create(name="Estado vazio", x=99, y=99)
        self.assertIn("STATE_WITHOUT_CITY", self.codes())
        self.assertIn("STATE_WITHOUT_CAPITAL", self.codes())

    def test_city_with_the_wrong_number_of_neighborhoods(self):
        Neighborhood.objects.filter(city=City.objects.first()).order_by("index").last().delete()
        self.assertIn("CITY_WRONG_NEIGHBORHOOD_COUNT", self.codes())

    def test_city_whose_type_plan_changed(self):
        h = Neighborhood.objects.filter(zoning="residential").first()
        Neighborhood.objects.filter(pk=h.pk).update(zoning="commercial")
        self.assertIn("CITY_TYPE_PLAN_MISMATCH", self.codes())

    def test_overlapping_lots(self):
        hood = Neighborhood.objects.filter(zoning="residential").first()
        a, b = Lot.objects.filter(neighborhood=hood).order_by("index")[:2]
        Lot.objects.filter(pk=b.pk).update(x=a.x, y=a.y)
        self.assertEqual(self.codes(), ["DUPLICATE_LOT_COORDINATES"])

    def test_overlapping_neighborhoods_cities_and_states(self):
        h1, h2 = Neighborhood.objects.filter(city=City.objects.first()).order_by("index")[:2]
        Neighborhood.objects.filter(pk=h2.pk).update(x=h1.x, y=h1.y)
        c1, c2 = City.objects.filter(state=State.objects.first()).order_by("index")[:2]
        City.objects.filter(pk=c2.pk).update(x=c1.x, y=c1.y)
        s1, s2 = State.objects.order_by("id")
        State.objects.filter(pk=s2.pk).update(x=s1.x, y=s1.y)
        self.assertEqual(self.codes(), ["DUPLICATE_CITY_COORDINATES", "DUPLICATE_NEIGHBORHOOD_COORDINATES", "DUPLICATE_STATE_COORDINATES"])

    def test_deposit_on_a_non_rural_lot(self):
        lot = Lot.objects.filter(category="residential").first()
        ResourceDeposit.objects.create(lot=lot, resource="gold", richness="0.5")
        self.assertIn("DEPOSIT_ON_NON_RURAL_LOT", self.codes())

    def test_resource_frequency_off_its_rarity(self):
        ResourceDeposit.objects.filter(resource="iron").first().delete()
        self.assertIn("RESOURCE_SHARE_MISMATCH", self.codes())

    def test_integrity_follows_the_scenario_in_force(self):
        """Se o cenário muda (ex.: decisão [ABERTO] dos lotes), o mesmo mundo passa a ser inválido para ele."""
        from geography.balance import get_scenario
        from geography.tests.base import SMALL
        other = get_scenario(**{**SMALL, "states": 2, "lot_capacity": {"residential": 5}})
        self.assertIn("NEIGHBORHOOD_LOT_COMPOSITION_MISMATCH", check_integrity(other).codes)
