"""
Parâmetros `[PROV]` das Empresas (GD 2026-10-14, Q3): valores iniciais calibráveis, em tabela AUDITÁVEL. O design (02 §14, §22)
define a ESTRUTURA (estrelas = potencial da empresa) e manda manter os números parametrizados; o que NÃO está definido em
nenhum documento é como uma empresa SOBE de estrela: isso não foi implementado nem inventado (decisão pendente do GD).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

SOURCE = "GD 2026-10-14 Q3 [PROV]"

INITIAL_STARS = 1        # estrela de uma empresa recém-fundada (02 §14: "estrutura e potencial da empresa")


@dataclass(frozen=True)
class ProvisionalRow:
    scope: str
    parameter: str
    value: str
    rule: str
    source: str
    status: str = "PROV"


def provisional_table() -> List[ProvisionalRow]:
    return [ProvisionalRow("companies", "initial_stars", str(INITIAL_STARS),
                           "estrela inicial da empresa fundada; evolução de estrelas não definida no design (02 §14)", SOURCE)]
