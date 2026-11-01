"""
Parâmetros do processo legislativo. Prazos de 3 dias são do design (07 §07.5, §07.8, §07.12) e NÃO são ajustáveis por lei.
Os cooldowns (07 §07.11) são "parâmetros técnicos de balanceamento" sem valor no design: `[PROV]`, tabela auditável abaixo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

DAY = 86400

DISCUSSION_DAYS = 3             # 07.5: dias de calendário (contando o dia da criação; ver design/07a, L1)
VOTING_SECONDS = 3 * DAY        # 07.8
SANCTION_SECONDS = 3 * DAY      # 07.12
OVERRIDE_NUMERATOR, OVERRIDE_DENOMINATOR = 2, 3     # 07.15: 2/3 de TODAS as cadeiras consideradas

COOLDOWN_SECONDS = 7 * DAY              # [PROV] 07.11: reapresentar uma proposta rejeitada da mesma lei
COOLDOWN_MODIFIED_SECONDS = 3 * DAY     # [PROV] 07.11: com alteração real de algum parâmetro X
DESCRIPTION_MAX = 1000                  # técnico (limite de texto)
JUSTIFICATION_MAX = 1000


@dataclass(frozen=True)
class ParamRow:
    parameter: str
    value: str
    source: str
    status: str                 # "DESIGN" | "PROV"
    note: str = ""


def parameter_table() -> List[ParamRow]:
    return [
        ParamRow("discussion_days", str(DISCUSSION_DAYS), "07 §07.5", "DESIGN"),
        ParamRow("voting_seconds", str(VOTING_SECONDS), "07 §07.8", "DESIGN"),
        ParamRow("sanction_seconds", str(SANCTION_SECONDS), "07 §07.12", "DESIGN"),
        ParamRow("override_fraction", f"{OVERRIDE_NUMERATOR}/{OVERRIDE_DENOMINATOR}", "07 §07.15", "DESIGN"),
        ParamRow("cooldown_seconds", str(COOLDOWN_SECONDS), "07 §07.11 (valor ausente)", "PROV"),
        ParamRow("cooldown_modified_seconds", str(COOLDOWN_MODIFIED_SECONDS), "07 §07.11 (valor ausente)", "PROV"),
    ]
