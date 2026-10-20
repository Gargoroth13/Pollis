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


# --- produção (02 §5-8, §13, §18, §22: "valores calibrados principalmente através dos testes com bots") ----------------------
# Todos `[PROV]` (GD 2026-10-14, Q3): estrutura do design, números calibráveis. A progressão de estrelas está em `design/02a`.
PRODUCING_TYPES = frozenset({CompanyType.MATRIX, CompanyType.INDUSTRIAL})     # 02 §2.1-2.2; Construtora: obra (P1.04e)
UNITS_PER_WORK_BASE = Decimal(1)                 # 02 §7: skill 1 e especialização 0 → ~1 unidade por trabalho
SKILL_PRODUCTION_PER_LEVEL = Decimal("0.02")     # curva `linear_prov`: fator = 1 + nível × 0,02 (01 §1.6: relação em aberto)
SPECIALIZATION_PRODUCTION_PER_POINT = Decimal("0.01")   # fator = 1 + especialização × 0,01 (02 §7, §13)
PRODUCTION_CURVE = "linear_prov"                 # usada quando o balanceamento de Skills não define outra (≠ "none")
STARS = (1, 2, 3, 4, 5)
STOCK_CAPACITY_PER_STAR = {n: 500 * n for n in STARS}      # 02 §11.1, §22: unidades de estoque por estrela
QUALITY_CAP_PER_STAR = {n: Decimal(100 * n) for n in STARS}    # 02 §8, §18: teto de qualidade, na escala dos níveis de skill
SETUP_SECONDS = 6 * 3600                         # 02 §5.3: setup "significativamente menor que o cooldown"
COOLDOWN_SECONDS = 7 * 86_400                    # 02 §5.3: "aproximadamente uma semana"
PRODUCTION_CHANGE_COST_CENTS = 0                 # 02 §5.3: "custo fixo"; natureza/destino do dinheiro não definidos no 24 (GAP)


# --- cargos de suporte (02 §9, §22) `[PROV]` ------------------------------------------------------------------------------------
# Engenheiro: cada trabalho soma `ENGINEER_BONUS_PER_WORK × fator de skill × fator de especialização` ao bônus do DIA da empresa;
# a produção por trabalho de cada funcionário de produção é multiplicada por `1 + bônus do dia` (o bônus reinicia a cada dia).
# Calibração (alvo de balanceamento do 02 §9.1, "~2,5× da produção base"): empresa 5★ com 5 Engenheiros, 5 trabalhos cada (uma
# barra de Energia = 100/20), skill no nível máximo (fator 3) e sem especialização → 25 × 0,02 × 3 = 1,5 → 2,5×.
# Advogado: mesma forma; a soma diária REDUZ o multiplicador de risco de Burnout dos funcionários (1 − redução, piso 1% em `players`).
ENGINEER_BONUS_PER_WORK = Decimal("0.02")
LAWYER_REDUCTION_PER_WORK = Decimal("0.02")
SUPPORT_LIMIT_PER_STAR = {n: n for n in STARS}      # 02 §9: "limitada pela estrela" (02a §2.3: Engenheiros/Advogados = estrela)
LAWYER_SPECIALIZATION_KEY = "support:lawyer"         # 02 §13: o Advogado se especializa na própria atividade


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
    for name, value, rule in (
            ("production.producing_types", ",".join(sorted(t.value for t in PRODUCING_TYPES)), "tipos que escolhem produto (02 §5)"),
            ("production.units_per_work_base", str(UNITS_PER_WORK_BASE), "unidades por trabalho com skill 1 e especialização 0 (02 §7)"),
            ("production.skill_per_level", str(SKILL_PRODUCTION_PER_LEVEL), "curva linear de skill → produção (01 §1.6 em aberto)"),
            ("production.specialization_per_point", str(SPECIALIZATION_PRODUCTION_PER_POINT), "especialização → produção (02 §7)"),
            ("production.curve", PRODUCTION_CURVE, "curva de skill usada se o balanceamento de Skills estiver em 'none'"),
            ("stock.capacity_per_star", ",".join(f"{n}:{v}" for n, v in STOCK_CAPACITY_PER_STAR.items()),
             "estoque máximo (unidades) por estrela (02 §11.1)"),
            ("quality.cap_per_star", ",".join(f"{n}:{v}" for n, v in QUALITY_CAP_PER_STAR.items()),
             "teto de qualidade por estrela (02 §8, §18)"),
            ("production.setup_seconds", str(SETUP_SECONDS), "setup ao trocar de produto (02 §5.3)"),
            ("production.cooldown_seconds", str(COOLDOWN_SECONDS), "cooldown entre trocas (02 §5.3)"),
            ("production.change_cost_cents", str(PRODUCTION_CHANGE_COST_CENTS), "custo fixo da troca (02 §5.3); > 0 exige natureza no 24")):
        rows.append(ProvisionalRow("companies", name, value, rule, SOURCE))
    for name, value, rule in (
            ("support.engineer_bonus_per_work", str(ENGINEER_BONUS_PER_WORK), "bônus diário de produção por trabalho de Engenheiro (02 §9.1)"),
            ("support.lawyer_reduction_per_work", str(LAWYER_REDUCTION_PER_WORK), "redução diária do risco de Burnout por trabalho de Advogado (02 §9.2)"),
            ("support.limit_per_star", ",".join(f"{n}:{v}" for n, v in SUPPORT_LIMIT_PER_STAR.items()),
             "máximo de vagas de Engenheiro e de Advogado por estrela (02 §9; 02a §2.3)"),
            ("support.lawyer_specialization_key", LAWYER_SPECIALIZATION_KEY, "chave de especialização do Advogado (02 §13)")):
        rows.append(ProvisionalRow("companies", name, value, rule, SOURCE))
    for kind in PositionKind:
        rows.append(ProvisionalRow("companies", f"relevant_skill.{kind.value}", RELEVANT_SKILL[kind].value,
                                   "skill relevante do cargo para S (01 §1.7-1.8): distribuição refinada em Empresas", SOURCE))
    for ctype in CompanyType:
        rows.append(ProvisionalRow("companies", f"hirable_kinds.{ctype.value}",
                                   ",".join(sorted(k.value for k in HIRABLE_KINDS[ctype])),
                                   "cargos que a empresa pode abrir no mural (02 §9, §11.2)", SOURCE))
    return rows
