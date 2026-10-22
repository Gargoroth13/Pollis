"""
Auditoria das Escolas (design/03). Só LÊ. Invariantes (numeração própria deste app):
  1  escola: pública sem dono e particular com dono; estrela válida; no máximo uma escola de origem por bairro (só pública)
  2  materiais: estoque em cache = soma dos movimentos; cada `quantity_after` é a soma acumulada; nunca negativo; dentro do limite da
     estrela; decaimento só do ciclo diário (um por escola e dia, com a chave e o valor que a regra produz)
  3  matrícula: no máximo uma ativa por jogador; todo jogador tem escola; histórico contínuo (sem buraco nem sobreposição); só troca para
     escola do MESMO bairro; a primeira matrícula está no bairro de origem do jogador
  4  qualidade: uma linha por escola e dia; retrato = materiais da trilha antes do dia; base = retrato × qualidade por material limitado
     pela estrela; qualidade = base + bônus; cada dia de ciclo tem o decaimento da regra
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Dict, List

from django.db.models import Sum

from ledger.audit import AuditReport
from ledger.money import competence_day_of
from players.models import Player

from . import materials, params, quality
from .constants import EnrollmentEnd, MaterialOperation, SchoolKind
from .models import Enrollment, MaterialMovement, QualityDay, School


def audit_schools() -> AuditReport:
    report = AuditReport()
    schools = list(School.objects.order_by("id"))
    report.stats["schools"] = len(schools)
    neighborhoods: Dict[int, int] = {}
    for s in schools:
        kind = report.enum(SchoolKind, s.kind, "School", "kind", s.pk)
        if kind is None:
            continue
        if (kind is SchoolKind.PUBLIC) != (s.owner_id is None):
            report.add(1, "OWNER_KIND_MISMATCH", school=s.pk)
        if s.stars not in params.MATERIALS_MAX_PER_STAR:
            report.add(1, "INVALID_STARS", school=s.pk, stars=s.stars)
            continue
        if s.initial:
            neighborhoods[s.neighborhood_id] = neighborhoods.get(s.neighborhood_id, 0) + 1
            if kind is not SchoolKind.PUBLIC:
                report.add(1, "INITIAL_NOT_PUBLIC", school=s.pk)
        _audit_materials(report, s)
        _audit_quality(report, s)
    for neighborhood, count in neighborhoods.items():
        if count > 1:
            report.add(1, "MANY_INITIAL_SCHOOLS", neighborhood=neighborhood, count=count)
    _audit_enrollments(report, {s.pk: s for s in schools})
    return report


def _audit_materials(report: AuditReport, s: School) -> None:
    running = 0
    decay_days = defaultdict(int)
    for m in MaterialMovement.objects.filter(school=s).order_by("id"):
        op = report.enum(MaterialOperation, m.operation, "MaterialMovement", "operation", m.pk)
        running += m.delta
        if m.quantity_after != running:
            report.add(2, "MOVEMENT_CHAIN_BROKEN", movement=m.pk, school=s.pk, recorded=m.quantity_after, expected=running)
        if running < 0:
            report.add(2, "NEGATIVE_MATERIALS", school=s.pk, movement=m.pk)
        if op is MaterialOperation.DECAY:
            if m.delta >= 0:
                report.add(2, "DECAY_NOT_NEGATIVE", movement=m.pk)
            decay_days[competence_day_of(m.at)] += 1
            if m.key != f"decay:{s.pk}:{competence_day_of(m.at)}":
                report.add(2, "DECAY_KEY_UNEXPECTED", movement=m.pk)
        elif op is MaterialOperation.PURCHASE and m.delta <= 0:
            report.add(2, "PURCHASE_NOT_POSITIVE", movement=m.pk)
    if s.materials != running:
        report.add(2, "MATERIALS_CACHE_MISMATCH", school=s.pk, cached=s.materials, trail=running)
    if s.materials > materials.max_materials(s.stars):
        report.add(2, "MATERIALS_OVER_LIMIT", school=s.pk, stored=s.materials, limit=materials.max_materials(s.stars))
    for day, n in decay_days.items():
        if n > 1:
            report.add(2, "DECAY_REPEATED", school=s.pk, day=day)


def _audit_quality(report: AuditReport, s: School) -> None:
    for row in QualityDay.objects.filter(school=s).order_by("day"):
        start, _ = _day_start(row.day)
        want_snapshot = 0 if row.day == competence_day_of(s.created_at) else materials.materials_at(s.pk, start)
        if row.materials_snapshot != want_snapshot:
            report.add(4, "SNAPSHOT_MISMATCH", school=s.pk, day=row.day, recorded=row.materials_snapshot, expected=want_snapshot)
        explained, base = quality.explain_quality(row.materials_snapshot, s.stars, row.teacher_bonus, row.computed_at)
        if row.base_quality != base.quantize(Decimal("0.000001")) or row.quality != explained.value.quantize(Decimal("0.000001")):
            report.add(4, "QUALITY_MISMATCH", school=s.pk, day=row.day, recorded=str(row.quality), expected=str(explained.value))
        if row.teacher_bonus < 0:
            report.add(4, "NEGATIVE_BONUS", school=s.pk, day=row.day)
        if row.day != competence_day_of(s.created_at):
            loss = materials.decay_of(row.materials_snapshot)
            got = -(MaterialMovement.objects.filter(school=s, key=f"decay:{s.pk}:{row.day}").aggregate(t=Sum("delta"))["t"] or 0)
            want = min(loss, _stock_before_decay(s, row.day, start))
            if got != want:
                report.add(4, "DECAY_MISMATCH", school=s.pk, day=row.day, recorded=got, expected=want)


def _day_start(day: int):
    from market.rollup import day_bounds
    return day_bounds(day)


def _stock_before_decay(s: School, day: int, start: int) -> int:
    """Materiais da escola no instante do ciclo, antes do decaimento do dia (compras no instante exato da virada contam)."""
    return (MaterialMovement.objects.filter(school=s, at__lte=start).exclude(key=f"decay:{s.pk}:{day}").aggregate(t=Sum("delta"))["t"] or 0)


def _audit_enrollments(report: AuditReport, schools: Dict[int, School]) -> None:
    by_player: Dict[int, List[Enrollment]] = defaultdict(list)
    for e in Enrollment.objects.order_by("player_id", "started_at", "id"):
        by_player[e.player_id].append(e)
    report.stats["enrollments"] = sum(len(v) for v in by_player.values())
    for player_id in Player.objects.order_by("id").values_list("id", flat=True):
        rows = by_player.get(player_id)
        if not rows:
            report.add(3, "PLAYER_WITHOUT_SCHOOL", player=player_id)
            continue
        active = [r for r in rows if r.ended_at is None]
        if len(active) != 1:
            report.add(3, "ACTIVE_ENROLLMENTS_NOT_ONE", player=player_id, active=len(active))
        for prev, nxt in zip(rows, rows[1:]):
            if prev.ended_at is None or prev.ended_at != nxt.started_at:
                report.add(3, "ENROLLMENT_HISTORY_NOT_CONTINUOUS", player=player_id, enrollment=nxt.pk)
            elif schools[prev.school_id].neighborhood_id != schools[nxt.school_id].neighborhood_id:
                report.add(3, "TRANSFER_ACROSS_NEIGHBORHOODS", player=player_id, enrollment=nxt.pk)
            if prev.end_reason != EnrollmentEnd.TRANSFER.value:
                report.add(3, "ENROLLMENT_END_REASON_UNEXPECTED", player=player_id, enrollment=prev.pk, reason=prev.end_reason)
    for rows in by_player.values():
        for r in rows:
            if r.school_id not in schools:
                report.add(3, "SCHOOL_MISSING", enrollment=r.pk)
