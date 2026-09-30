"""
Linha do tempo do jogo: funções PURAS, sem banco e sem relógio real.

Tempo de jogo = número inteiro de SEGUNDOS DE JOGO desde a época do mundo.
Usar inteiros (e não datetime) torna tudo determinístico e barato de comparar.

Convenções técnicas (registradas em CHANGELOG_DEV.md, não são regra de gameplay):
- a época (t = 0) é uma segunda-feira, 00:00 do tempo do jogo;
- "horário do servidor" citado em design/07 é lido como tempo DE JOGO;
- um tick de período P ocorre em t = k*P, k >= 1 (não existe tick em t = 0).
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable, Iterator

SECONDS_PER_HOUR = 3600
HOURS_PER_DAY = 24
DAYS_PER_WEEK = 7
SECONDS_PER_DAY = SECONDS_PER_HOUR * HOURS_PER_DAY
SECONDS_PER_WEEK = SECONDS_PER_DAY * DAYS_PER_WEEK


class TickKind(IntEnum):
    """
    O valor numérico é o RANK de desempate quando vários ticks caem no mesmo
    instante (ex.: segunda 00:00 é HOURLY + DAILY + WEEKLY): horário primeiro,
    semanal por último. Ordem provisória: design/04 §27 ainda a lista como
    questão em aberto.
    """

    HOURLY = 1
    DAILY = 2
    WEEKLY = 3


PERIOD_SECONDS = {
    TickKind.HOURLY: SECONDS_PER_HOUR,
    TickKind.DAILY: SECONDS_PER_DAY,
    TickKind.WEEKLY: SECONDS_PER_WEEK,
}

WEEKDAY_NAMES = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


@dataclass(frozen=True, order=True)
class Tick:
    """Um instante de tick. A ordenação natural já é a ordem de processamento."""

    at: int
    kind: TickKind


def day_of(t: int) -> int:
    """Dia de jogo (0 = primeiro dia)."""
    return t // SECONDS_PER_DAY


def hour_of_day(t: int) -> int:
    return (t % SECONDS_PER_DAY) // SECONDS_PER_HOUR


def weekday_of(t: int) -> int:
    """0 = segunda ... 6 = domingo."""
    return day_of(t) % DAYS_PER_WEEK


def week_of(t: int) -> int:
    return t // SECONDS_PER_WEEK


def describe(t: int) -> str:
    """Texto legível: 'dia 9 (terça) 14:00'. Só apresentação."""
    minutes = (t % SECONDS_PER_HOUR) // 60
    return f"dia {day_of(t)} ({WEEKDAY_NAMES[weekday_of(t)]}) {hour_of_day(t):02d}:{minutes:02d}"


def next_tick_at(after: int, kind: TickKind) -> int:
    """Primeiro instante de tick do tipo `kind` estritamente depois de `after`."""
    period = PERIOD_SECONDS[kind]
    return (max(after, 0) // period + 1) * period


def _kind_ticks(start: int, end: int, kind: TickKind) -> Iterator[Tick]:
    period = PERIOD_SECONDS[kind]
    at = next_tick_at(start, kind)
    while at <= end:
        yield Tick(at, kind)
        at += period


def ticks_between(start: int, end: int, kinds: Iterable[TickKind] = tuple(TickKind)) -> Iterator[Tick]:
    """
    Ticks no intervalo (start, end]: `start` exclusivo, `end` inclusivo.
    Assim, processar (a, b] e depois (b, c] nunca repete nem perde um tick.

    É um GERADOR: uma ausência longa não materializa milhões de objetos.
    Ordem determinística: por instante e, no mesmo instante, por TickKind.
    """
    if end <= start:
        return iter(())
    return heapq.merge(*(_kind_ticks(start, end, k) for k in sorted(set(kinds))))
