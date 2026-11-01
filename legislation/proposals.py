"""
Criar, editar e retirar propostas (design/07 §07.3-§07.5, §07.11, §07.17, §07.20, §07.21-§07.22, §07.23-§07.24).

Toda recusa vem de funções `*_refusal` que a execução e o Action Registry compartilham (bots e jogadores usam o mesmo caminho).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.db import IntegrityError, transaction

from core import clock as game_clock
from players.services import ActionResult

from . import authority, calendar, catalog, laws, params
from .common import event, is_int, keys_refusal, player_exists, refuse
from .constants import ACTIVE, EventKind, Kind, Status
from .models import LegislativeState, Proposal, ProposalVersion

CREATE_KEYS = frozenset({"law"})
CREATE_OPTIONAL = frozenset({"params", "revoke", "description"})
EDIT_KEYS = frozenset({"proposal"})
EDIT_OPTIONAL = frozenset({"params", "description"})
WITHDRAW_KEYS = frozenset({"proposal"})


# --- validação de parâmetros e coerência ----------------------------------------------------------------------------------------------------
def normalize_params(spec: catalog.LawSpec, values: Any) -> Any:
    """Conjunto COMPLETO de parâmetros X da lei, normalizado; ou recusa. Texto e outros elementos da lei não são editáveis (07 §07.2)."""
    if not isinstance(values, dict) or set(values) != {p.name for p in spec.params}:
        return refuse("INVALID_PARAMS", expected=[p.name for p in spec.params])
    out: Dict[str, Any] = {}
    for p in spec.params:
        norm = catalog.normalize(values[p.name], p.kind)
        if norm is None:
            return refuse("INVALID_PARAM_VALUE", param=p.name, value=repr(values[p.name])[:40], kind=p.kind)
        d = catalog.to_decimal(norm)
        if not catalog.to_decimal(p.minimum) <= d <= catalog.to_decimal(p.maximum):
            return refuse("PARAM_OUT_OF_RANGE", param=p.name, value=norm, minimum=p.minimum, maximum=p.maximum)
        out[p.name] = norm
    return out


def coherence_checks(spec: catalog.LawSpec, values: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validações de coerência exibidas no preview (07 §07.24): limites do catálogo, pisos constitucionais e validadores da lei."""
    checks: List[Dict[str, Any]] = []
    for p in spec.params:
        d = catalog.to_decimal(values[p.name])
        ok = catalog.to_decimal(p.minimum) <= d <= catalog.to_decimal(p.maximum)
        checks.append({"key": f"range:{p.name}", "ok": ok, "reason": "within_catalog_limits" if ok else "outside_catalog_limits",
                       "minimum": p.minimum, "maximum": p.maximum, "value": values[p.name]})
        floor = catalog.floor_of(spec.key, p.name)
        if floor is not None:
            fok = d >= catalog.to_decimal(floor)
            checks.append({"key": f"constitutional_floor:{p.name}", "ok": fok, "reason": "above_constitutional_floor" if fok else "below_constitutional_floor",
                           "floor": floor, "value": values[p.name]})
    ctx = laws.context()
    for validator in spec.validators:
        checks.extend(validator(values, ctx))
    return checks


def _current_actor_role(actor_id: int) -> Optional[str]:
    if authority.president() == actor_id:
        return "president"
    if actor_id in authority.deputies():
        return "deputy"
    return None


def proposer_refusal(actor_id: Any) -> Optional[ActionResult]:
    if not player_exists(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    try:
        role = _current_actor_role(actor_id)
    except authority.ProviderConflict as exc:
        return refuse("OFFICE_CONFLICT", detail=str(exc)[:120])
    if role is None:
        return refuse("NOT_A_PROPOSER")          # 07.3: só Presidente e Deputados formalizam
    return None


def new_proposal_refusal(actor_id: Any, target: Any, *, check_actor: bool = True) -> Optional[ActionResult]:
    """Recusas de criar uma proposta; `target` = {"law", "params" | "revoke": true, ["description"]}."""
    bad = keys_refusal(target, CREATE_KEYS, CREATE_OPTIONAL)
    if bad is not None:
        return bad
    if check_actor:
        refusal = proposer_refusal(actor_id)
        if refusal is not None:
            return refusal
    spec = catalog.get(target["law"])
    if spec is None:
        return refuse("UNKNOWN_LAW", law=repr(target["law"])[:60])
    description = target.get("description", "")
    if not isinstance(description, str) or len(description) > params.DESCRIPTION_MAX:
        return refuse("INVALID_DESCRIPTION", maximum=params.DESCRIPTION_MAX)
    revoke = target.get("revoke", False)
    if revoke is not True and revoke is not False:
        return refuse("INVALID_PARAMS", expected=["revoke: bool"])
    now = game_clock.now()
    if revoke:
        if "params" in target:
            return refuse("INVALID_PARAMS", detail="revoke_has_no_params")
        if not laws.in_force(spec.key):
            return refuse("LAW_NOT_IN_FORCE", law=spec.key)
        values = None
    else:
        if "params" not in target:
            return refuse("INVALID_PARAMS", expected=["params"])
        values = normalize_params(spec, target["params"])
        if isinstance(values, ActionResult):
            return values
        if values == laws.current_values(spec.key):
            return refuse("NO_CHANGE", law=spec.key)
        failed = [c for c in coherence_checks(spec, values) if not c["ok"]]
        if failed:
            code = "BELOW_CONSTITUTIONAL_FLOOR" if any(c["key"].startswith("constitutional_floor") for c in failed) else "VALIDATION_FAILED"
            return refuse(code, failed=failed)
    blocking = Proposal.objects.filter(scope=spec.scope, status__in=[s.value for s in ACTIVE]).values_list("pk", flat=True).first()
    if blocking is not None:
        return refuse("LAW_BLOCKED", law=spec.key, scope=spec.scope, blocking_proposal=blocking)
    cooldown = _cooldown_refusal(spec, values, now)
    if cooldown is not None:
        return cooldown
    return None


def _cooldown_refusal(spec: catalog.LawSpec, values: Optional[Dict[str, Any]], now: int) -> Optional[ActionResult]:
    """07 §07.11: reapresentar uma proposta rejeitada espera um cooldown; com alteração REAL de algum X, o cooldown reduzido."""
    last = Proposal.objects.filter(law_key=spec.key, status=Status.REJECTED.value).order_by("-closed_at", "-pk").first()
    if last is None or last.closed_at is None:
        return None
    modified = values != last.rejection_params
    wait = params.COOLDOWN_MODIFIED_SECONDS if modified else params.COOLDOWN_SECONDS
    if now < last.closed_at + wait:
        return refuse("COOLDOWN_ACTIVE", law=spec.key, until=last.closed_at + wait, modified=modified, rejected_proposal=last.pk)
    return None


def create_proposal(actor_id: Any, target: Any, *, _skip_actor_check: bool = False) -> ActionResult:
    with transaction.atomic():
        state = LegislativeState.load(for_update=True)       # serializa criação × avanço do calendário
        refusal = new_proposal_refusal(actor_id, target, check_actor=not _skip_actor_check)
        if refusal is not None:
            return refusal
        spec = catalog.get(target["law"])
        now = game_clock.now()
        revoke = bool(target.get("revoke", False))
        values = None if revoke else normalize_params(spec, target["params"])
        ends = calendar.discussion_ends_at(now)
        try:
            with transaction.atomic():
                proposal = Proposal.objects.create(
                    author_id=actor_id, law_key=spec.key, scope=spec.scope, kind=(Kind.REVOKE if revoke else Kind.CHANGE).value, params=values,
                    description=target.get("description", ""), created_at=now, discussion_ends_at=ends,
                    deadline_at=calendar.monday_at_or_after(ends))
        except IntegrityError:
            return refuse("LAW_BLOCKED", law=spec.key, scope=spec.scope)
        ProposalVersion.objects.create(proposal=proposal, number=1, params=values, description=proposal.description, at=now, by_id=actor_id)
        event(proposal, EventKind.CREATED, now, actor_id, law=spec.key, kind=proposal.kind, params=values, discussion_ends_at=ends)
        return ActionResult(True, "OK", {"proposal": proposal.pk, "version": 1, "discussion_ends_at": ends, "vote_window": proposal.deadline_at})


# --- editar e retirar (só na discussão) -----------------------------------------------------------------------------------------------------
def _own_open_discussion(actor_id: Any, proposal: Optional[Proposal], now: int) -> Optional[ActionResult]:
    if proposal is None:
        return refuse("PROPOSAL_NOT_FOUND")
    if proposal.author_id != actor_id:
        return refuse("NOT_AUTHOR", proposal=proposal.pk)
    if proposal.status != Status.DISCUSSION.value:
        return refuse("NOT_IN_DISCUSSION", proposal=proposal.pk, status=proposal.status)
    if proposal.deadline_at is not None and proposal.deadline_at <= now and LegislativeState.load().interregnum_since is None:
        return refuse("VOTING_STARTED", proposal=proposal.pk)         # a janela semanal já passou: a proposta está congelada (07 §07.5)
    return None


def _find(target: Any, lock: bool = False) -> Optional[Proposal]:
    pid = target.get("proposal") if isinstance(target, dict) else None
    if not is_int(pid):
        return None
    qs = Proposal.objects.select_for_update() if lock else Proposal.objects
    return qs.filter(pk=pid).first()


def edit_refusal(actor_id: Any, target: Any, *, proposal: Optional[Proposal] = None) -> Optional[ActionResult]:
    bad = keys_refusal(target, EDIT_KEYS, EDIT_OPTIONAL)
    if bad is not None:
        return bad
    if not player_exists(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    proposal = proposal if proposal is not None else _find(target)
    now = game_clock.now()
    refusal = _own_open_discussion(actor_id, proposal, now)
    if refusal is not None:
        return refusal
    spec = catalog.get(proposal.law_key)
    if spec is None:
        return refuse("UNKNOWN_LAW", law=proposal.law_key)
    description = target.get("description", proposal.description)
    if not isinstance(description, str) or len(description) > params.DESCRIPTION_MAX:
        return refuse("INVALID_DESCRIPTION", maximum=params.DESCRIPTION_MAX)
    if proposal.kind == Kind.REVOKE.value:
        if "params" in target:
            return refuse("INVALID_PARAMS", detail="revoke_has_no_params")
        values = None
    elif "params" in target:
        values = normalize_params(spec, target["params"])
        if isinstance(values, ActionResult):
            return values
        if values == laws.current_values(spec.key):
            return refuse("NO_CHANGE", law=spec.key)
        failed = [c for c in coherence_checks(spec, values) if not c["ok"]]
        if failed:
            code = "BELOW_CONSTITUTIONAL_FLOOR" if any(c["key"].startswith("constitutional_floor") for c in failed) else "VALIDATION_FAILED"
            return refuse(code, failed=failed)
    else:
        values = proposal.params
    if values == proposal.params and description == proposal.description:
        return refuse("NOTHING_CHANGED", proposal=proposal.pk)
    return None


def edit_proposal(actor_id: Any, target: Any) -> ActionResult:
    """O autor altera os parâmetros X (e/ou a descrição) durante a discussão: nova versão; as anteriores ficam no histórico (07 §07.5, §07.25)."""
    with transaction.atomic():
        proposal = _find(target, lock=True)
        refusal = edit_refusal(actor_id, target, proposal=proposal)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        spec = catalog.get(proposal.law_key)
        values = normalize_params(spec, target["params"]) if "params" in target else proposal.params
        description = target.get("description", proposal.description)
        old = proposal.params
        proposal.params, proposal.description, proposal.version = values, description, proposal.version + 1
        proposal.save(update_fields=["params", "description", "version"])
        ProposalVersion.objects.create(proposal=proposal, number=proposal.version, params=values, description=description, at=now, by_id=actor_id)
        event(proposal, EventKind.EDITED, now, actor_id, version=proposal.version, old_params=old, new_params=values)
        return ActionResult(True, "OK", {"proposal": proposal.pk, "version": proposal.version})


def withdraw_refusal(actor_id: Any, target: Any, *, proposal: Optional[Proposal] = None) -> Optional[ActionResult]:
    bad = keys_refusal(target, WITHDRAW_KEYS)
    if bad is not None:
        return bad
    if not player_exists(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    proposal = proposal if proposal is not None else _find(target)
    return _own_open_discussion(actor_id, proposal, game_clock.now())


def withdraw_proposal(actor_id: Any, target: Any) -> ActionResult:
    with transaction.atomic():
        proposal = _find(target, lock=True)
        refusal = withdraw_refusal(actor_id, target, proposal=proposal)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        proposal.status, proposal.deadline_at, proposal.closed_at = Status.WITHDRAWN.value, None, now
        proposal.save(update_fields=["status", "deadline_at", "closed_at"])
        event(proposal, EventKind.WITHDRAWN, now, actor_id)
        return ActionResult(True, "OK", {"proposal": proposal.pk})
