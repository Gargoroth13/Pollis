"""Dono atual de um lote (10 §2-3): sem título = governo."""
from __future__ import annotations

from typing import Optional, Tuple

from .constants import OwnerKind
from .models import LotTitle


def owner_of_lot(lot_id: int) -> Tuple[OwnerKind, Optional[int]]:
    row = LotTitle.objects.filter(lot_id=lot_id).values_list("owner_kind", "owner_id").first()
    return (OwnerKind.GOVERNMENT, None) if row is None else (OwnerKind(row[0]), row[1])
