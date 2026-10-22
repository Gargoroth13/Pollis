"""
Ações das Escolas no Action Registry (players.registry; design/21 §20). Nenhuma regra vive aqui: a disponibilidade vem da MESMA função
de recusa que a execução usa (`services.change_refusal`) e o efeito é o do serviço dono. Bots e jogadores usam o mesmo caminho.

  change_school  Trocar de escola   alvo = {"school": id}   (03 §2: só para outra escola do MESMO bairro)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from players.registry import TARGET_PARAMS, ActionDescriptor, TargetSpec, register_action
from players.services import ActionResult

from . import services

CHANGE_ID = "change_school"
CHANGE_KEYS = frozenset({"school"})


def _params(target) -> Optional[dict]:
    return target if isinstance(target, dict) and set(target) == CHANGE_KEYS else None


def _invalid(target) -> ActionResult:
    return ActionResult(False, "INVALID_PARAMS", {"action": CHANGE_ID, "expected": sorted(CHANGE_KEYS), "target": repr(target)[:80]})


def _check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    p = _params(target)
    return _invalid(target) if p is None else services.change_refusal(player.pk, p["school"])


def _execute(player_id: int, target: Any) -> ActionResult:
    p = _params(target)
    return _invalid(target) if p is None else services.change_school(player_id, p["school"])


def _preview(player, now, bal, target) -> Dict[str, Any]:
    p = _params(target) if target is not None else None
    if p is None or not isinstance(p["school"], int) or isinstance(p["school"], bool):
        return {}
    status = services.school_status(p["school"])
    return {} if status is None else {"school": status}


def register() -> None:
    register_action(
        ActionDescriptor(
            id=CHANGE_ID, name="Trocar de escola",
            requirements=("INVALID_PARAMS", "PLAYER_NOT_FOUND", "SCHOOL_NOT_FOUND", "NOT_ENROLLED", "ALREADY_ENROLLED_HERE",
                          "SCHOOL_IN_OTHER_NEIGHBORHOOD", "SCHOOL_FULL"),
            cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("enrollment_changed",)),
        check=_check, execute=_execute, preview=_preview)
