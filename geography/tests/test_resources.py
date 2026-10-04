from collections import Counter
from decimal import Decimal as D

from django.test import SimpleTestCase

from geography import resources
from geography.balance import get_scenario
from geography.constants import RARITY_BASE, RESOURCE_KIND, Category, Resource, ResourceKind
from geography.generator import generate_world
from geography.models import Lot, Neighborhood, ResourceDeposit

from .base import GeoTestCase


class GlobalFrequencyTests(SimpleTestCase):
    """08 §23.3: a raridade define a frequência GLOBAL."""

    def test_target_count_is_the_rarity_times_the_lots(self):
        for total, rarity, want in ((480, "0.20", 96), (480, "0.01", 5), (1000, "0.30", 300), (10, "0", 0), (7, "0.5", 4), (5, "0.5", 2)):
            self.assertEqual(resources.target_count(total, D(rarity)), want, (total, rarity))

    def test_selection_picks_exactly_the_target_number(self):
        pts = [(float(i % 20), float(i // 20)) for i in range(400)]
        for rarity in ("0.01", "0.02", "0.06", "0.30"):
            self.assertEqual(len(resources.select(pts, D(rarity), 1, "iron", 3, 2.0)), resources.target_count(400, D(rarity)))

    def test_no_points_or_zero_rarity_selects_nothing(self):
        self.assertEqual(resources.select([], D("0.2"), 1, "iron", 3, 2.0), [])
        self.assertEqual(resources.select([(0.0, 0.0)] * 5, D(0), 1, "iron", 3, 2.0), [])

    def test_richness_is_relative_to_the_richest_lot(self):
        pts = [(float(i % 20), float(i // 20)) for i in range(400)]
        out = resources.select(pts, D("0.10"), 5, "coal", 3, 2.0)
        values = [r for _, r in out]
        self.assertEqual(max(values), D(1))
        self.assertTrue(all(D("0.001") <= v <= 1 for v in values))
        self.assertGreater(len(set(values)), 1)                         # "depósitos maiores ou menores"


class WorldResourcesTests(GeoTestCase):
    def setUp(self):
        super().setUp()
        self.sc = get_scenario(states=2, cities_per_state=2)            # mundo padrão: 480 lotes rurais
        generate_world(self.sc)
        self.rural = Lot.objects.filter(category="rural").count()

    def test_every_resource_hits_its_documented_rarity(self):
        """08 §15: ferro 20%, cobre 10%, sílica 30%, carvão 15%, sal 12%, lítio 6%, ouro 2%, prata 4%, diamante 1%."""
        have = Counter(ResourceDeposit.objects.values_list("resource", flat=True))
        for res, rarity in RARITY_BASE.items():
            self.assertEqual(have[res.value], resources.target_count(self.rural, rarity), res.value)
        self.assertEqual(have["iron"], 96)
        self.assertEqual(have["diamond"], 5)

    def test_oil_is_rare(self):
        n = ResourceDeposit.objects.filter(resource="oil").count()
        self.assertGreater(n, 0)
        self.assertLess(n, ResourceDeposit.objects.filter(resource="iron").count())

    def test_deposits_exist_only_on_rural_lots(self):
        self.assertFalse(ResourceDeposit.objects.exclude(lot__category="rural").exists())

    def test_a_lot_can_hold_more_than_one_resource_but_never_the_same_twice(self):
        per_lot = Counter(ResourceDeposit.objects.values_list("lot_id", flat=True))
        self.assertGreaterEqual(max(per_lot.values()), 1)
        self.assertEqual(ResourceDeposit.objects.count(), len(set(ResourceDeposit.objects.values_list("lot_id", "resource"))))

    def test_deposits_are_spatially_clustered_not_independent_per_lot(self):
        """
        08 §13: 'Um lote não deve simplesmente realizar uma rolagem completamente independente.'

        Mede o ÍNDICE DE DISPERSÃO por bairro rural: variância das contagens dividida pela variância esperada se cada
        lote sorteasse sozinho (n·p·(1-p)). Sorteio independente dá ~1; concentração regional dá bem mais. (Uma medida
        por vizinho mais próximo NÃO serve: os lotes de um bairro ficam numa grade apertada, então a distância ao
        vizinho é minúscula com ou sem concentração. A escala relevante é a do bairro.)
        """
        hoods = list(Neighborhood.objects.filter(zoning="rural").values_list("id", flat=True))
        lots_per_hood = self.rural // len(hoods)
        for resource, rarity in (("iron", 0.20), ("silica", 0.30), ("coal", 0.15), ("copper", 0.10)):
            per = Counter(ResourceDeposit.objects.filter(resource=resource).values_list("lot__neighborhood_id", flat=True))
            counts = [per.get(h, 0) for h in hoods]
            mean = sum(counts) / len(counts)
            variance = sum((c - mean) ** 2 for c in counts) / (len(counts) - 1)
            dispersion = variance / (lots_per_hood * rarity * (1 - rarity))
            self.assertGreater(dispersion, 5, f"{resource}: dispersão {dispersion:.2f} (independente ≈ 1)")

    def test_there_are_rich_areas_and_areas_with_no_occurrence(self):
        """08 §13: 'áreas ricas', 'regiões sem ocorrência', 'concentrações locais'."""
        for resource in ("iron", "silica", "coal"):
            per_hood = Counter(ResourceDeposit.objects.filter(resource=resource, lot__category="rural")
                               .values_list("lot__neighborhood_id", flat=True))
            rural_hoods = list(Neighborhood.objects.filter(zoning="rural").values_list("id", flat=True))
            counts = [per_hood.get(h, 0) for h in rural_hoods]
            self.assertEqual(min(counts), 0, f"{resource}: deveria haver bairro rural sem ocorrência")
            self.assertGreater(max(counts), 0.5 * 40, f"{resource}: deveria haver bairro rural muito concentrado")

    def test_same_global_share_but_different_regions_per_resource(self):
        iron = set(ResourceDeposit.objects.filter(resource="iron").values_list("lot_id", flat=True))
        silica = set(ResourceDeposit.objects.filter(resource="silica").values_list("lot_id", flat=True))
        self.assertNotEqual(iron, silica)

    def test_resource_kinds_for_the_extraction_systems(self):
        self.assertEqual(RESOURCE_KIND[Resource.OIL], ResourceKind.EXTRACTIVE)


class SmallWorldResourcesTests(GeoTestCase):
    def test_zero_rarity_resource_generates_nothing(self):
        self.world(resource_rarity={"gold": 0, "iron": "0.5"})
        self.assertFalse(ResourceDeposit.objects.filter(resource="gold").exists())
        self.assertEqual(ResourceDeposit.objects.filter(resource="iron").count(),
                         resources.target_count(Lot.objects.filter(category="rural").count(), D("0.5")))

    def test_world_without_rural_lots_has_no_deposits_and_is_still_valid(self):
        from geography.integrity import check_integrity
        sc = self.world(neighborhood_type_counts={"institutional": 1, "commercial": 1, "residential": 4}, resource_rarity={"oil": "0.5"})
        self.assertEqual(ResourceDeposit.objects.count(), 0)
        self.assertTrue(check_integrity(sc).ok)

    def test_richness_stays_inside_the_documented_column_range(self):
        self.world(resource_rarity={"iron": "0.9"})
        for d in ResourceDeposit.objects.all():
            self.assertTrue(0 < d.richness <= 1)

