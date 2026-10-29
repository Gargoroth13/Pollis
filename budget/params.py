"""
Parâmetros do Orçamento Público (design/09; 11 §11.2.1; 24 §24.16). Valores que o design não dá entram como `[PROV]` na tabela auditável.
As LEIS (P1.12) ainda não existem: os padrões do catálogo `11` valem até lá (mesmo tratamento de salário mínimo e IR em `companies.params`).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, FrozenSet, List

from companies.params import ProvisionalRow
from ledger.constants import Nature

from .constants import FLOOR_AREAS, Area

SOURCE = "09 FINAL; 11 §11.2.1; 24 §24.16"

# 09 §8: "O ciclo orçamentário padrão será de 30 dias." O design não diz de onde contam: contam da ÉPOCA do jogo (`budget.periods`). [PROV]
PERIOD_DAYS = 30
PERIOD_ANCHOR_RULE = "game_epoch"

# 24 §24.16 (decisão do GD 2026-10-15): janela móvel de 360 dias, mínimo de 30 dias de histórico, referência anualizada.
WINDOW_DAYS = 360
MIN_WINDOW_DAYS = 30

# 11 §11.2.1 / tabela de leis (mín–máx–PADRÃO): teto de déficit 0%–50% (padrão 10%); pisos Educação 5%–30% (10%), Saúde 1%–30% (10%),
# Infraestrutura 1%–30% (10%). Enquanto não existir o motor de leis (P1.12), vale o PADRÃO. [PROV]
DEFICIT_CEILING_PCT = Decimal("10")
DEFICIT_CEILING_RANGE = (Decimal("0"), Decimal("50"))
FLOOR_PCT: Dict[Area, Decimal] = {Area.EDUCATION: Decimal("10"), Area.HEALTH: Decimal("10"), Area.INFRASTRUCTURE: Decimal("10")}
FLOOR_RANGE: Dict[Area, tuple] = {Area.EDUCATION: (Decimal("5"), Decimal("30")), Area.HEALTH: (Decimal("1"), Decimal("30")),
                                  Area.INFRASTRUCTURE: (Decimal("1"), Decimal("30"))}

# 09 §11 manda priorizar as obrigações já assumidas; 24 §24.9 deixa à P1.09 decidir se isso bloqueia repasses. GD 2026-10-29 (mantida): o governo só repassa o que sobra
# depois do comprometido E das obrigações pendentes (design/09a, K3).
TRANSFERS_RESPECT_PENDING_OBLIGATIONS = True

# Classificação das naturezas do ledger (24 §24.8, lista fechada) para receita/despesa do §24.16. REGRA: o que ENTRA na conta é receita, o que SAI é despesa,
# exceto os itens abaixo, que o `24` manda NÃO contar. Natureza que o `24` não cita fica na regra geral (receita "não financeira" / despesa real).
#   Receita NÃO conta: dotações iniciais, emissão de títulos, dinheiro ainda retido.
NOT_REVENUE: FrozenSet[Nature] = frozenset({Nature.SCENARIO_GRANT, Nature.BOND_PURCHASE, Nature.RETENTION_IN})
#   Despesa NÃO conta: transferências a níveis inferiores, amortização do principal, dinheiro enviado à retenção.
NOT_EXPENSE: FrozenSet[Nature] = frozenset({Nature.GOV_TRANSFER, Nature.BOND_REDEMPTION, Nature.RETENTION_IN})


def provisional_table() -> List[ProvisionalRow]:
    rows = [
        ProvisionalRow("budget", "period_days", str(PERIOD_DAYS), "ciclo orçamentário padrão (09 §8)", "09 §8", status="GD"),
        ProvisionalRow("budget", "period_anchor", PERIOD_ANCHOR_RULE, "o design não diz de onde contam os períodos de 30 dias: da época do jogo",
                       "09 §8", status="PROV"),
        ProvisionalRow("budget", "window_days", str(WINDOW_DAYS), "janela móvel do teto de déficit (24 §24.16)", "24 §24.16", status="GD"),
        ProvisionalRow("budget", "min_window_days", str(MIN_WINDOW_DAYS), "histórico mínimo para o teto bloquear (24 §24.16)", "24 §24.16", status="GD"),
        ProvisionalRow("budget", "deficit_ceiling_pct", str(DEFICIT_CEILING_PCT),
                       f"teto de déficit; faixa {DEFICIT_CEILING_RANGE[0]}–{DEFICIT_CEILING_RANGE[1]}%; padrão de 11 até o motor de leis (P1.12)",
                       "11 §11.2.1", status="PROV"),
    ]
    for area in FLOOR_AREAS:
        lo, hi = FLOOR_RANGE[area]
        rows.append(ProvisionalRow("budget", f"floor_pct.{area.value}", str(FLOOR_PCT[area]),
                                   f"piso municipal; faixa {lo}–{hi}%; padrão de 11 até o motor de leis (P1.12); base: receitas de 30 dias (11 §11.2.1)",
                                   "11 §11.2.1", status="PROV"))
    rows.append(ProvisionalRow("budget", "transfers_respect_pending_obligations", str(TRANSFERS_RESPECT_PENDING_OBLIGATIONS),
                               "repasse só do que sobra após comprometido e obrigações pendentes (09 §11; 24 §24.9 deixa à P1.09)", "GD 2026-10-29", status="GD"))
    rows.append(ProvisionalRow("budget", "not_revenue", ",".join(sorted(n.value for n in NOT_REVENUE)),
                               "o que não conta como receita (24 §24.16)", "24 §24.16", status="GD"))
    rows.append(ProvisionalRow("budget", "not_expense", ",".join(sorted(n.value for n in NOT_EXPENSE)),
                               "o que não conta como despesa (24 §24.16)", "24 §24.16", status="GD"))
    return rows
