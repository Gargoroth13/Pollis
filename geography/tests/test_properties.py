"""
Propriedades sobre cenários ALEATÓRIOS (semente fixa => reproduzíveis): tamanhos, capacidades (inclusive 0),
composição de tipos de bairro, raridades e seeds variados. Para TODOS:

  1. o mundo gerado passa na integridade territorial;
  2. a contagem de lotes é exatamente a que o cenário prevê;
  3. o mesmo cenário gera exatamente o mesmo mundo (determinismo);
  4. frequência global de cada recurso = raridade (arredondada ao lote) e só em lotes rurais;
  5. coordenadas e hierarquia coerentes (todo lote tem 1 bairro, 1 cidade, 1 estado; capital pertence ao estado).
"""
import random
from collections import Counter
from decimal import Decimal

from django.test import TestCase

from geography import resources, spatial
from geography.balance import get_scenario
from geography.constants import CATEGORIES, RESOURCES, Category
from geography.generator import generate_world, neighborhood_types
from geography.integrity import check_integrity
from geography.models import City, Lot, Neighborhood, ResourceDeposit, State

from .base import wipe_world

TYPES = [c.value for c in CATEGORIES]


def random_scenario(rng: random.Random):
    n = rng.randint(1, 14)
    counts = Counter(rng.choices(TYPES, k=n))
    order = TYPES[:]
    rng.shuffle(order)
    return get_scenario(
        seed=rng.randint(1, 10_000), states=rng.randint(1, 3), cities_per_state=rng.randint(1, 3),
        neighborhoods_per_city=n, neighborhood_type_counts=dict(counts), type_order_from_center=tuple(order),
        lot_capacity={c: rng.randint(0, 6) for c in TYPES if c != "rural"}, rural_lots_per_neighborhood=rng.randint(0, 9),
        resource_rarity={r.value: Decimal(rng.randint(0, 60)) / 100 for r in RESOURCES},
    )


def expected_lots(sc):
    per_city = sum(sum(sc.expected_composition(t).values()) for t in neighborhood_types(sc))
    return sc.states * sc.cities_per_state * per_city


def snapshot():
    return (list(Lot.objects.order_by("id").values_list("category", "x", "y")),
            list(ResourceDeposit.objects.order_by("lot_id", "resource").values_list("resource", "richness")),
            list(Neighborhood.objects.order_by("id").values_list("zoning", "x", "y")))


class PropertyTests(TestCase):
    SEEDS = range(1, 41)

    def test_random_scenarios_generate_intact_worlds_with_exact_counts(self):
        for seed in self.SEEDS:
            sc = random_scenario(random.Random(seed))
            summary = generate_world(sc)
            report = check_integrity(sc)
            self.assertTrue(report.ok, (seed, report.violations[:3]))
            self.assertEqual(summary.lots, expected_lots(sc), seed)
            self.assertEqual(summary.neighborhoods, sc.states * sc.cities_per_state * sc.neighborhoods_per_city, seed)
            wipe_world()

    def test_same_scenario_same_world(self):
        for seed in (3, 9, 17, 25, 33):
            sc = random_scenario(random.Random(seed))
            generate_world(sc)
            first = snapshot()
            wipe_world()
            generate_world(sc)
            self.assertEqual(snapshot(), first, seed)
            wipe_world()

    def test_resource_frequency_matches_rarity_and_lives_only_on_rural_lots(self):
        for seed in self.SEEDS:
            sc = random_scenario(random.Random(seed))
            generate_world(sc)
            rural = Lot.objects.filter(category="rural").count()
            have = Counter(ResourceDeposit.objects.values_list("resource", flat=True))
            for res in RESOURCES:
                self.assertEqual(have.get(res.value, 0), resources.target_count(rural, sc.resource_rarity[res]), (seed, res.value))
            self.assertFalse(ResourceDeposit.objects.exclude(lot__category="rural").exists(), seed)
            wipe_world()

    def test_hierarchy_and_capitals_are_coherent(self):
        for seed in range(1, 16):
            sc = random_scenario(random.Random(seed))
            generate_world(sc)
            self.assertEqual(State.objects.count(), sc.states)
            for s in State.objects.all():
                self.assertEqual(s.capital.state_id, s.id)
                self.assertEqual(s.cities.count(), sc.cities_per_state)
            self.assertEqual(Lot.objects.filter(neighborhood__city__state__isnull=True).count(), 0)
            wipe_world()

    def test_distances_are_symmetric_and_satisfy_the_triangle_inequality_on_real_places(self):
        rng = random.Random(5)
        sc = random_scenario(random.Random(2))
        generate_world(sc)
        places = list(Neighborhood.objects.all()) + list(City.objects.all()) + list(State.objects.all())
        for metric in ("euclidean", "manhattan"):
            for _ in range(60):
                a, b, c = rng.sample(places, 3) if len(places) >= 3 else (places[0],) * 3
                d = lambda p, q: spatial.distance(p, q, metric)
                self.assertEqual(d(a, b), d(b, a))
                self.assertGreaterEqual(d(a, b), 0)
                self.assertLessEqual(d(a, c), d(a, b) + d(b, c) + Decimal("1e-20"))

    def test_the_random_scenarios_actually_exercise_the_interesting_cases(self):
        """Guarda contra teste vazio: precisa haver mundos com depósitos, sem lote rural, e bairros sem lotes."""
        seen = set()
        for seed in self.SEEDS:
            sc = random_scenario(random.Random(seed))
            generate_world(sc)
            if ResourceDeposit.objects.exists():
                seen.add("WITH_DEPOSITS")
            if not Lot.objects.filter(category="rural").exists():
                seen.add("NO_RURAL_LOTS")
            if any(not h.lots.exists() for h in Neighborhood.objects.all()):
                seen.add("EMPTY_NEIGHBORHOOD")
            if State.objects.count() > 1 and City.objects.count() / State.objects.count() > 1:
                seen.add("MULTI_STATE_MULTI_CITY")
            if len({h.zoning for h in Neighborhood.objects.all()}) >= 4:
                seen.add("MIXED_TYPES")
            wipe_world()
        self.assertEqual(seen, {"WITH_DEPOSITS", "NO_RURAL_LOTS", "EMPTY_NEIGHBORHOOD", "MULTI_STATE_MULTI_CITY", "MIXED_TYPES"}, seen)
