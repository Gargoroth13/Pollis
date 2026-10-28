"""Períodos orçamentários de 30 dias (09 §8). Os períodos contam da ÉPOCA do jogo (`[PROV]`, o design não diz de onde contam)."""
from __future__ import annotations

from typing import Tuple

from ledger.money import competence_day_of

from . import params

EPOCH_DAY = competence_day_of(0)


def period_of(day: int) -> int:
    return (day - EPOCH_DAY) // params.PERIOD_DAYS


def bounds_of(period: int) -> Tuple[int, int]:
    """Primeiro e último dia (inclusive) do período."""
    first = EPOCH_DAY + period * params.PERIOD_DAYS
    return first, first + params.PERIOD_DAYS - 1
