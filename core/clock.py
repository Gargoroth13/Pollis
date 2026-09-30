"""
Relógio do jogo, INJETÁVEL.

Nenhuma regra de jogo deve chamar timezone.now() ou time.time(). Regras
recebem/pedem o tempo de jogo por aqui. Isso permite testes e bots
determinísticos (ManualClock) e o ambiente acelerado do Bot Test.
"""
from __future__ import annotations

import contextlib
import contextvars
from typing import Callable, Iterator, Optional, Protocol

from django.db import transaction
from django.utils import timezone

from .models import WorldClock
from .timeline import SECONDS_PER_DAY, SECONDS_PER_HOUR


class Clock(Protocol):
    def now(self) -> int:
        """Tempo de jogo atual, em segundos de jogo desde a época."""


class RealtimeClock:
    """Relógio de produção: deriva o tempo de jogo do relógio real + WorldClock."""

    def __init__(self, real_now: Callable = timezone.now):
        self._real_now = real_now

    def now(self) -> int:
        return WorldClock.load().game_time_at(self._real_now())


class ManualClock:
    """Relógio de teste/simulação: só anda quando mandado. Nunca retrocede."""

    def __init__(self, start: int = 0):
        self._t = int(start)

    def now(self) -> int:
        return self._t

    def set(self, t: int) -> None:
        if t < self._t:
            raise ValueError("O relógio do jogo não pode retroceder.")
        self._t = int(t)

    def advance(self, *, seconds: int = 0, hours: int = 0, days: int = 0, weeks: int = 0) -> int:
        delta = seconds + hours * SECONDS_PER_HOUR + days * SECONDS_PER_DAY + weeks * 7 * SECONDS_PER_DAY
        if delta < 0:
            raise ValueError("O relógio do jogo não pode retroceder.")
        self._t += delta
        return self._t


_override: contextvars.ContextVar[Optional[Clock]] = contextvars.ContextVar("polis_clock", default=None)
_default = RealtimeClock()


def get_clock() -> Clock:
    return _override.get() or _default


def now() -> int:
    """Atalho: tempo de jogo atual segundo o relógio ativo."""
    return get_clock().now()


@contextlib.contextmanager
def use_clock(clock: Clock) -> Iterator[Clock]:
    """Troca o relógio ativo dentro do bloco (por thread/contexto)."""
    token = _override.set(clock)
    try:
        yield clock
    finally:
        _override.reset(token)


def set_speed(real_seconds_per_game_day: int, *, real_now: Callable = timezone.now) -> WorldClock:
    """
    Muda a velocidade do mundo sem salto de tempo: re-ancora no instante atual.
    """
    if real_seconds_per_game_day < 1:
        raise ValueError("real_seconds_per_game_day deve ser >= 1.")
    with transaction.atomic():
        wc = WorldClock.load(for_update=True)
        instant = real_now()
        wc.anchor_game = wc.game_time_at(instant)
        wc.anchor_real = instant
        wc.real_seconds_per_game_day = real_seconds_per_game_day
        wc.save(update_fields=["anchor_game", "anchor_real", "real_seconds_per_game_day"])
    return wc
