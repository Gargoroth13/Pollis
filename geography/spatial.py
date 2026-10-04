"""
Geometria do mundo (design/08 §17, §22): funções PURAS, sem banco. Coordenadas X/Y são a base espacial; toda
distância é DERIVADA delas (não existe "distância até a capital" como atributo, 08 §17).

Determinismo: o layout não usa aleatoriedade. Coordenadas são arredondadas a 3 casas para o resultado não
depender do último bit do ponto flutuante entre plataformas.
"""
from __future__ import annotations

import math
from decimal import ROUND_HALF_EVEN, Decimal
from typing import List, Protocol, Tuple

from .constants import DISTANCE_METRICS

_GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))
_Q3 = Decimal("0.001")

Point = Tuple[Decimal, Decimal]


class Located(Protocol):
    x: Decimal
    y: Decimal


def q3(v) -> Decimal:
    return Decimal(repr(float(v))).quantize(_Q3, rounding=ROUND_HALF_EVEN)


def distance(a: Located, b: Located, metric: str = "euclidean") -> Decimal:
    """
    Distância em unidades de grid, derivada das coordenadas. Decimal exato (sqrt do Decimal é determinístico).
    Métrica padrão: euclidiana (decisão do Game Director, 2026-10-03); configurável no cenário (Scenario.distance_metric).
    """
    if metric not in DISTANCE_METRICS:
        raise ValueError(f"Métrica desconhecida: {metric}")
    dx, dy = abs(a.x - b.x), abs(a.y - b.y)
    return dx + dy if metric == "manhattan" else (dx * dx + dy * dy).sqrt()


def spiral_offsets(count: int, spacing: Decimal) -> List[Point]:
    """
    Posições em espiral (ângulo áureo, raio ∝ √i) a partir da origem: o item 0 fica NA origem e os demais se afastam
    sem nunca coincidir. Usada para estados no país e cidades no estado.
    """
    out: List[Point] = []
    for i in range(count):
        r = float(spacing) * math.sqrt(i)
        out.append((q3(r * math.cos(i * _GOLDEN_ANGLE)), q3(r * math.sin(i * _GOLDEN_ANGLE))))
    return out


def neighborhood_offsets(count: int, radius: Decimal) -> List[Point]:
    """
    Bairros CONCENTRADOS em torno de uma região central (08 §3.1: "distribuição concentrada ... semelhante a uma
    distribuição gaussiana/espiral, em vez de uma grade perfeitamente uniforme").

    Raios pelos quantis de uma distribuição de Rayleigh (a radial de uma gaussiana 2D) e ângulos pelo ângulo áureo
    (espiral, sem sobreposição). O índice cresce do centro para a periferia; o último fica a `radius` do centro.
    """
    if count == 1:
        return [(Decimal(0), Decimal(0))]
    sigma = float(radius) / math.sqrt(-2 * math.log(0.5 / count))
    out: List[Point] = []
    for i in range(count):
        u = (i + 0.5) / count
        r = sigma * math.sqrt(-2 * math.log(1 - u))
        out.append((q3(r * math.cos(i * _GOLDEN_ANGLE)), q3(r * math.sin(i * _GOLDEN_ANGLE))))
    return out


def lot_offsets(count: int, spacing: Decimal) -> List[Point]:
    """Lotes numa grade quadrada centrada no bairro (aritmética exata em Decimal)."""
    if count == 0:
        return []
    side = math.isqrt(count - 1) + 1  # ceil(sqrt(count))
    half = Decimal(side - 1) / 2
    return [((Decimal(i % side) - half) * spacing, (Decimal(i // side) - half) * spacing) for i in range(count)]


def add(origin: Point, offset: Point) -> Point:
    return (origin[0] + offset[0], origin[1] + offset[1])
