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
    Quem a transforma em custo ou QoL é outro sistema; o tempo-BASE de viagem está em `base_travel_minutes` (04 §21).
    """
    return distance(a, b, metric or get_scenario().distance_metric)


def base_travel_minutes(a: Located, b: Located) -> Decimal:
    """
    Tempo-BASE de viagem em minutos de jogo: `distância × minutos_por_unidade` (04 §21).

    A Geografia só fornece a distância; este valor é apenas o tempo-base, sem veículos, estradas ou outros modificadores,
    que são do sistema de viagem/transporte e poderão reduzi-lo no futuro. `travel_minutes_per_unit` é parâmetro de
    cenário (valor inicial de calibração do Bot Test, não balanceamento definitivo).
    """
    sc = get_scenario()
    return distance(a, b, sc.distance_metric) * sc.travel_minutes_per_unit


def neighborhood_capacity(neighborhood: Neighborhood) -> Dict[str, int]:
    return neighborhood.lot_capacity()


def lots_of(neighborhood: Neighborhood, category: Optional[Category] = None):
    qs = Lot.objects.filter(neighborhood=neighborhood).order_by("index")
    return qs.filter(category=category.value) if category else qs
