"""
Parâmetros das Escolas. O `03` (REVIEW) define a ESTRUTURA e manda manter tudo parametrizado (§27); os números marcados `[PROV]`
são iniciais, calibráveis nos testes com Bots, e estão numa tabela AUDITÁVEL (nenhum valor inventado fora daqui).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict

from .constants import MAX_STARS, MIN_STARS

# 03 §4: vagas = residências possíveis no bairro × 1,5 ("O multiplicador deve ser parametrizado"). DEFINIDO no design.
CAPACITY_MULTIPLIER = Decimal("1.5")

# 03 §2/§13: estrela inicial da escola. `[PROV]`: o 03 não diz; segue o padrão das empresas (02 §25.1, GD 2026-10-19: 1★ [PROV]).
INITIAL_STARS = 1

# 03 §8: "escola 3★ → máximo de 1.000 materiais → qualidade base máxima de 1.000"; "a quantidade exata por estrela será definida
# posteriormente". `[PROV]`: reta que passa pelo único ponto dado (3★ = 1.000): 1★ 333, 2★ 667, 3★ 1.000, 4★ 1.333, 5★ 1.667.
MATERIALS_MAX_PER_STAR: Dict[int, int] = {n: round(1000 * n / 3) for n in range(MIN_STARS, MAX_STARS + 1)}

# 03 §9: "a taxa de decaimento será definida posteriormente". `[PROV]`: 2% do estoque do ciclo por dia (arredondado, HALF_EVEN).
MATERIAL_DECAY_RATE = Decimal("0.02")

# 03 §8: materiais → qualidade base 1:1 (o exemplo: máximo de 1.000 materiais ↔ qualidade base máxima de 1.000).
QUALITY_PER_MATERIAL = Decimal(1)

SOURCE = "03 REVIEW; valores [PROV]"
