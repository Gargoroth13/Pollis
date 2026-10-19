"""
Ações das Empresas no Action Registry (players.registry; design/21 §20). Nenhuma regra vive aqui: a disponibilidade vem das MESMAS
funções de recusa que a execução usa, o efeito é o do serviço dono e o feedback vem dos `Explained` (20). Bots e jogadores
reais usam o mesmo caminho (CLAUDE.md §5.4).

  found_company  Fundar empresa   alvo = {"type": tipo, "name": texto, "owner_salary_cents": n}
  fund_company   Aportar capital  alvo = {"company": id, "amount_cents": n}
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from players.registry import TARGET_PARAMS, ActionDescriptor, TargetSpec, register_action
from players.services import ActionResult

from . import services

FOUND_ID = "found_company"
FUND_ID = "fund_company"
FOUND_KEYS = frozenset({"type", "name", "owner_salary_cents"})
FUND_KEYS = frozenset({"company", "amount_cents"})


def _invalid(action: str, keys, target) -> ActionResult:
    return ActionResult(False, "INVALID_PARAMS", {"action": action, "expected": sorted(keys), "target": repr(target)[:80]})


def _params(target, keys) -> Optional[dict]:
    return target if isinstance(target, dict) and set(target) == keys else None


def _found_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    p = _params(target, FOUND_KEYS)
    return _invalid(FOUND_ID, FOUND_KEYS, target) if p is None else services.founding_refusal(
        player.pk, p["type"], p["name"], p["owner_salary_cents"])


def _found_execute(player_id: int, target: Any) -> ActionResult:
    p = _params(target, FOUND_KEYS)
    return _invalid(FOUND_ID, FOUND_KEYS, target) if p is None else services.found_company(
        player_id, p["type"], p["name"], p["owner_salary_cents"])


def _found_preview(player, now, bal, target) -> Dict[str, Any]:
    p = _params(target, FOUND_KEYS) if target is not None else None
    if p is None or not isinstance(p["type"], str):
        return {}
    cost = services.founding_cost(p["type"])
    return {} if cost is None else {"cost": cost, "cost_cents": int(cost.value)}


def _fund_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    p = _params(target, FUND_KEYS)
    return _invalid(FUND_ID, FUND_KEYS, target) if p is None else services.contribution_refusal(
        player.pk, p["company"], p["amount_cents"])


def _fund_execute(player_id: int, target: Any) -> ActionResult:
    p = _params(target, FUND_KEYS)
    return _invalid(FUND_ID, FUND_KEYS, target) if p is None else services.fund_company(
        player_id, p["company"], p["amount_cents"])


def _fund_preview(player, now, bal, target) -> Dict[str, Any]:
    return {}


def register() -> None:
    register_action(
        ActionDescriptor(
            id=FOUND_ID, name="Fundar empresa",
            requirements=("INVALID_PARAMS", "INVALID_COMPANY_TYPE", "INVALID_NAME", "INVALID_SALARY", "INSUFFICIENT_FUNDS"),
            cost=("money",), target=TargetSpec(TARGET_PARAMS, required=True),
            effects=("company_founded", "owner_position_created", "founding_fee_charged")),
        check=_found_check, execute=_found_execute, preview=_found_preview)
    register_action(
        ActionDescriptor(
            id=FUND_ID, name="Aportar capital na empresa",
            requirements=("INVALID_PARAMS", "INVALID_AMOUNT", "COMPANY_NOT_FOUND", "NOT_OWNER", "INSUFFICIENT_FUNDS"),
            cost=("money",), target=TargetSpec(TARGET_PARAMS, required=True), effects=("capital_contributed",)),
        check=_fund_check, execute=_fund_execute, preview=_fund_preview)
