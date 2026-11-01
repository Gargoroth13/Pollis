"""
Ferramentas de Admin/Dev (21 §21.60): observar, congelar, reiniciar, remover, inspecionar, exportar. Ficam FORA do agente: nada daqui é visível à política.
Nenhuma cria recurso ou dinheiro.
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction

from core import clock as game_clock

from .constants import BotStatus, RunStatus, WakeReason
from .models import Bot, BotRun


def freeze(bot_id: int) -> bool:
    return _set_status(bot_id, BotStatus.ACTIVE, BotStatus.FROZEN)


def unfreeze(bot_id: int) -> bool:
    """Descongela e agenda a próxima avaliação para agora (sem salto: o Bot só fica elegível, a avaliação segue as regras normais)."""
    with transaction.atomic():
        bot = Bot.objects.select_for_update().filter(pk=bot_id, status=BotStatus.FROZEN.value).first()
        if bot is None:
            return False
        bot.status, bot.wake_reason, bot.next_eval_at = BotStatus.ACTIVE.value, WakeReason.ADMIN.value, game_clock.now()
        bot.save(update_fields=["status", "wake_reason", "next_eval_at"])
        return True


def retire(bot_id: int) -> bool:
    """Remove da população ativa. A conta e todo o histórico permanecem (auditoria, CLAUDE.md §12)."""
    with transaction.atomic():
        bot = Bot.objects.select_for_update().select_related("run").filter(pk=bot_id).exclude(status=BotStatus.RETIRED.value).first()
        if bot is None:
            return False
        run = BotRun.objects.select_for_update().get(pk=bot.run_id)
        bot.status, bot.retired_game_at = BotStatus.RETIRED.value, game_clock.now()
        bot.save(update_fields=["status", "retired_game_at"])
        run.bots_removed += 1
        run.save(update_fields=["bots_removed"])
        return True


def _set_status(bot_id: int, old: BotStatus, new: BotStatus) -> bool:
    with transaction.atomic():
        bot = Bot.objects.select_for_update().filter(pk=bot_id, status=old.value).first()
        if bot is None:
            return False
        bot.status = new.value
        bot.save(update_fields=["status"])
        return True


def stop_run(run_id: int) -> Optional[BotRun]:
    from django.utils import timezone
    with transaction.atomic():
        run = BotRun.objects.select_for_update().filter(pk=run_id).first()
        if run is None or run.status == RunStatus.STOPPED.value:
            return run
        run.status, run.ended_game_at, run.ended_real_at = RunStatus.STOPPED.value, game_clock.now(), timezone.now()
        run.save(update_fields=["status", "ended_game_at", "ended_real_at"])
        return run
