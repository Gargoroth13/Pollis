from django.test import TestCase

from geography.balance import get_scenario
from geography.constants import Category
from geography.generator import generate_world

# Mundo pequeno (rápido) que mantém TODAS as categorias de bairro; capacidades reduzidas por serem parâmetros (08 §6).
SMALL = dict(
    states=1, cities_per_state=2, neighborhoods_per_city=6,
    neighborhood_type_counts={"institutional": 1, "commercial": 1, "residential": 2, "industrial": 1, "rural": 1},
    type_order_from_center=("institutional", "commercial", "residential", "special", "industrial", "rural"),
    lot_capacity={"residential": 4, "commercial": 3, "industrial": 2, "institutional": 1, "special": 1},
    rural_lots_per_neighborhood=20,
)


class GeoTestCase(TestCase):
    def world(self, **overrides):
        """Gera o mundo pequeno (ou variações) e devolve o cenário usado."""
        sc = get_scenario(**{**SMALL, **overrides})
        self.summary = generate_world(sc)
        return sc


def wipe_world():
    """Apaga o mundo (só nos testes) para regenerar com outro cenário."""
    from geography.models import City, Lot, Neighborhood, ResourceDeposit, State
    ResourceDeposit.objects.all().delete()
    Lot.objects.all().delete()
    Neighborhood.objects.all().delete()
    State.objects.update(capital=None)
    City.objects.all().delete()
    State.objects.all().delete()
