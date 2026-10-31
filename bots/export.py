"""
Exportação de uma execução para análise externa (21 §21.53, §21.57): `bot_test_<data>.zip` com CSV (tabelas), JSON (configuração) e JSONL (eventos).
Os arquivos de 21 §21.53 que dependem de sistemas ainda não construídos (`training_metrics`: P1.19; `economy_daily`: dashboards econômicos, P1.21; detecção
de anomalias: P1.22) NÃO são inventados: o `manifest` do `run.json` os lista como pendentes, e `anomalies.csv` traz só as falhas técnicas já registradas.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from typing import Any, Dict, Iterable, List

from . import dashboard
from .models import Bot, BotActionLog, BotDecisionLog, BotRun, BotTickMetric, PopulationSnapshot

PENDING = {"training_metrics.csv": "P1.19 (treinamento RL)", "economy_daily.csv": "P1.21 (dashboards econômicos)",
           "anomalies.csv (detecção)": "P1.22 (detecção de anomalias); o arquivo traz apenas falhas técnicas registradas"}
TECHNICAL_FAILURES = frozenset({"EXCEPTION", "POLICY_EXCEPTION", "POLICY_ILLEGAL_ACTION"})


def _csv(rows: Iterable[Dict[str, Any]], columns: List[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})
    return buf.getvalue()


def _jsonl(rows: Iterable[Dict[str, Any]]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n" for r in rows)


def build_files(run: BotRun) -> Dict[str, str]:
    run.refresh_from_db()
    bots = list(Bot.objects.filter(run=run).order_by("index"))
    files: Dict[str, str] = {}
    files["run.json"] = json.dumps({
        "run_id": run.pk, "name": run.name, "status": run.status, "started_game_at": run.started_game_at, "started_real_at": run.started_real_at.isoformat(),
        "ended_game_at": run.ended_game_at, "ended_real_at": run.ended_real_at.isoformat() if run.ended_real_at else None, "game_version": run.game_version,
        "model_version": run.model_version, "config": run.config, "target_population": run.target_population,
        "creation_interval_real_seconds": run.creation_interval_real_seconds, "clock_real_seconds_per_game_day": run.clock_real_seconds_per_game_day,
        "global_seed": run.global_seed, "bots_created": run.bots_created, "bots_removed": run.bots_removed, "pending_files": PENDING},
        ensure_ascii=False, indent=2, sort_keys=True)
    cols = ["bot_id", "player_id", "index", "seed", "archetype", "personality", "goal", "specialization", "status", "created_game_at", "retired_game_at",
            "evaluations", "next_eval_at"]
    files["bots.csv"] = _csv(({"bot_id": b.pk, "player_id": b.player_id, "index": b.index, "seed": b.seed, "archetype": b.archetype, "personality": b.personality,
                               "goal": b.goal, "specialization": b.specialization, "status": b.status, "created_game_at": b.created_game_at,
                               "retired_game_at": b.retired_game_at, "evaluations": b.eval_count, "next_eval_at": b.next_eval_at} for b in bots), cols)
    state_cols = ["bot_id", "evaluated_at", "energy", "health", "nutrition", "burnout", "burnout_active", "health_critical", "hospitalized", "qol_current", "money_cents"]
    files["bot_states.csv"] = _csv(({"bot_id": b.pk, "evaluated_at": b.last_eval_at, **{k: (b.last_observation or {}).get(k) for k in state_cols[2:]}}
                                    for b in bots if b.last_observation), state_cols)
    actions = BotActionLog.objects.filter(bot__run=run).order_by("id")
    files["actions.jsonl"] = _jsonl({"timestamp": a.at, "bot_id": a.bot_id, "action": a.action, "target": a.target, "success": a.success, "code": a.code,
                                     "detail": a.detail, "energy_before": a.energy_before, "energy_after": a.energy_after, "money_before": a.money_before,
                                     "money_after": a.money_after, "decision": a.decision_id} for a in actions.iterator())
    decisions = BotDecisionLog.objects.filter(bot__run=run).order_by("id")
    files["decisions.jsonl"] = _jsonl({"decision": d.pk, "timestamp": d.at, "bot_id": d.bot_id, "eval": d.eval_no, "seed": d.decision_seed,
                                       "game_version": d.game_version, "model_version": d.model_version, "goal": d.goal, "observation": d.observation,
                                       "available_actions": d.available_actions, "chosen_action": d.chosen_action, "chosen_target": d.chosen_target,
                                       "score": d.score, "exploration": d.exploration, "result_code": d.result_code, "reward": d.reward,
                                       "next_observation": d.next_observation} for d in decisions.iterator())
    files["anomalies.csv"] = _csv(({"at": a.at, "bot_id": a.bot_id, "action": a.action, "code": a.code, "detail": json.dumps(a.detail, ensure_ascii=False, default=str)}
                                   for a in actions.filter(code__in=TECHNICAL_FAILURES)), ["at", "bot_id", "action", "code", "detail"])
    snaps = PopulationSnapshot.objects.filter(run=run).order_by("game_day")
    files["population_daily.csv"] = _csv(({"game_day": s.game_day, "taken_at": s.taken_at, "total_active": s.total_active,
                                           "data": json.dumps(s.data, ensure_ascii=False, sort_keys=True)} for s in snaps), ["game_day", "taken_at", "total_active", "data"])
    perf_cols = ["game_at", "real_seconds", "created", "evaluated", "acted", "errors", "backlog_after", "db_queries", "db_seconds", "cpu_seconds", "rss_mb"]
    files["system_performance.csv"] = _csv(({c: getattr(m, c) for c in perf_cols} for m in BotTickMetric.objects.filter(run=run).order_by("id")), perf_cols)
    files["summary.json"] = json.dumps(dashboard.overview(run), ensure_ascii=False, indent=2, sort_keys=True, default=str)
    return files


def export_run(run: BotRun, path: str) -> Dict[str, int]:
    """Grava o zip em `path` e devolve {arquivo: bytes}. Só LÊ o banco."""
    files = build_files(run)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return {n: len(c.encode("utf-8")) for n, c in files.items()}
