"""
Ações dos Contratos no Action Registry (players.registry; design/21 §20). Nenhuma regra vive aqui: a disponibilidade vem das MESMAS
funções de recusa que a execução usa e o efeito é o do serviço dono. Bots e jogadores usam o mesmo caminho (CLAUDE.md §5.4).

  propose_contract   Propor contrato     alvo = {"type", "role", "proposer": {"kind","id"}, "counterparty": {...}, "terms": {...},
                                                 "frequency", ["starts_on", "ends_on", "penalty_cents", "max_failures"]}
  accept_contract    Aceitar contrato    alvo = {"contract": id, "party": {"kind","id"}}
  decline_contract   Recusar proposta    alvo = {"contract": id, "party": {"kind","id"}}
  withdraw_contract  Retirar proposta    alvo = {"contract": id, "party": {"kind","id"}}
  break_contract     Quebrar contrato    alvo = {"contract": id, "party": {"kind","id"}}
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from players.registry import TARGET_PARAMS, ActionDescriptor, TargetSpec, register_action
from players.services import ActionResult

from . import services

PROPOSE_ID, ACCEPT_ID, DECLINE_ID, WITHDRAW_ID, BREAK_ID = (
    "propose_contract", "accept_contract", "decline_contract", "withdraw_contract", "break_contract")
CONTRACT_KEYS = frozenset({"contract", "party"})


def _invalid(action: str, keys, target) -> ActionResult:
    return ActionResult(False, "INVALID_PARAMS", {"action": action, "expected": sorted(keys), "target": repr(target)[:80]})


def _contract_params(target) -> Optional[dict]:
    return target if isinstance(target, dict) and set(target) == CONTRACT_KEYS else None


def _status_preview(target) -> Dict[str, Any]:
    p = _contract_params(target) if target is not None else None
    view = services.contract_view(p["contract"]) if p is not None and isinstance(p["contract"], int) and not isinstance(p["contract"], bool) else None
    return {} if view is None else {"contract": view}


def _simple(action_id: str, refusal: Callable, execute: Callable):
    def check(player, now, bal, target):
        if target is None:
            return None
        p = _contract_params(target)
        if p is None:
            return _invalid(action_id, CONTRACT_KEYS, target)
        res = refusal(player.pk, p["contract"], p["party"])
        return res if isinstance(res, ActionResult) else None

    def run(player_id, target):
        p = _contract_params(target)
        return _invalid(action_id, CONTRACT_KEYS, target) if p is None else execute(player_id, p["contract"], p["party"])

    def preview(player, now, bal, target):
        return _status_preview(target)

    return check, run, preview


def _propose_check(player, now, bal, target):
    if target is None:
        return None
    res = services.parse_proposal(player.pk, target, now)
    return res if isinstance(res, ActionResult) else None


def _propose_preview(player, now, bal, target) -> Dict[str, Any]:
    if target is None:
        return {}
    res = services.parse_proposal(player.pk, target, now)
    if isinstance(res, ActionResult):
        return {}
    return {"occurrences": res.prepared.occurrences, "penalty_limit_cents": res.prepared.penalty_limit,
            "role_a": res.handler.role_a, "role_b": res.handler.role_b}


def register() -> None:
    register_action(
        ActionDescriptor(
            id=PROPOSE_ID, name="Propor contrato",
            requirements=("INVALID_PARAMS", "PLAYER_NOT_FOUND", "TYPE_NOT_AVAILABLE", "INVALID_ROLE", "INVALID_PARTY", "SAME_PARTY",
                          "PARTY_KIND_NOT_ALLOWED", "PARTY_NOT_FOUND", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER", "INVALID_FREQUENCY",
                          "INVALID_TERMS", "INVALID_SCHEDULE", "INVALID_PENALTY", "INVALID_MAX_FAILURES"),
            cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("contract_proposed",)),
        check=_propose_check, execute=lambda pid, target: services.propose(pid, target), preview=_propose_preview)
    for action_id, name, refusal, execute, requirements, effects in (
            (ACCEPT_ID, "Aceitar contrato", services.accept_refusal, services.accept,
             ("INVALID_PARAMS", "CONTRACT_NOT_FOUND", "NOT_A_PARTY", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER", "NOT_PROPOSED",
              "ALREADY_ACCEPTED", "STARTS_ON_PASSED", "LENDER_INSUFFICIENT_FUNDS"), ("contract_accepted", "contract_activated")),
            (DECLINE_ID, "Recusar proposta de contrato", services.decline_refusal, services.decline,
             ("INVALID_PARAMS", "CONTRACT_NOT_FOUND", "NOT_A_PARTY", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER", "NOT_PROPOSED", "IS_PROPOSER"),
             ("contract_declined",)),
            (WITHDRAW_ID, "Retirar proposta de contrato", services.withdraw_refusal, services.withdraw,
             ("INVALID_PARAMS", "CONTRACT_NOT_FOUND", "NOT_A_PARTY", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER", "NOT_PROPOSED", "NOT_PROPOSER"),
             ("contract_withdrawn",)),
            (BREAK_ID, "Quebrar contrato", services.break_refusal, services.break_contract,
             ("INVALID_PARAMS", "CONTRACT_NOT_FOUND", "NOT_A_PARTY", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER", "NOT_RUNNING",
              "PENALTY_UNPAYABLE"), ("contract_broken", "penalty_paid"))):
        check, run, preview = _simple(action_id, refusal, execute)
        register_action(
            ActionDescriptor(id=action_id, name=name, requirements=requirements, cost=("money",) if action_id == BREAK_ID else (),
                             target=TargetSpec(TARGET_PARAMS, required=True), effects=effects),
            check=check, execute=run, preview=preview)
