"""
Linha do tempo do jogo: funções PURAS (sem banco, sem relógio real).

Modelo (decisão do Game Director, 2026-09-30):
- O tempo do jogo É o tempo real: segundos, dias e meses reais do calendário.
- O calendário do jogo usa a SUA PRÓPRIA time zone (settings.POLIS_GAME_TIMEZONE),
  nunca a do usuário.
- Só a VELOCIDADE pode ser acelerada (Bot Test: 1 dia = 10 min reais). Ver clock.py.

Representação: tempo de jogo = inteiro de segundos desde 1970-01-01 UTC, do
relógio de JOGO (com velocidade 1x é exatamente o Unix time real). Inteiros
mantêm tudo determinístico e barato de comparar.

Ticks:
- HOURLY : a cada 3600 s absolutos (alinhado à hora UTC; não muda com DST).
- DAILY  : 00:00 local, todo dia.
- WEEKLY : segunda-feira 00:00 local (design/07).
- MONTHLY: dia 1, 00:00 local, mês de calendário real (28-31 dias).
Um tick em t cobre o instante t; intervalos são (start, end].
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo
from enum import IntEnum
from typing import Iterable, Iterator, Optional
from zoneinfo import ZoneInfo

from django.conf import settings

SECONDS_PER_HOUR = 3600
SECONDS_PER_DAY = 24 * SECONDS_PER_HOUR
SECONDS_PER_WEEK = 7 * SECONDS_PER_DAY


class TickKind(IntEnum):
    """
    O valor numérico é o RANK de desempate quando vários ticks caem no mesmo
    instante (ex.: dia 1 que cai numa segunda é HOURLY+DAILY+WEEKLY+MONTHLY):
    do menor período para o maior. Ordem provisória: design/04 §27 ainda a
    lista como questão em aberto.
    """

    HOURLY = 1
    DAILY = 2
    WEEKLY = 3
    MONTHLY = 4


WEEKDAY_NAMES = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


@dataclass(frozen=True, order=True)
class Tick:
    """Um instante de tick. A ordenação natural já é a ordem de processamento."""

    at: int
    kind: TickKind


# --- fuso e calendário ---------------------------------------------------

def game_tz() -> tzinfo:
    """Time zone do jogo (não a do usuário)."""
    return ZoneInfo(getattr(settings, "POLIS_GAME_TIMEZONE", settings.TIME_ZONE))


def local_dt(t: int, tz: Optional[tzinfo] = None) -> datetime:
    """Data/hora local do jogo correspondente ao tempo de jogo `t`."""
    return datetime.fromtimestamp(t, tz or game_tz())


def game_ts(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0,
            tz: Optional[tzinfo] = None) -> int:
    """Tempo de jogo de uma data/hora LOCAL do jogo. Útil em testes e seeds."""
    return int(datetime(year, month, day, hour, minute, second, tzinfo=tz or game_tz()).timestamp())


def weekday_of(t: int, tz: Optional[tzinfo] = None) -> int:
    """0 = segunda ... 6 = domingo (calendário local do jogo)."""
    return local_dt(t, tz).weekday()


def describe(t: int, tz: Optional[tzinfo] = None) -> str:
    """Texto legível: '2026-09-30 (quarta) 14:30'. Só apresentação."""
    d = local_dt(t, tz)
    return f"{d:%Y-%m-%d} ({WEEKDAY_NAMES[d.weekday()]}) {d:%H:%M}"


# --- ticks ---------------------------------------------------------------

def _midnight_ts(d: date, tz: tzinfo) -> int:
    # fold=0 e fuso com lacuna de DST à meia-noite: o instante resolve para o
    # primeiro horário existente do dia, sem duplicar nem voltar no tempo.
    return int(datetime(d.year, d.month, d.day, tzinfo=tz).timestamp())


def next_tick_at(after: int, kind: TickKind, tz: Optional[tzinfo] = None) -> int:
    """Primeiro instante de tick do tipo `kind` estritamente depois de `after`."""
    if kind is TickKind.HOURLY:
        return (after // SECONDS_PER_HOUR + 1) * SECONDS_PER_HOUR
    tz = tz or game_tz()
    today = local_dt(after, tz).date()
    if kind is TickKind.DAILY:
        target = today + timedelta(days=1)
    elif kind is TickKind.WEEKLY:
        target = today + timedelta(days=7 - today.weekday())  # próxima segunda
    elif kind is TickKind.MONTHLY:
        target = date(today.year + (today.month == 12), today.month % 12 + 1, 1)
    else:  # pragma: no cover
        raise ValueError(kind)
    return _midnight_ts(target, tz)


def _kind_ticks(start: int, end: int, kind: TickKind, tz: tzinfo) -> Iterator[Tick]:
    at = next_tick_at(start, kind, tz)
    while at <= end:
        yield Tick(at, kind)
        nxt = next_tick_at(at, kind, tz)
        if nxt <= at:
            # Nunca deve ocorrer. Se ocorrer (ex.: anomalia de DST num fuso novo),
            # falhar alto é melhor do que travar o processo num laço infinito.
            raise RuntimeError(f"next_tick_at não avançou: {kind.name} {at} -> {nxt} (tz={tz})")
        at = nxt


def ticks_between(start: int, end: int, kinds: Iterable[TickKind] = tuple(TickKind),
                  tz: Optional[tzinfo] = None) -> Iterator[Tick]:
    """
    Ticks em (start, end]: `start` exclusivo, `end` inclusivo. Assim, processar
    (a, b] e depois (b, c] nunca repete nem perde um tick.

    É um GERADOR: uma ausência longa não materializa milhões de objetos.
    Ordem determinística: por instante e, no mesmo instante, por TickKind.
    """
    if end <= start:
        return iter(())
    tz = tz or game_tz()
    return heapq.merge(*(_kind_ticks(start, end, k, tz) for k in sorted(set(kinds))))
