"""
Auditoria dos Rankings (design/14 §14.9): confere que os dados guardados são íntegros e que os recordes não ficaram ATRÁS
da fonte (o que indicaria uma atualização perdida). Só lê. Achados: {code, ...detalhe}.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any, Dict, List

from django.db.models import Max

from core import clock as game_clock

from . import live, params
from .constants import ENTITY_TYPES, Cat, Group, spec as category_spec
from .models import ActivityEvent, ActivityStreak, NetWorthCandidate, QolSnapshot, QolSnapshotEntry, RankingHistorico


def audit_rankings(at: int = None) -> Dict[str, Any]:
    at = game_clock.now() if at is None else at
    findings: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {"at": at}

    streaks = list(ActivityStreak.objects.all())
    stats["streaks"] = len(streaks)
    for s in streaks:
        if s.best_length != s.best_end - s.best_start or s.best_length < s.last_action_at - s.current_start:
            findings.append({"code": "STREAK_INCONSISTENT", "player_id": s.player_id})

    streak_last = {x.player_id: x.last_action_at for x in streaks}
    # outbox de atividade: pendentes, erros e o evento pendente mais antigo
    pending_qs = ActivityEvent.objects.filter(processed_at__isnull=True)
    oldest = pending_qs.order_by("at", "id").first()
    errors = pending_qs.filter(attempts__gt=0)
    stats["activity_outbox"] = {"pending": pending_qs.count(), "with_errors": errors.count(),
                                "oldest_pending_id": None if oldest is None else oldest.pk,
                                "oldest_pending_at": None if oldest is None else oldest.at,
                                "oldest_pending_age_seconds": None if oldest is None else max(0, at - oldest.at)}
    if oldest is not None and at - oldest.at > params.ACTIVITY_OUTBOX_OVERDUE_SECONDS:
        findings.append({"code": "ACTIVITY_OUTBOX_OVERDUE", "oldest_event_id": oldest.pk, "oldest_at": oldest.at,
                         "age_seconds": at - oldest.at, "pending": stats["activity_outbox"]["pending"]})
    for ev in errors.order_by("at", "id")[:20]:
        findings.append({"code": "ACTIVITY_EVENT_ERROR", "event_id": ev.pk, "player_id": ev.player_id, "action_id": ev.action_id,
                         "at": ev.at, "attempts": ev.attempts, "last_error": ev.last_error})
    # processado mas a sequência não reflete (a atualização e a marcação são atômicas: isto indicaria corrupção)
    for pid, last_at in (ActivityEvent.objects.filter(processed_at__isnull=False).values("player_id")
                         .annotate(m=Max("at")).values_list("player_id", "m")):
        s = streak_last.get(pid)
        if s is None or s < last_at:
            findings.append({"code": "ACTIVITY_PROCESSED_NOT_REFLECTED", "player_id": pid, "event_at": last_at,
                             "streak_last_action_at": s})

    records = {r.category: r for r in RankingHistorico.objects.all()}
    stats["records"] = len(records)
    for key, r in records.items():
        try:
            spec = category_spec(key)
        except ValueError:
            spec = None
        if spec is None or spec.group != Group.HISTORICAL:
            findings.append({"code": "RECORD_UNKNOWN_CATEGORY", "category": key})
            continue
        if r.entity_type not in ENTITY_TYPES:
            findings.append({"code": "RECORD_BAD_ENTITY_TYPE", "category": key, "entity_type": r.entity_type})
        if r.recorded_at > at:
            findings.append({"code": "RECORD_IN_THE_FUTURE", "category": key, "recorded_at": r.recorded_at})

    ar = records.get(Cat.ACTIVE_TIME_RECORD.value)
    best = max(streaks, key=lambda s: (s.best_length, -s.player_id), default=None)
    if best is not None and best.best_length > 0 and (ar is None or best.best_length > ar.value):         # 0 s não é recorde
        findings.append({"code": "RECORD_BEHIND_SOURCE", "category": Cat.ACTIVE_TIME_RECORD.value,
                         "record": None if ar is None else ar.value, "source": best.best_length, "player_id": best.player_id})
    if ar is not None:
        m = ar.metadata
        if (m.get("length_seconds") != ar.value or m.get("end", 0) - m.get("start", 0) != ar.value
                or not ar.entity_type == "player"):
            findings.append({"code": "RECORD_METADATA_MISMATCH", "category": ar.category})

    nr = records.get(Cat.NET_WORTH_RECORD.value)
    top = live.net_worth_rows(limit=1, at=at)
    if top and top[0]["value"] > 0 and (nr is None or top[0]["value"] > nr.value):
        findings.append({"code": "RECORD_BEHIND_SOURCE", "category": Cat.NET_WORTH_RECORD.value,
                         "record": None if nr is None else nr.value, "source": top[0]["value"],
                         "player_id": top[0]["entity_id"]})

    pending = NetWorthCandidate.objects.count()
    stats["net_worth_candidates_pending"] = pending
    if pending:
        findings.append({"code": "NET_WORTH_CANDIDATES_PENDING", "count": pending,
                         "oldest_at": NetWorthCandidate.objects.order_by("at").values_list("at", flat=True).first()})

    # snapshots de QoL: COMPLETE precisa ter exatamente os elegíveis representados; OPEN vencida há muito indica job parado
    for sn in QolSnapshot.objects.filter(status=QolSnapshot.COMPLETE):
        n = QolSnapshotEntry.objects.filter(snapshot=sn).count()
        if n != sn.eligible or n != sn.represented or sn.missing != 0:
            findings.append({"code": "QOL_SNAPSHOT_INCONSISTENT", "reference_at": sn.reference_at, "entries": n,
                             "eligible": sn.eligible})
    overdue = QolSnapshot.objects.filter(status=QolSnapshot.OPEN, reference_at__lt=at - 2 * params.QOL_SNAPSHOT_INTERVAL_SECONDS)
    for sn in overdue:
        findings.append({"code": "QOL_SNAPSHOT_OVERDUE", "reference_at": sn.reference_at})
    latest = QolSnapshot.objects.filter(status=QolSnapshot.COMPLETE).order_by("-reference_at").first()
    stats["qol_latest_complete"] = None if latest is None else latest.reference_at
    stats["qol_incomplete"] = QolSnapshot.objects.filter(status=QolSnapshot.INCOMPLETE).count()

    pr = records.get(Cat.PRESIDENT_VOTE_RECORD.value)
    if pr is not None:
        m = pr.metadata
        ok = all(isinstance(m.get(k), int) for k in ("votes", "total_votes", "election_date")) and m.get("election")
        if not ok or not 0 <= m["votes"] <= m["total_votes"] or m["total_votes"] <= 0 \
                or pr.value != m["votes"] * 1_000_000 // m["total_votes"]:
            findings.append({"code": "RECORD_METADATA_MISMATCH", "category": pr.category})
    stats["parameters"] = {"production_window_days": params.PRODUCTION_WINDOW_DAYS,
                           "taxpayer_window_days": params.TAXPAYER_WINDOW_DAYS,
                           "streak_max_gap_seconds": params.STREAK_MAX_GAP_SECONDS}
    return {"ok": not findings, "findings": findings, "stats": stats}
