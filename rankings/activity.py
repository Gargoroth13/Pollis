"""
Maior tempo ativo (design/14 §14.3.11): sequência de atividade por conta.

Ação válida = execução BEM-SUCEDIDA pelo Action Registry (o mesmo para jogadores e bots). Login, chat e navegação não contam.
Continuação: o intervalo entre duas ações consecutivas é INFERIOR a 72 h (exatamente 72 h encerra a sequência: "3 dias ou mais").
O período de uma sequência vai da primeira à última ação dela. Uma ação não posterior à última já contada (mesmo instante ou
instante anterior) não altera nada: repetir o registro é inofensivo.
"""
from __future__ import annotations

from typing import Optional

from django.db import IntegrityError, transaction

from core import clock as game_clock

from . import params, records
from .models import ActivityStreak


def record_action(player_id: int, at: Optional[int] = None) -> ActivityStreak:
    """Registra uma ação válida do jogador no instante `at` (padrão: agora). Devolve a linha atualizada."""
    at = game_clock.now() if at is None else at
    with transaction.atomic():
        streak = ActivityStreak.objects.select_for_update().filter(player_id=player_id).first()
        if streak is None:
            try:
                with transaction.atomic():
                    streak = ActivityStreak.objects.create(player_id=player_id, current_start=at, last_action_at=at,
                                                           best_start=at, best_end=at, best_length=0)
            except IntegrityError:          # criação concorrente: segue sob trava
                streak = ActivityStreak.objects.select_for_update().get(player_id=player_id)
            else:
                records.check_active_time_record(streak)
                return streak
        if at <= streak.last_action_at:
            return streak
        if at - streak.last_action_at >= params.STREAK_MAX_GAP_SECONDS:
            streak.current_start = at           # sequência anterior encerrada; esta ação inicia outra
        streak.last_action_at = at
        length = at - streak.current_start
        if streak.current_start == streak.best_start or length > streak.best_length:
            streak.best_start, streak.best_end, streak.best_length = streak.current_start, at, length
        streak.save()
        records.check_active_time_record(streak)
        return streak
