"""
Distribuição ESPACIAL de recursos (design/08 §13-15, §23.2-3). Funções puras e determinísticas.

O 08 exige que um lote NÃO faça uma rolagem independente; os recursos devem formar "regiões de maior e menor
concentração" e "raridade e localização são conceitos diferentes: a raridade define a frequência GLOBAL; a
distribuição espacial define ONDE os recursos se concentram".

Método (uma entre várias formas possíveis; o 08 não prescreve algoritmo):
  1. campo contínuo = soma de concentrações gaussianas (hotspots) centradas em lotes rurais, sorteadas com semente;
  2. os lotes com maior valor de campo recebem o depósito, até completar a fração global = raridade.
Assim a frequência global é EXATA (arredondada ao lote), os depósitos se agrupam em regiões e há regiões sem
nenhuma ocorrência. A `richness` é o valor do campo relativo ao lote mais rico (depósitos maiores e menores).
"""
from __future__ import annotations

import math
import random
from decimal import ROUND_HALF_EVEN, Decimal
from typing import List, Sequence, Tuple

Pt = Tuple[float, float]


def target_count(total_lots: int, rarity: Decimal) -> int:
    """Quantos lotes devem ter o recurso: fração global = raridade, arredondada ao lote."""
    return int((Decimal(total_lots) * rarity).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def field_values(points: Sequence[Pt], seed: int, resource: str, hotspots: int, sigma: float) -> List[float]:
    """Valor do campo em cada ponto. Semente por (seed, recurso): recursos diferentes têm regiões diferentes."""
    if not points:
        return []
    rng = random.Random(f"{seed}:{resource}")
    centers = rng.sample(list(points), k=min(hotspots, len(points)))
    weights = [rng.uniform(0.5, 1.5) for _ in centers]
    two_s2 = 2.0 * sigma * sigma
    return [sum(w * math.exp(-((x - cx) ** 2 + (y - cy) ** 2) / two_s2) for (cx, cy), w in zip(centers, weights))
            for x, y in points]


def select(points: Sequence[Pt], rarity: Decimal, seed: int, resource: str, hotspots: int, sigma: float
           ) -> List[Tuple[int, Decimal]]:
    """
    Devolve [(índice do ponto, richness)] dos lotes que recebem o recurso, em ordem de índice.
    `richness` em (0, 1]: campo / campo do lote mais rico (3 casas, mínimo 0,001).
    """
    n = target_count(len(points), rarity)
    if n == 0:
        return []
    values = field_values(points, seed, resource, hotspots, sigma)
    ranked = sorted(range(len(points)), key=lambda i: (-values[i], i))[:n]   # desempate por índice: determinístico
    top = values[ranked[0]]
    out = []
    for i in sorted(ranked):
        rel = Decimal(repr(values[i] / top if top > 0 else 1.0)).quantize(Decimal("0.001"), rounding=ROUND_HALF_EVEN)
        out.append((i, max(Decimal("0.001"), min(Decimal(1), rel))))
    return out
