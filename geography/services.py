"""Consultas de Geografia para os demais sistemas (08 §21): onde as coisas existem; o que fazem é de cada sistema."""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, Optional

from .balance import get_scenario
from .constants import Category
from .models import Lot, Neighborhood
from .spatial import Located, distance


def distance_between(a: Located, b: Located, metric: Optional[str] = None) -> Decimal:
    """
    Distância em unidades de grid entre dois lugares (Estado, Cidade, Bairro ou Lote), derivada das coordenadas.
    Quem a transforma em tempo, custo ou QoL é outro sistema (ex.: 04 §21 converte a 40 min por unidade).
    """
    return distance(a, b, metric or get_scenario().distance_metric)


def neighborhood_capacity(neighborhood: Neighborhood) -> Dict[str, int]:
    return neighborhood.lot_capacity()


def lots_of(neighborhood: Neighborhood, category: Optional[Category] = None):
    qs = Lot.objects.filter(neighborhood=neighborhood).order_by("index")
    return qs.filter(category=category.value) if category else qs
