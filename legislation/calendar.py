"""
Calendário legislativo (design/07 §07.5-§07.8, §07.16). Funções PURAS sobre o tempo de jogo (segundos); sem banco, sem relógio.

`weekly tick` = segunda-feira 00:00 no fuso do JOGO (`core.timeline`).
"""
from __future__ import annotations

from datetime import timedelta

from core import timeline

from . import params


def _midnight(day, tz) -> int:
    return timeline._midnight_ts(day, tz)


def discussion_ends_at(created_at: int) -> int:
    """00:00 do 4º dia contado a partir do dia da criação: 3 dias de CALENDÁRIO, contando o dia da criação (design/07a, L1).

    Enviada na sexta (a qualquer hora) → termina na segunda 00:00: entra na votação dessa segunda (07 §07.6)."""
    tz = timeline.game_tz()
    day = timeline.local_dt(created_at, tz).date()
    return _midnight(day + timedelta(days=params.DISCUSSION_DAYS), tz)


def monday_at_or_after(t: int) -> int:
    """Primeira segunda-feira 00:00 com instante ≥ t."""
    return t if is_weekly_tick(t) else timeline.next_tick_at(t, timeline.TickKind.WEEKLY)


def monday_after(t: int) -> int:
    """Primeiro `weekly tick` ESTRITAMENTE depois de t (07 §07.16: "no próximo weekly tick")."""
    return timeline.next_tick_at(t, timeline.TickKind.WEEKLY)


def is_weekly_tick(t: int) -> bool:
    return timeline.next_tick_at(t - 1, timeline.TickKind.WEEKLY) == t
