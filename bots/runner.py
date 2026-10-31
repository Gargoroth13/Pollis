"""
Ciclo de decisão do Bot (21 §21.4): observa → máscara → política → ação pelo Action Registry normal → logs → próxima avaliação.
O Bot usa o MESMO caminho do jogador (`players.registry.execute_action`); não há caminho privilegiado (CLAUDE.md §5.4). No máximo UMA ação por avaliação.
Exceções da política ou da execução NUNCA são escondidas: viram registro de decisão/ação com o código `EXCEPTION`/`POLICY_*` e texto do erro (anomalia).
"""
from __future__ import annotations

import logging
import resource
import time
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import connection, transaction

from core import clock as game_clock
from players import registry

from . import masking, observation, scheduler
from .constants import BotStatus, WakeReason
from .models import Bot, BotActionLog, BotDecisionLog, BotRun, BotTickMetric
from .policy import Decision, Policy
from .seeds import derive_seed, rng_for

log = logging.getLogger(__name__)


def game_version() -> str:
    return str(getattr(settings, "POLIS_GAME_VERSION", "dev"))


def _result_dict(result) -> Dict[str, Any]:
    return {"ok": result.ok, "code": result.code, "detail": _jsonable(result.detail)}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)


def evaluate(bot_id: int, policy: Policy) -> Optional[Dict[str, Any]]:
    """Avalia UM Bot vencido. Devolve um resumo, ou None se o Bot não está ativo ou ainda não venceu."""
    with transaction.atomic():
        bot = Bot.objects.select_for_update().select_related("run").filter(pk=bot_id).first()
        now = game_clock.now()
        if bot is None or bot.status != BotStatus.ACTIVE.value or bot.next_eval_at > now:
            return None
        before = observation.observe(bot.player_id)
        _backfill_previous(bot, before)
        mask = masking.action_mask(bot.player_id)
        eval_no = bot.eval_count + 1
        seed = derive_seed(bot.seed, "decision", eval_no)
        rng = rng_for(seed)
        decision: Optional[Decision] = None
        code, error = "", ""
        try:
            decision = policy.decide(dict(before), {a: dict(m) for a, m in mask.items()}, rng)
        except Exception as exc:                                    # noqa: BLE001 - anomalia registrada, nunca escondida
            code, error = "POLICY_EXCEPTION", f"{type(exc).__name__}: {exc}"[:300]
            log.exception("política falhou no Bot %s", bot.pk)
        if decision is not None and not (decision.action_id in mask and mask[decision.action_id]["available"]):
            code, error = "POLICY_ILLEGAL_ACTION", f"ação fora da máscara: {decision.action_id!r}"[:300]       # a máscara é lei (21 §21.21)
            decision_illegal, decision = decision, None
        else:
            decision_illegal = None
        dlog = BotDecisionLog.objects.create(
            bot=bot, at=now, eval_no=eval_no, decision_seed=seed, game_version=game_version(), model_version=policy.model_version, goal=bot.goal,
            observation=before, available_actions={a: m["available"] for a, m in mask.items()},
            chosen_action=(decision.action_id if decision else (decision_illegal.action_id if decision_illegal else None)),
            chosen_target=_jsonable(decision.target) if decision else None, score=decision.score if decision else None,
            exploration=_jsonable(decision.exploration) if decision else {}, result_code=code or ("NO_ACTION" if decision is None else ""))
        acted = False
        if decision is not None:
            acted = _act(bot, dlog, decision, before, now)
        elif error:
            dlog.exploration = {"error": error}
            dlog.save(update_fields=["exploration"])
        nxt = scheduler.next_eval_at(rng_for(derive_seed(bot.seed, "schedule", eval_no)), now, acted)
        bot.eval_count, bot.last_eval_at, bot.last_observation = eval_no, now, before
        bot.next_eval_at, bot.wake_reason = nxt, WakeReason.PLANNED.value
        bot.save(update_fields=["eval_count", "last_eval_at", "last_observation", "next_eval_at", "wake_reason"])
        return {"bot": bot.pk, "eval": eval_no, "action": dlog.chosen_action, "result": dlog.result_code, "acted": acted, "next_eval_at": nxt}


def _act(bot: Bot, dlog: BotDecisionLog, decision: Decision, before: Dict[str, Any], now: int) -> bool:
    try:
        result = registry.execute_action(bot.player_id, decision.action_id, decision.target)
        res = _result_dict(result)
    except Exception as exc:                                        # noqa: BLE001
        log.exception("execução falhou no Bot %s", bot.pk)
        res = {"ok": False, "code": "EXCEPTION", "detail": {"error": f"{type(exc).__name__}: {exc}"[:300]}}
    after = observation.observe(bot.player_id)
    dlog.result_code = res["code"]
    dlog.save(update_fields=["result_code"])
    BotActionLog.objects.create(bot=bot, decision=dlog, at=now, action=decision.action_id, target=_jsonable(decision.target), success=res["ok"], code=res["code"],
                                detail=res["detail"], energy_before=before["energy"], energy_after=after["energy"],
                                money_before=before["money_cents"], money_after=after["money_cents"])
    return bool(res["ok"])


def _backfill_previous(bot: Bot, current: Dict[str, Any]) -> None:
    """Experiência (21 §21.26): a observação de agora é o `next_observation` da decisão anterior. O reward vem depois (P1.19)."""
    BotDecisionLog.objects.filter(bot=bot, eval_no=bot.eval_count, next_observation__isnull=True).update(next_observation=current)


def run_due(run: BotRun, policy: Policy, *, limit: Optional[int] = None, created: int = 0) -> BotTickMetric:
    """Uma passada do scheduler: avalia os Bots vencidos (do mais atrasado), mede o tempo e deixa a fila restante na métrica."""
    started, cpu_started = time.perf_counter(), time.process_time()
    now = game_clock.now()
    evaluated = acted = errors = 0
    db = {"n": 0, "seconds": 0.0}

    def timed(execute, sql, params, many, context):
        t0 = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            db["n"] += 1
            db["seconds"] += time.perf_counter() - t0

    with connection.execute_wrapper(timed):
        for bot_id in scheduler.due(now, limit=limit, run_id=run.pk):
            try:
                res = evaluate(bot_id, policy)
            except Exception:                                       # noqa: BLE001 - falha de infraestrutura: contada e registrada, a passada continua
                log.exception("avaliação falhou no Bot %s", bot_id)
                errors += 1
                continue
            if res is None:
                continue
            evaluated += 1
            acted += int(res["acted"])
            errors += int(res["result"] in ("EXCEPTION", "POLICY_EXCEPTION", "POLICY_ILLEGAL_ACTION"))
        backlog = scheduler.backlog(now, run.pk)
    return BotTickMetric.objects.create(run=run, game_at=now, real_seconds=time.perf_counter() - started, created=created, evaluated=evaluated, acted=acted,
                                        errors=errors, backlog_after=backlog, db_queries=db["n"], db_seconds=db["seconds"],
                                        cpu_seconds=time.process_time() - cpu_started,
                                        rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024)
