"""Calendário das ocorrências (18.5). Dias de competência são o ordinal da data do calendário local do jogo."""
from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

from .constants import MAX_OCCURRENCES, Frequency


def shift(anchor_day: int, frequency: Frequency, k: int) -> int:
    """Dia da ocorrência `k` (a partir de 0) de uma série ancorada em `anchor_day`. Mensal: mesmo dia do mês, limitado ao fim do mês."""
    if frequency is Frequency.ONCE:
        return anchor_day if k == 0 else anchor_day + 10 ** 9
    if frequency is Frequency.DAILY:
        return anchor_day + k
    if frequency is Frequency.WEEKLY:
        return anchor_day + 7 * k
    start = date.fromordinal(anchor_day)
    index = start.month - 1 + k
    year, month = start.year + index // 12, index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1])).toordinal()


def count_until(anchor_day: int, frequency: Frequency, ends_on: int) -> Optional[int]:
    """Quantas ocorrências cabem em [anchor_day, ends_on]. None se passar do limite técnico."""
    if ends_on < anchor_day:
        return 0
    if frequency is Frequency.ONCE:
        return 1
    n = 0
    while shift(anchor_day, frequency, n) <= ends_on:
        n += 1
        if n > MAX_OCCURRENCES:
            return None
    return n
