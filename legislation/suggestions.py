"""Sugestões de Governadores e Prefeitos ao Presidente (design/07 §07.3): não criam proposta; o Presidente decide se a formaliza."""
from __future__ import annotations

from typing import Any, Optional

from django.db import transaction

from core import clock as game_clock
from players.services import ActionResult

from . import authority, catalog, params, proposals
from .common import is_int, keys_refusal, player_exists, refuse
from .constants import Kind, SuggestionStatus
from .models import Suggestion

SUGGEST_KEYS = frozenset({"law"})
SUGGEST_OPTIONAL = frozenset({"params", "revoke", "description"})
DECIDE_KEYS = frozenset({"suggestion"})


def suggest_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    bad = keys_refusal(target, SUGGEST_KEYS, SUGGEST_OPTIONAL)
    if bad is not None:
        return bad
    if not player_exists(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    if actor_id not in authority.suggesters():
        return refuse("NOT_A_SUGGESTER")                 # só Governadores e Prefeitos sugerem (07 §07.3)
    # a sugestão precisa ser uma proposta válida em forma (lei, parâmetros X, coerência); o bloqueio por conflito/cooldown vale só na formalização
    spec = catalog.get(target["law"])
    if spec is None:
        return refuse("UNKNOWN_LAW", law=repr(target["law"])[:60])
    if not isinstance(target.get("description", ""), str) or len(target.get("description", "")) > params.DESCRIPTION_MAX:
        return refuse("INVALID_DESCRIPTION", maximum=params.DESCRIPTION_MAX)
    if target.get("revoke", False) is True:
        if "params" in target:
            return refuse("INVALID_PARAMS", detail="revoke_has_no_params")
        return None
    if "params" not in target:
        return refuse("INVALID_PARAMS", expected=["params"])
    values = proposals.normalize_params(spec, target["params"])
    if isinstance(values, ActionResult):
        return values
    failed = [c for c in proposals.coherence_checks(spec, values) if not c["ok"]]
    if failed:
        return refuse("VALIDATION_FAILED", failed=failed)
    return None


def suggest_law(actor_id: Any, target: Any) -> ActionResult:
    with transaction.atomic():
        refusal = suggest_refusal(actor_id, target)
        if refusal is not None:
            return refusal
        spec = catalog.get(target["law"])
        revoke = target.get("revoke", False) is True
        values = None if revoke else proposals.normalize_params(spec, target["params"])
        s = Suggestion.objects.create(author_id=actor_id, law_key=spec.key, kind=(Kind.REVOKE if revoke else Kind.CHANGE).value, params=values,
                                      description=target.get("description", ""), created_at=game_clock.now())
        return ActionResult(True, "OK", {"suggestion": s.pk})


def _decide_refusal(actor_id: Any, target: Any, s: Optional[Suggestion]) -> Optional[ActionResult]:
    bad = keys_refusal(target, DECIDE_KEYS)
    if bad is not None:
        return bad
    if not player_exists(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    try:
        president = authority.president()
    except authority.ProviderConflict as exc:
        return refuse("OFFICE_CONFLICT", detail=str(exc)[:120])
    if president is None or president != actor_id:
        return refuse("NOT_PRESIDENT")
    if s is None:
        return refuse("SUGGESTION_NOT_FOUND")
    if s.status != SuggestionStatus.PENDING.value:
        return refuse("SUGGESTION_DECIDED", status=s.status)
    return None


def _get(target: Any, lock: bool = False) -> Optional[Suggestion]:
    sid = target.get("suggestion") if isinstance(target, dict) else None
    if not is_int(sid):
        return None
    return (Suggestion.objects.select_for_update() if lock else Suggestion.objects).filter(pk=sid).first()


def adopt_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    s = _get(target)
    refusal = _decide_refusal(actor_id, target, s)
    if refusal is not None:
        return refusal
    return proposals.new_proposal_refusal(actor_id, _as_proposal(s))


def _as_proposal(s: Suggestion) -> dict:
    out: dict = {"law": s.law_key, "description": s.description}
    if s.kind == Kind.REVOKE.value:
        out["revoke"] = True
    else:
        out["params"] = s.params
    return out


def adopt_suggestion(actor_id: Any, target: Any) -> ActionResult:
    """O Presidente transforma a sugestão em proposta formal (ele passa a ser o autor); todas as recusas de uma proposta valem."""
    with transaction.atomic():
        s = _get(target, lock=True)
        refusal = _decide_refusal(actor_id, target, s)
        if refusal is not None:
            return refusal
        res = proposals.create_proposal(actor_id, _as_proposal(s))
        if not res.ok:
            return res
        s.status, s.decided_at, s.decided_by_id, s.proposal_id = SuggestionStatus.ADOPTED.value, game_clock.now(), actor_id, res.detail["proposal"]
        s.save(update_fields=["status", "decided_at", "decided_by_id", "proposal"])
        return ActionResult(True, "OK", {"suggestion": s.pk, **res.detail})


def dismiss_suggestion(actor_id: Any, target: Any) -> ActionResult:
    with transaction.atomic():
        s = _get(target, lock=True)
        refusal = _decide_refusal(actor_id, target, s)
        if refusal is not None:
            return refusal
        s.status, s.decided_at, s.decided_by_id = SuggestionStatus.DISMISSED.value, game_clock.now(), actor_id
        s.save(update_fields=["status", "decided_at", "decided_by_id"])
        return ActionResult(True, "OK", {"suggestion": s.pk})


def dismiss_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    return _decide_refusal(actor_id, target, _get(target))
