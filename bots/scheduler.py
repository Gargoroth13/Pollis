"""
Scheduler individual (21 §21.4): cada Bot tem o seu próximo instante de avaliação, variável e reproduzível (seed do Bot); não há blocos artificiais.
O scheduler só diz QUANDO avaliar. Não concede ações extras: cada avaliação faz no máximo UMA ação, pelo Action Registry, que aplica Energia,
cooldowns e requisitos normais.
"""
from __future__ import annotations

import random
from typing import List, Optional

from django.db import transaction

from . import params
from .constants import BotStatus, WakeReason
from .models import Bot


def interval(rng: random.Random, bounds) -> int:
    lo, hi = bounds
    return rng.randint(lo, hi)


def first_eval_at(rng: random.Random, created_at: int) -> int:
    return created_at + interval(rng, params.EVAL_FIRST_SECONDS)


def next_eval_at(rng: random.Random, now: int, acted: bool) -> int:
    return now + interval(rng, params.EVAL_AFTER_ACTION_SECONDS if acted else params.EVAL_IDLE_SECONDS)


def due(now: int, limit: Optional[int] = None, run_id: Optional[int] = None) -> List[int]:
    """Ids dos Bots ativos cuja avaliação venceu, do mais atrasado ao mais recente (desempate por id: determinístico)."""
    qs = Bot.objects.filter(status=BotStatus.ACTIVE.value, next_eval_at__lte=now)
    if run_id is not None:
        qs = qs.filter(run_id=run_id)
    qs = qs.order_by("next_eval_at", "id").values_list("pk", flat=True)
    return list(qs[:limit] if limit else qs)


def backlog(now: int, run_id: Optional[int] = None) -> int:
    qs = Bot.objects.filter(status=BotStatus.ACTIVE.value, next_eval_at__lte=now)
    return (qs.filter(run_id=run_id) if run_id is not None else qs).count()


def wake(bot_id: int, reason: WakeReason, at: int) -> bool:
    """Antecipa a próxima avaliação (21 §21.4: ação concluída, mudança de situação, oportunidade, janela política, emprego...). Nunca a adia."""
    with transaction.atomic():
        bot = Bot.objects.select_for_update().filter(pk=bot_id, status=BotStatus.ACTIVE.value).first()
        if bot is None or bot.next_eval_at <= at:
            return False
        bot.next_eval_at, bot.wake_reason = at, reason.value
        bot.save(update_fields=["next_eval_at", "wake_reason"])
        return True
