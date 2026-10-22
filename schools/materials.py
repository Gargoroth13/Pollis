"""
Materiais da escola (design/03 §8-§9): estoque de Materiais escolares com limite pela estrela, trilha imutável e decaimento diário.

PROTOCOLO: quem altera o estoque trava ANTES a linha da escola. Esta camada NÃO move dinheiro: quem compra liga o pagamento à entrada
na MESMA transação (P1.05b). Entrada externa só `PURCHASE`; o decaimento só nasce do ciclo diário (`quality`). Nada nasce sem origem.
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Dict, Optional

from django.db import IntegrityError, transaction

from core import clock as game_clock
from players.services import ActionResult

from . import params
from .constants import MAX_MATERIALS_PER_MOVEMENT, MaterialOperation
from .models import MaterialMovement, School


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def max_materials(stars: int) -> int:
    """Limite de armazenamento da estrela (03 §8; `[PROV]` em `params`)."""
    return params.MATERIALS_MAX_PER_STAR[stars]


def decay_of(stock: int) -> int:
    """Decaimento de um ciclo sobre `stock` unidades (03 §9; taxa `[PROV]`), arredondado uma vez (HALF_EVEN)."""
    return int((Decimal(stock) * params.MATERIAL_DECAY_RATE).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _same(existing: MaterialMovement, school_id: int, delta: int, operation: MaterialOperation) -> bool:
    return (existing.school_id, existing.delta, existing.operation) == (school_id, delta, operation.value)


def _apply(school: School, delta: int, operation: MaterialOperation, *, key: str, reference_kind: str, reference_id, origin: str,
           at: int) -> MaterialMovement:
    """Aplica sob a trava da escola já tomada pelo chamador."""
    after = school.materials + delta
    movement = MaterialMovement.objects.create(school=school, delta=delta, quantity_after=after, operation=operation.value, key=key,
                                               reference_kind=reference_kind, reference_id=str(reference_id), origin=origin, at=at)
    School.objects.filter(pk=school.pk).update(materials=after)
    school.materials = after
    return movement


def credit_materials(school_id: Any, quantity: Any, *, key: Any, reference_kind: str, reference_id, origin: str,
                     at: Optional[int] = None) -> ActionResult:
    """
    Entrada de materiais por compra. Idempotente por `key`. Recusas: INVALID_PARAMS, INVALID_QUANTITY, SCHOOL_NOT_FOUND,
    MATERIALS_FULL (acima do limite da estrela nada é armazenado: 03 §8, a entrada inteira é recusada), IDEMPOTENCY_CONFLICT.
    """
    if not isinstance(school_id, int) or isinstance(school_id, bool) or school_id <= 0 or not isinstance(key, str) or not key \
            or not reference_kind or not origin:
        return _refuse("INVALID_PARAMS")
    if not isinstance(quantity, int) or isinstance(quantity, bool) or not 0 < quantity <= MAX_MATERIALS_PER_MOVEMENT:
        return _refuse("INVALID_QUANTITY", quantity=repr(quantity)[:40], max=MAX_MATERIALS_PER_MOVEMENT)
    at = game_clock.now() if at is None else at
    with transaction.atomic():
        school = School.objects.select_for_update().filter(pk=school_id).first()
        if school is None:
            return _refuse("SCHOOL_NOT_FOUND", school=school_id)
        existing = MaterialMovement.objects.filter(key=key).first()
        if existing is not None:
            return (ActionResult(True, "OK", {"already_applied": True, "school": school_id, "quantity": existing.delta})
                    if _same(existing, school_id, quantity, MaterialOperation.PURCHASE) else _refuse("IDEMPOTENCY_CONFLICT", key=key))
        limit = max_materials(school.stars)
        if school.materials + quantity > limit:
            return _refuse("MATERIALS_FULL", school=school_id, stored=school.materials, limit=limit, free=limit - school.materials)
        try:
            with transaction.atomic():
                movement = _apply(school, quantity, MaterialOperation.PURCHASE, key=key, reference_kind=reference_kind,
                                  reference_id=reference_id, origin=origin, at=at)
        except IntegrityError:
            return _refuse("IDEMPOTENCY_CONFLICT", key=key)
    return ActionResult(True, "OK", {"school": school_id, "quantity": quantity, "materials": movement.quantity_after, "limit": limit})


def materials_at(school_id: int, before: int) -> int:
    """Estoque da escola considerando só os movimentos com `at` ESTRITAMENTE antes de `before` (retrato do ciclo anterior)."""
    from django.db.models import Sum
    return MaterialMovement.objects.filter(school_id=school_id, at__lt=before).aggregate(s=Sum("delta"))["s"] or 0
