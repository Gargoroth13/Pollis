"""
Parâmetros do Histórico do Mundo. O design (12 §12.4, §12.12) manda parametrizar limiares e intervalos "para balanceamento após o
Bot Test" mas NÃO dá valores: todos `[PROV]`, na tabela auditável abaixo. O limite de 5★ para a falência é do design (12 §12.5).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List

from .constants import Priority

DAY = 86_400

BANKRUPTCY_MIN_STARS = 5                              # 12.5: falência de empresa de 5★ ou mais "sempre pode gerar notícia"
PRICE_TREND_THRESHOLD_PCT = Decimal("5")              # [PROV] 12.4: |tendência de 7 dias| mínima para virar notícia
MAJOR_TREND_PCT = Decimal("20")                       # [PROV] 12.13: a partir daqui é "grande acontecimento econômico" (senão, "menor")
INDICATOR_MIN_INTERVAL_SECONDS = 3 * DAY              # [PROV] 12.12: intervalo mínimo entre notícias do MESMO indicador (produto)
LAW_PRIORITY = Priority.ELECTION                      # [PROV] 12.13 não lista leis; só desempata notícias no mesmo instante
FEED_PAGE_SIZE = 20                                   # técnico
FEED_MAX_PAGE_SIZE = 100                              # técnico
HEADLINE_MAX = 200                                    # técnico


@dataclass(frozen=True)
class ParamRow:
    parameter: str
    value: str
    source: str
    status: str                 # "DESIGN" | "PROV"
    note: str = ""


def parameter_table() -> List[ParamRow]:
    return [
        ParamRow("bankruptcy_min_stars", str(BANKRUPTCY_MIN_STARS), "12 §12.5", "DESIGN"),
        ParamRow("price_trend_threshold_pct", str(PRICE_TREND_THRESHOLD_PCT), "12 §12.4 (valor ausente)", "PROV", "tendência de 7 dias, em módulo"),
        ParamRow("major_trend_pct", str(MAJOR_TREND_PCT), "12 §12.13 (corte ausente)", "PROV", "separa 'grandes' de 'menores' eventos econômicos"),
        ParamRow("indicator_min_interval_seconds", str(INDICATOR_MIN_INTERVAL_SECONDS), "12 §12.12 (valor ausente)", "PROV", "por produto"),
        ParamRow("law_priority", str(int(LAW_PRIORITY)), "12 §12.13 (leis não listadas)", "PROV", "só desempata no mesmo instante"),
    ]
