"""
Geração do mundo (design/08 §3.1, §19, §22). DETERMINÍSTICA: o mesmo Scenario (inclusive a seed) produz sempre o
mesmo mundo, o que permite que cenários de Bot Test sejam comparáveis (21 §21.49).

Não destrói nada: se já existe mundo, recusa. Recriar um mundo é decisão explícita de quem opera, não efeito colateral.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from django.db import transaction

from . import resources, spatial
from .balance import Scenario, get_scenario
from .constants import CATEGORIES, RESOURCES, Category, Occupation
from .models import City, Lot, Neighborhood, ResourceDeposit, State


class WorldAlreadyExists(Exception):
    pass


@dataclass(frozen=True)
class WorldSummary:
    states: int
    cities: int
    neighborhoods: int
    lots: int
    lots_by_category: Dict[str, int]
    deposits_by_resource: Dict[str, int]


def neighborhood_types(sc: Scenario) -> List[Category]:
    """Tipo de cada bairro, do centro (índice 0) para a periferia, segundo o plano do cenário."""
    return [t for t in sc.type_order_from_center for _ in range(sc.neighborhood_type_counts.get(t, 0))]


@transaction.atomic
def generate_world(scenario: Optional[Scenario] = None) -> WorldSummary:
    sc = scenario or get_scenario()
    if State.objects.exists():
        raise WorldAlreadyExists("Já existe um mundo gerado; a geração não sobrescreve nem apaga nada.")

    types = neighborhood_types(sc)
    state_pts = spatial.spiral_offsets(sc.states, sc.state_spacing)
    city_pts = spatial.spiral_offsets(sc.cities_per_state, sc.city_spacing)
    hood_pts = spatial.neighborhood_offsets(sc.neighborhoods_per_city, sc.city_radius)

    for si, spt in enumerate(state_pts):
        state = State.objects.create(name=f"Estado {si + 1}", x=spt[0], y=spt[1])
        capital: Optional[City] = None
        for ci, cpt in enumerate(city_pts):
            cx, cy = spatial.add(spt, cpt)
            city = City.objects.create(state=state, index=ci, name=f"Cidade {si + 1}.{ci + 1}", x=cx, y=cy)
            if ci == sc.capital_city_index:
                capital = city
            Neighborhood.objects.bulk_create([
                Neighborhood(city=city, index=ni, name=f"Bairro {si + 1}.{ci + 1}.{ni + 1:02d}",
                             x=spatial.add((cx, cy), hpt)[0], y=spatial.add((cx, cy), hpt)[1], zoning=types[ni].value)
                for ni, hpt in enumerate(hood_pts)])
            lots: List[Lot] = []
            for hood in Neighborhood.objects.filter(city=city).order_by("index"):
                composition = sc.expected_composition(Category(hood.zoning))
                categories = [c for c in CATEGORIES for _ in range(composition.get(c, 0))]
                for li, off in enumerate(spatial.lot_offsets(len(categories), sc.lot_spacing)):
                    lx, ly = spatial.add((hood.x, hood.y), off)
                    lots.append(Lot(neighborhood=hood, index=li, category=categories[li].value, x=lx, y=ly,
                                    occupation=Occupation.EMPTY.value))  # 10 §2: todos os lotes começam vazios
            Lot.objects.bulk_create(lots)
        state.capital = capital  # o 08 §2 exige uma capital por estado, sem dizer qual: vem do cenário (capital_city_index)
        state.save(update_fields=["capital"])

    deposits = _generate_resources(sc)
    by_cat = {c.value: Lot.objects.filter(category=c.value).count() for c in CATEGORIES}
    return WorldSummary(State.objects.count(), City.objects.count(), Neighborhood.objects.count(),
                        Lot.objects.count(), {k: v for k, v in by_cat.items() if v}, deposits)


def _generate_resources(sc: Scenario) -> Dict[str, int]:
    """
    Recursos só em lotes RURAIS (08 §12: é o lote rural que "permite a exploração do território e de seus recursos
    naturais"). O 08 §5 diz apenas "eventuais recursos naturais" no lote; restringir ao rural é interpretação.
    """
    rural = list(Lot.objects.filter(category=Category.RURAL.value).order_by("id"))
    points = [(float(l.x), float(l.y)) for l in rural]
    counts: Dict[str, int] = {}
    for resource in RESOURCES:
        rarity = sc.resource_rarity.get(resource, Decimal(0))
        picked = resources.select(points, rarity, sc.seed, resource.value, sc.hotspots_per_resource, float(sc.hotspot_sigma))
        ResourceDeposit.objects.bulk_create([
            ResourceDeposit(lot=rural[i], resource=resource.value, richness=richness) for i, richness in picked])
        if picked:
            counts[resource.value] = len(picked)
    return counts
