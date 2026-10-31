"""Dashboard técnico básico (21 §21.43-§21.45, §21.52): visão geral da execução, cobertura, ações e desempenho. Só LÊ; é ferramenta de Admin/Dev."""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict

from core import clock as game_clock

from . import population, scheduler
from .constants import BotStatus
from .models import Bot, BotActionLog, BotDecisionLog, BotRun, BotTickMetric


def overview(run: BotRun) -> Dict[str, Any]:
    run.refresh_from_db()           # contadores mudam por fora (criação/remoção); nunca mostrar um objeto velho
    now = game_clock.now()
    by_status = dict(Counter(Bot.objects.filter(run=run).values_list("status", flat=True)))
    actions = Counter()
    failures = Counter()
    for action, success in BotActionLog.objects.filter(bot__run=run).values_list("action", "success"):
        actions[action] += 1
        if not success:
            failures[action] += 1
    codes = Counter(BotDecisionLog.objects.filter(bot__run=run).exclude(result_code="").values_list("result_code", flat=True))
    metrics = list(BotTickMetric.objects.filter(run=run).order_by("-id")[:20])
    decisions = BotDecisionLog.objects.filter(bot__run=run).count()
    return {
        "run": {"id": run.pk, "name": run.name, "status": run.status, "target_population": run.target_population, "created": run.bots_created,
                "removed": run.bots_removed, "game_version": run.game_version, "model_version": run.model_version, "global_seed": run.global_seed},
        "population": {"by_status": by_status, "active": by_status.get(BotStatus.ACTIVE.value, 0), "coverage": population.coverage(run),
                       "gaps": population.gaps(run)[:10]},
        "scheduler": {"now": now, "due_now": scheduler.backlog(now, run.pk)},
        "decisions": {"total": decisions, "by_result_code": dict(codes)},
        "actions": {"total": sum(actions.values()), "by_action": dict(actions), "failures_by_action": dict(failures),
                    "success_rate": None if not actions else round(1 - sum(failures.values()) / sum(actions.values()), 4)},
        "performance": {"recent_ticks": [{"game_at": m.game_at, "real_seconds": round(m.real_seconds, 4), "evaluated": m.evaluated, "acted": m.acted,
                                          "errors": m.errors, "backlog_after": m.backlog_after, "db_queries": m.db_queries,
                                          "db_seconds": round(m.db_seconds, 4), "cpu_seconds": round(m.cpu_seconds, 4), "rss_mb": round(m.rss_mb, 1),
                                          "decisions_per_second": None if m.real_seconds == 0 else round(m.evaluated / m.real_seconds, 2)} for m in metrics]},
    }


def bot_view(bot_id: int, decisions: int = 10) -> Dict[str, Any]:
    """Painel individual (21 §21.45): perfil, seed, agendamento, última observação e as últimas decisões com o resultado."""
    bot = Bot.objects.select_related("player").get(pk=bot_id)
    last = BotDecisionLog.objects.filter(bot=bot).order_by("-eval_no")[:decisions]
    return {"bot": bot.pk, "player": bot.player_id, "run": bot.run_id, "profile": {"archetype": bot.archetype, "personality": bot.personality, "goal": bot.goal,
                                                                                     "specialization": bot.specialization}, "status": bot.status,
            "seed": bot.seed, "next_eval_at": bot.next_eval_at, "wake_reason": bot.wake_reason, "evaluations": bot.eval_count,
            "last_observation": bot.last_observation,
            "decisions": [{"eval": d.eval_no, "at": d.at, "action": d.chosen_action, "result": d.result_code, "score": d.score, "exploration": d.exploration,
                           "model": d.model_version, "seed": d.decision_seed} for d in last]}
