"""
Parâmetros `[PROV]` das Empresas (GD 2026-10-14, Q3): valores iniciais calibráveis, em tabela AUDITÁVEL. O design (02 §14, §22)
define a ESTRUTURA e manda manter os números parametrizados.

Estrelas: toda empresa nasce com 1★ `[PROV]` e sobe por melhorias compradas com o caixa (GD 2026-10-19, `02` §25.1). A
progressão está na proposta `design/02a-estrelas-PROPOSTA.md` e NÃO é implementada antes de aprovada.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, FrozenSet, List

from ledger.money import from_reais
from skills.constants import Skill

from .constants import CompanyType, PositionKind

SOURCE = "GD 2026-10-14 Q3 [PROV]"

INITIAL_STARS = 1        # estrela de uma empresa recém-fundada (02 §14; GD 2026-10-19: 1★ [PROV])

# --- salário (01 §1.7; 11 §11.1.0) -------------------------------------------------------------------------------------
# Padrões das LEIS PARAMÉTRICAS (11 §11.1). Enquanto o sistema de leis (P1.12) não existe, valem os padrões do próprio 11.
MIN_WAGE_PER_DAY_CENTS = from_reais(50)           # 11 §11.1: salário mínimo, padrão R$ 50/dia
WAGE_CEILING_PER_DAY_CENTS = None                  # 11 §11.1: teto salarial T, padrão "sem teto" (None ≠ 0)
INCOME_TAX_RATE = Decimal("0.05")                  # 11 §11.1: imposto de renda sobre salários pagos, padrão 5%

# --- skill relevante por cargo (01 §1.8: "a distribuição exata dos cargos entre as três skills será refinada" em Empresas) --
# [PROV]: Físico = operação/produção; Inteligência = cargos intelectuais, gestão (Dono) e jurídico; Carisma = vendas.
RELEVANT_SKILL: Dict[PositionKind, Skill] = {
    PositionKind.OWNER: Skill.INTELLIGENCE,
    PositionKind.WORKER: Skill.PHYSICAL,
    PositionKind.ENGINEER: Skill.INTELLIGENCE,
    PositionKind.LAWYER: Skill.INTELLIGENCE,
    PositionKind.SALESPERSON: Skill.CHARISMA,
}

# --- cargos que cada tipo de empresa pode abrir [PROV] (02 §11.2: funcionários do Varejo vendem; §9: suporte em geral) ------
_SUPPORT = frozenset({PositionKind.ENGINEER, PositionKind.LAWYER})
HIRABLE_KINDS: Dict[CompanyType, FrozenSet[PositionKind]] = {
    CompanyType.RETAIL: frozenset({PositionKind.SALESPERSON}) | _SUPPORT,
    CompanyType.SERVICES: frozenset({PositionKind.WORKER}) | _SUPPORT,
    CompanyType.MATRIX: frozenset({PositionKind.WORKER}) | _SUPPORT,
    CompanyType.INDUSTRIAL: frozenset({PositionKind.WORKER}) | _SUPPORT,
    CompanyType.CONSTRUCTION: frozenset({PositionKind.WORKER}) | _SUPPORT,
    CompanyType.FINANCIAL: frozenset({PositionKind.WORKER}) | _SUPPORT,
}


@dataclass(frozen=True)
class ProvisionalRow:
    scope: str
    parameter: str
    value: str
    rule: str
    source: str
    status: str = "PROV"


def provisional_table() -> List[ProvisionalRow]:
    rows = [ProvisionalRow("companies", "initial_stars", str(INITIAL_STARS),
                           "estrela inicial; progressão por melhorias pagas pelo caixa (02 §25.1; proposta em 02a)", SOURCE)]
    rows.append(ProvisionalRow("companies", "min_wage_per_day_cents", str(MIN_WAGE_PER_DAY_CENTS),
                               "W: padrão da lei de salário mínimo (11 §11.1) até o sistema de leis existir", "11 §11.1 padrão"))
    rows.append(ProvisionalRow("companies", "wage_ceiling_per_day_cents", "None",
                               "T: padrão 'sem teto' (11 §11.1); None não é zero", "11 §11.1 padrão"))
    rows.append(ProvisionalRow("companies", "income_tax_rate", str(INCOME_TAX_RATE),
                               "IR sobre salário pago (11 §11.1) até o sistema de leis existir", "11 §11.1 padrão"))
    for kind in PositionKind:
        rows.append(ProvisionalRow("companies", f"relevant_skill.{kind.value}", RELEVANT_SKILL[kind].value,
                                   "skill relevante do cargo para S (01 §1.7-1.8): distribuição refinada em Empresas", SOURCE))
    for ctype in CompanyType:
        rows.append(ProvisionalRow("companies", f"hirable_kinds.{ctype.value}",
                                   ",".join(sorted(k.value for k in HIRABLE_KINDS[ctype])),
                                   "cargos que a empresa pode abrir no mural (02 §9, §11.2)", SOURCE))
    return rows
