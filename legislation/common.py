from __future__ import annotations

from typing import Any, Optional

from players.models import Player
from players.services import ActionResult

from .constants import EventKind
from .models import Proposal, ProposalEvent


def refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and -(2 ** 63) <= v < 2 ** 63


def player_exists(player_id: Any) -> bool:
    return is_int(player_id) and Player.objects.filter(pk=player_id).exists()


def event(proposal: Proposal, ev: EventKind, at: int, actor_id: Optional[int] = None, **data) -> ProposalEvent:
    return ProposalEvent.objects.create(proposal=proposal, kind=ev.value, at=at, actor_id=actor_id, data=data)


def keys_refusal(target: Any, required: frozenset, optional: frozenset = frozenset()) -> Optional[ActionResult]:
    if not isinstance(target, dict) or not required <= set(target) or not set(target) <= required | optional:
        return refuse("INVALID_PARAMS", expected=sorted(required), optional=sorted(optional))
    return None
