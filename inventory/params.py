"""
Parâmetros `[PROV]` do Inventário (GD 2026-10-14, Q3): valores iniciais, calibráveis durante o Bot Test, registrados numa tabela
AUDITÁVEL com a fonte de verdade. NÃO são regra de design: o design (05 §12, §21; 04 §15) define a ESTRUTURA e manda manter estes
números parametrizados. Calibrar é mudar o valor aqui; `provisional_table()` os exporta (e um teste confere que a tabela
cobre todo parâmetro).

Fórmula da taxa do Correio (05 §12): `taxa = MAX(taxa_mínima, valor_de_referência × percentual)`, onde o valor de referência é
o `base_price` do catálogo × quantidade (`17 §20`: é referência, nunca preço de mercado).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List

SOURCE = "GD 2026-10-14 Q3 [PROV]"

MAIL_FEE_RATE = Decimal("0.10")          # percentual da taxa de correio sobre o valor de referência (05 §12, §21)
MAIL_FEE_MIN_CENTS = 100                 # taxa mínima de correio, em centavos (R$ 1,00) (05 §12, §21)
FOOD_EFFECT_DURATION_SECONDS = 3600      # duração do efeito temporário de QoL da categoria Comida (04 §4.4, §27)


@dataclass(frozen=True)
class ProvisionalRow:
    scope: str
    parameter: str
    value: str
    rule: str
    source: str
    status: str = "PROV"


def provisional_table() -> List[ProvisionalRow]:
    """TODA linha provisória do Inventário (escopo, parâmetro, valor, regra, fonte)."""
    return [
        ProvisionalRow("inventory", "mail_fee_rate", str(MAIL_FEE_RATE),
                       "taxa = MAX(mínimo, valor de referência × percentual); 05 §12", SOURCE),
        ProvisionalRow("inventory", "mail_fee_min_cents", str(MAIL_FEE_MIN_CENTS),
                       "taxa mínima do Correio em centavos; 05 §12", SOURCE),
        ProvisionalRow("inventory", "food_effect_duration_seconds", str(FOOD_EFFECT_DURATION_SECONDS),
                       "duração do efeito temporário de Comida (um novo efeito substitui o anterior); 04 §4.4, §16", SOURCE),
    ]
