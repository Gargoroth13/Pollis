from decimal import Decimal as D

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from geography.balance import get_scenario
from geography.constants import Category, Resource
from geography.generator import generate_world, neighborhood_types
from geography.integrity import check_integrity
from geography.models import Lot, Neighborhood

from .base import SMALL, GeoTestCase


class ScenarioConfigTests(SimpleTestCase):
    def test_defaults_keep_08_values_separate_from_scenario_values(self):
        s = get_scenario()
        self.assertEqual((s.neighborhoods_per_city, s.lot_capacity[Category.RESIDENTIAL], s.resource_rarity[Resource.IRON]), (25, 50, D("0.20")))
        self.assertEqual(sum(s.neighborhood_type_counts.values()), 25)

    def test_decided_defaults(self):
        """Decisões do Game Director (2026-10-03): distância euclidiana; capital = 1ª cidade (cenário); 15 min/unidade."""
        s = get_scenario()
        self.assertEqual((s.distance_metric, s.zoning_permissions, s.capital_city_index, s.travel_minutes_per_unit),
                         ("euclidean", None, 0, D(15)))

    def test_travel_cost_per_unit_is_a_provisional_scenario_parameter(self):
        """Decisão do GD (2026-10-07): a viagem também custa dinheiro; o valor (10) é calibração do Bot Test, não balanceamento."""
        self.assertEqual(get_scenario().travel_cost_per_unit, D(10))
        self.assertEqual(get_scenario(travel_cost_per_unit=0).travel_cost_per_unit, D(0))
        self.assertEqual(get_scenario(travel_cost_per_unit="2.5").travel_cost_per_unit, D("2.5"))

    def test_lot_composition_is_no_longer_configurable(self):
        """Decisão: leitura A. A leitura B (todas as categorias em todos os bairros) foi descartada."""
        with self.assertRaises(ImproperlyConfigured):
            get_scenario(lot_composition={"residential": {"residential": 1, "commercial": 1}})

    @override_settings(POLIS_GEOGRAPHY={"lot_capacity": {"residential": 7}, "resource_rarity": {"gold": 0.5}})
    def test_overrides_merge_by_key(self):
        s = get_scenario()
        self.assertEqual((s.lot_capacity[Category.RESIDENTIAL], s.lot_capacity[Category.COMMERCIAL], s.resource_rarity[Resource.GOLD], s.resource_rarity[Resource.IRON]),
                         (7, 30, D("0.5"), D("0.20")))

    def test_invalid_scenarios_fail_loudly(self):
        bad = [
            {"nope": 1},
            {"states": 0}, {"cities_per_state": 0}, {"neighborhoods_per_city": 0},
            {"neighborhood_type_counts": {"residential": 3}},                         # não soma 25
            {"neighborhoods_per_city": 5, "neighborhood_type_counts": {"residential": 5}, "type_order_from_center": ["commercial"]},
            {"lot_capacity": {"rural": 5}},                                           # rural não tem capacidade fixa
            {"lot_capacity": {"residential": -1}},
            {"resource_rarity": {"iron": 2}},
            {"distance_metric": "chebyshev"},
            {"state_spacing": 0}, {"hotspots_per_resource": 0},
            {"zoning_permissions": {"commercial": ["castle"]}},
            {"capital_city_index": 5},                                                # só 2 cidades por estado
            {"capital_city_index": -1},
            {"travel_minutes_per_unit": 0}, {"travel_minutes_per_unit": -3},
            {"travel_cost_per_unit": -1},                                             # custo nunca negativo (0 é válido: viagem grátis)
        ]
        for overrides in bad:
            with self.assertRaises((ImproperlyConfigured, ValueError), msg=str(overrides)):
                get_scenario(**overrides)

    def test_neighborhood_types_follow_the_center_to_periphery_order(self):
        types = neighborhood_types(get_scenario())
        self.assertEqual(len(types), 25)
        self.assertEqual(types[0], Category.INSTITUTIONAL)
        self.assertEqual(types[-1], Category.RURAL)


class LotCompositionReadingATests(GeoTestCase):
    """
    Decisão do Game Director (2026-10-03): leitura A. Cada bairro tem um tipo predominante e a quantidade de lotes
    correspondente à capacidade DAQUELE tipo. Quantos bairros de cada tipo existem nas 25 posições segue sendo
    cenário provisório.
    """

    def test_every_neighborhood_holds_only_lots_of_its_own_type_with_that_types_capacity(self):
        sc = self.world()
        for hood in Neighborhood.objects.all():
            cap = hood.lot_capacity()
            want = sc.rural_lots_per_neighborhood if hood.zoning == "rural" else sc.lot_capacity[Category(hood.zoning)]
            self.assertEqual(cap, {hood.zoning: want}, hood.name)

    def test_reading_b_never_happens_no_neighborhood_mixes_categories(self):
        self.world()
        self.assertEqual(max(len(h.lot_capacity()) for h in Neighborhood.objects.all()), 1)

    def test_special_lots_exist_only_in_special_neighborhoods(self):
        sc = self.world(neighborhood_type_counts={"institutional": 1, "commercial": 1, "residential": 2, "special": 1, "rural": 1})
        self.assertEqual(set(Lot.objects.filter(category="special").values_list("neighborhood__zoning", flat=True)), {"special"})
        self.assertTrue(check_integrity(sc).ok)

    def test_how_many_neighborhoods_of_each_type_is_still_scenario_configuration(self):
        """A mistura de tipos dentro das posições da cidade NÃO virou regra: muda com o cenário."""
        a = self.world(neighborhood_type_counts={"institutional": 1, "commercial": 1, "residential": 2, "industrial": 1, "rural": 1})
        count_a = Neighborhood.objects.filter(zoning="residential").count()
        from geography.tests.base import wipe_world
        wipe_world()
        self.world(neighborhood_type_counts={"institutional": 1, "commercial": 1, "residential": 4})
        self.assertNotEqual(Neighborhood.objects.filter(zoning="residential").count(), count_a)
