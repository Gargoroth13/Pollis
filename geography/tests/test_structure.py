from decimal import Decimal as D

from django.test import TestCase

from geography.balance import get_scenario
from geography.constants import (CAPACITY_BASE, CATEGORIES, NEIGHBORHOODS_PER_CITY, RARITY_BASE, RESOURCE_KIND,
                                 Category, Occupation, Resource, ResourceKind)
from geography.generator import WorldAlreadyExists, generate_world
from geography.integrity import check_integrity
from geography.models import City, Lot, Neighborhood, ResourceDeposit, State

from .base import SMALL, GeoTestCase


class DocumentedConstantsTests(TestCase):
    """Os valores [08] não são calibração livre: este teste os trava contra o design."""

    def test_lot_capacities_08_section_6(self):
        self.assertEqual({c.value: n for c, n in CAPACITY_BASE.items()},
                         {"residential": 50, "commercial": 30, "industrial": 20, "institutional": 5, "special": 10})
        self.assertNotIn(Category.RURAL, CAPACITY_BASE)                   # rural: "definida pela estrutura territorial"

    def test_six_lot_categories_08_section_5(self):
        self.assertEqual([c.value for c in CATEGORIES], ["residential", "commercial", "industrial", "institutional", "special", "rural"])

    def test_twenty_five_neighborhoods_per_city_08_section_3_1(self):
        self.assertEqual(NEIGHBORHOODS_PER_CITY, 25)
        self.assertEqual(get_scenario().neighborhoods_per_city, 25)

    def test_mineral_rarities_08_section_15(self):
        self.assertEqual({r.value: v for r, v in RARITY_BASE.items()},
                         {"iron": D("0.20"), "copper": D("0.10"), "silica": D("0.30"), "coal": D("0.15"), "salt": D("0.12"),
                          "lithium": D("0.06"), "gold": D("0.02"), "silver": D("0.04"), "diamond": D("0.01")})

    def test_oil_is_extractive_only_never_mining_08_section_12(self):
        self.assertEqual(RESOURCE_KIND[Resource.OIL], ResourceKind.EXTRACTIVE)
        self.assertEqual([r.value for r in Resource if RESOURCE_KIND[r] is ResourceKind.EXTRACTIVE], ["oil"])
        self.assertEqual(len([r for r in Resource if RESOURCE_KIND[r] is ResourceKind.MINERAL]), 9)

    def test_oil_has_no_documented_rarity_so_it_is_a_provisional_scenario_value(self):
        self.assertNotIn(Resource.OIL, RARITY_BASE)                       # o 08 §14 só diz "raro"
        self.assertIn(Resource.OIL, get_scenario().resource_rarity)


class FullCityStructureTests(GeoTestCase):
    """Uma cidade completa com os parâmetros do 08: 25 bairros e a capacidade de lotes por tipo."""

    def test_a_default_city_has_25_neighborhoods_with_the_documented_lot_counts(self):
        sc = get_scenario(states=1, cities_per_state=1)
        generate_world(sc)
        city = City.objects.get()
        hoods = list(city.neighborhoods.order_by("index"))
        self.assertEqual(len(hoods), 25)
        expected = {"residential": 50, "commercial": 30, "industrial": 20, "institutional": 5, "special": 10}
        for h in hoods:
            cap = h.lot_capacity()
            if h.zoning == "rural":
                self.assertEqual(cap, {"rural": sc.rural_lots_per_neighborhood})
            else:
                self.assertEqual(cap, {h.zoning: expected[h.zoning]}, h.name)    # leitura literal [ABERTO]: 1 tipo por bairro
        self.assertTrue(check_integrity(sc).ok)

    def test_a_special_neighborhood_has_ten_special_lots(self):
        generate_world(get_scenario(states=1, cities_per_state=1))
        special = Neighborhood.objects.get(zoning="special")
        self.assertEqual(special.lot_capacity(), {"special": 10})            # 08 §11


class HierarchyTests(GeoTestCase):
    def test_state_city_neighborhood_lot_relations(self):
        self.world()
        self.assertEqual((State.objects.count(), City.objects.count()), (1, 2))
        for lot in Lot.objects.all()[:50]:
            self.assertEqual(lot.neighborhood.city.state.name, "Estado 1")
        self.assertEqual(Neighborhood.objects.count(), 12)

    def test_each_state_has_a_capital_that_belongs_to_it(self):
        self.world(states=3)
        for s in State.objects.all():
            self.assertEqual(s.capital.state_id, s.id)                        # 08 §2

    def test_reference_city_sits_at_origin(self):
        """04 §21: 'a cidade de referência em (0,0)' é só uma coordenada, sem bônus nem penalidade."""
        self.world(states=2)
        first = City.objects.order_by("state_id", "index").first()
        self.assertEqual((first.x, first.y), (D(0), D(0)))

    def test_every_lot_starts_empty(self):
        """10 §2: todos os lotes começam vazios."""
        self.world()
        self.assertFalse(Lot.objects.exclude(occupation=Occupation.EMPTY.value).exists())

    def test_neighborhood_has_no_fixed_social_class(self):
        """08 §4, §23.5: rico/médio/pobre não é característica permanente do bairro."""
        names = {f.name for f in Neighborhood._meta.get_fields()}
        self.assertFalse({n for n in names if any(w in n for w in ("class", "social", "rich", "poor", "income", "wealth"))})

    def test_distance_is_never_stored_as_an_attribute(self):
        """08 §17: não existe 'distância até a capital' como variável de gameplay."""
        for model in (State, City, Neighborhood, Lot):
            self.assertFalse([f.name for f in model._meta.get_fields() if "dist" in f.name or "capital_dist" in f.name], model)

    def test_lot_capacity_is_derived_from_lots_not_stored_twice(self):
        self.world()
        hood = Neighborhood.objects.filter(zoning="residential").first()
        self.assertEqual(hood.lot_capacity(), {"residential": 4})
        Lot.objects.filter(neighborhood=hood).first().delete()
        self.assertEqual(hood.lot_capacity(), {"residential": 3})


class GenerationSafetyTests(GeoTestCase):
    def test_generation_never_overwrites_an_existing_world(self):
        self.world()
        before = (Lot.objects.count(), ResourceDeposit.objects.count())
        with self.assertRaises(WorldAlreadyExists):
            generate_world(get_scenario(**SMALL))
        self.assertEqual((Lot.objects.count(), ResourceDeposit.objects.count()), before)

    def test_a_failure_midway_leaves_no_partial_world(self):
        from unittest import mock
        with mock.patch("geography.generator._generate_resources", side_effect=RuntimeError("falha")):
            with self.assertRaises(RuntimeError):
                self.world()
        self.assertEqual((State.objects.count(), City.objects.count(), Neighborhood.objects.count(), Lot.objects.count()), (0, 0, 0, 0))

    def test_same_scenario_generates_the_same_world(self):
        """Mesma seed => mundo idêntico (21 §21.49), o que torna cenários de Bot Test comparáveis."""
        def snapshot():
            return (list(State.objects.order_by("name").values_list("name", "x", "y")),
                    list(Lot.objects.order_by("id").values_list("category", "x", "y")),
                    list(ResourceDeposit.objects.order_by("lot_id", "resource").values_list("resource", "richness")))
        self.world(seed=11)
        first = snapshot()
        ResourceDeposit.objects.all().delete()
        Lot.objects.all().delete()
        Neighborhood.objects.all().delete()
        State.objects.update(capital=None)
        City.objects.all().delete()
        State.objects.all().delete()
        self.world(seed=11)
        self.assertEqual(snapshot(), first)

    def test_a_different_seed_changes_where_the_resources_are(self):
        self.world(seed=1)
        first = set(ResourceDeposit.objects.values_list("lot__x", "lot__y", "resource"))
        for m in (ResourceDeposit, Lot, Neighborhood):
            m.objects.all().delete()
        State.objects.update(capital=None)
        City.objects.all().delete()
        State.objects.all().delete()
        self.world(seed=2)
        self.assertNotEqual(set(ResourceDeposit.objects.values_list("lot__x", "lot__y", "resource")), first)
