"""
O que o Bot PODE saber (21 §21.17): somente o que o jogador veria pela interface normal. A observação é construída aqui, a partir dos MESMOS serviços do
jogador (`players.services.get_snapshot`, `ledger`), e é a única entrada da política. Nada de Admin/Dev, de reward futuro, de seeds, de outros jogadores
privados ou do estado futuro entra aqui. `ALLOWED_KEYS` é conferido por teste.
"""
from __future__ import annotations

from typing import Any, Dict

from core import clock as game_clock
from ledger import services as ledger
from players import services as player_services

ALLOWED_KEYS = frozenset({"at", "energy", "health", "nutrition", "burnout", "burnout_active", "health_critical", "hospitalized", "qol_current",
                          "money_cents", "work_blocked_by", "study_blocked_by", "leisure_blocked_by"})


def observe(player_id: int) -> Dict[str, Any]:
    """Estado PRÓPRIO do jogador (21 §21.17, "Informação própria"). Valores decimais viram texto exato (determinístico, serializável)."""
    snap = player_services.get_snapshot(player_id)
    account = ledger.player_account(player_id)
    return {
        "at": snap.at, "energy": str(snap.energy), "health": str(snap.health), "nutrition": str(snap.nutrition), "burnout": str(snap.burnout),
        "burnout_active": snap.burnout_active, "health_critical": snap.health_critical, "hospitalized": snap.hospitalized,
        "qol_current": str(snap.qol_current.value), "money_cents": ledger.available_of(account.pk),
        "work_blocked_by": list(snap.work_blocked_by), "study_blocked_by": list(snap.study_blocked_by), "leisure_blocked_by": list(snap.leisure_blocked_by),
    }


def now() -> int:
    return game_clock.now()
