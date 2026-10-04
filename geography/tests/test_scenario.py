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

    def test_open_decisions_default_to_the_most_literal_reading(self):
        s = get_scenario()
        self.assertEqual((s.lot_composition, s.zoning_permissions, s.distance_metric), (None, None, "euclidean"))

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
            {"lot_composition": {"residential": {"residential": 1}}},                 # faltam os outros tipos de bairro
        ]
        for overrides in bad:
            with self.assertRaises((ImproperlyConfigured, ValueError), msg=str(overrides)):
                get_scenario(**overrides)

    def test_neighborhood_types_follow_the_center_to_periphery_order(self):
        types = neighborhood_types(get_scenario())
        self.assertEqual(len(types), 25)
        self.assertEqual(types[0], Category.INSTITUTIONAL)
        self.assertEqual(types[-1], Category.RURAL)


class OpenLotCompositionDecisionTests(GeoTestCase):
    """
    [ABERTO 08 §4/§6/§11] Quantos lotes de cada categoria tem um bairro? O padrão é a leitura literal; estas
    alternativas provam que fechar a decisão é MUDAR UM VALOR do cenário, sem tocar em código.
    """

    def test_alternative_every_neighborhood_has_every_urban_category(self):
        urban = {"residential": 2, "commercial": 2, "industrial": 1, "institutional": 1}
        comp = {t: dict(urban) for t in ("institutional", "commercial", "residential", "industrial")}
        comp["rural"] = {"rural": 6}
        comp["special"] = {"special": 3}
        sc = self.world(lot_composition=comp)
        hood = Neighborhood.objects.filter(zoning="residential").first()
        self.assertEqual(hood.lot_capacity(), urban)
        self.assertTrue(check_integrity(sc).ok)

    def test_alternative_special_lots_only_in_special_neighborhoods(self):
        sc = self.world(neighborhood_type_counts={"institutional": 1, "commercial": 1, "residential": 2, "special": 1, "rural": 1})
        self.assertEqual(set(Lot.objects.filter(category="special").values_list("neighborhood__zoning", flat=True)), {"special"})
        self.assertTrue(check_integrity(sc).ok)
