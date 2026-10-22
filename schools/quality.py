"""
Qualidade da escola (design/03 §7-§13): Qualidade Base (materiais) + bônus dos professores, atualizada diariamente.

CICLO (tick diário do mundo, na virada do dia D):
  1. retrato = materiais da escola ao fim do dia D−1 (movimentos com `at` < início de D): "o estoque registrado no ciclo anterior" (03 §9);
  2. qualidade de D = base (retrato × qualidade por material) limitada pela estrela + bônus dos professores gerado em D−1 (0 enquanto não
     há professores: P1.06b);
  3. decaimento do dia: tira `decay_of(retrato)` dos materiais (movimento `decay` em `at` = início de D).
O retrato lê a TRILHA (não o cache) e exclui o decaimento do próprio dia, então o resultado não depende da ordem entre uma compra feita
no instante exato da virada e o tick. Idempotente: uma linha `QualityDay` por escola e dia; o tick refeito não repete decaimento.
Escola criada no meio do dia ganha a linha do dia com retrato 0 (estoque real zero: nenhum ciclo anterior com materiais).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from django.db import IntegrityError, transaction

from core import clock as game_clock
from core import ticks
from core.breakdown import Calc, Explained
from core.timeline import TickKind
from ledger.money import competence_day_of

from . import materials, params
from .constants import MaterialOperation
from .models import MaterialMovement, QualityDay, School

TICK_NAME = "schools_daily_cycle"


def explain_quality(snapshot: int, stars: int, teacher_bonus: Decimal, computed_at: int):
    """(Explained da qualidade do dia, base) — retrato × qualidade por material, limite da estrela e bônus dos professores (20)."""
    calc = (Calc("materials_snapshot", snapshot)
            .mul("quality_per_material", params.QUALITY_PER_MATERIAL)
            .cap("stars_materials_limit", materials.max_materials(stars) * params.QUALITY_PER_MATERIAL))
    base = calc.value
    calc.add("teacher_bonus", teacher_bonus)
    return calc.result(computed_at), base


def _write_day(school: School, day: int, snapshot: int, teacher_bonus: Decimal, at: int) -> bool:
    explained, base = explain_quality(snapshot, school.stars, teacher_bonus, at)
    try:
        with transaction.atomic():
            QualityDay.objects.create(school=school, day=day, materials_snapshot=snapshot, base_quality=base, teacher_bonus=teacher_bonus,
                                      quality=explained.value, explained=explained.to_dict(), computed_at=at)
    except IntegrityError:
        return False
    return True


def open_first_day(school: School, now: int) -> None:
    """Escola recém-criada: a linha do dia de criação (retrato 0, sem bônus)."""
    _write_day(school, competence_day_of(now), 0, Decimal(0), now)


def run_cycle(day_start: int) -> Dict[str, int]:
    """Ciclo da virada do dia que começa em `day_start`, para todas as escolas. Devolve contagens."""
    day = competence_day_of(day_start)
    done = decayed = 0
    for school_id in list(School.objects.order_by("id").values_list("id", flat=True)):
        with transaction.atomic():
            school = School.objects.select_for_update().get(pk=school_id)
            if QualityDay.objects.filter(school=school, day=day).exists():
                continue                                                         # dia já processado (tick refeito)
            snapshot = materials.materials_at(school.pk, day_start)
            _write_day(school, day, snapshot, Decimal(0), day_start)
            done += 1
            loss = materials.decay_of(snapshot)
            if loss > 0:
                loss = min(loss, school.materials)                              # nunca abaixo de zero
                if loss > 0:
                    materials._apply(school, -loss, MaterialOperation.DECAY, key=f"decay:{school.pk}:{day}", reference_kind="daily_cycle",
                                     reference_id=day, origin=f"school:{school.pk}", at=day_start)
                    decayed += 1
    return {"day": day, "schools": done, "decayed": decayed}


def quality_of(school_id: int, now: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Qualidade do dia corrente com o detalhamento, ou None se a escola não existe."""
    now = game_clock.now() if now is None else now
    row = QualityDay.objects.filter(school_id=school_id, day=competence_day_of(now)).first()
    if row is None:
        return None
    return {"school": school_id, "day": row.day, "quality": row.quality, "base_quality": row.base_quality, "teacher_bonus": row.teacher_bonus,
            "materials_snapshot": row.materials_snapshot, "explained": row.explained}


def _daily_tick(tick, ctx) -> None:
    run_cycle(tick.at)


def register() -> None:
    ticks.register(ticks.WORLD, TickKind.DAILY, TICK_NAME, priority=60)(_daily_tick)
