"""
Ações do Orçamento no Action Registry (players.registry; design/09, design/21 §20). Nenhuma regra vive aqui: a disponibilidade vem das MESMAS funções de
recusa que a execução usa. Bots e jogadores usam o mesmo caminho (CLAUDE.md §5.4).

  budget_transfer      Repassar verba (Presidente → Estado; Governador → Município do Estado)
                       alvo = {"from": {"level","id"}, "to": {"level","id"}, "amount": centavos, ["reason": texto]}
  set_budget_plan      Montar o plano orçamentário municipal do período (Prefeito)   alvo = {"city": id, "lines": {"education": centavos, ...}, ["period": n]}
  confirm_budget_plan  Confirmar o plano (confere pisos e disponível)                alvo = {"city": id, ["period": n]}
"""
from __future__ import annotations

from typing import Any, Dict

from players.registry import TARGET_PARAMS, ActionDescriptor, TargetSpec, register_action

from . import fiscal, plans, transfers
from .constants import Level
from .govs import is_int, parse_gov

TRANSFER_ID, SET_PLAN_ID, CONFIRM_PLAN_ID = "budget_transfer", "set_budget_plan", "confirm_budget_plan"


def _transfer_preview(player, now, bal, target) -> Dict[str, Any]:
    if not isinstance(target, dict) or "from" not in target or not is_int(target.get("amount")) or target["amount"] <= 0:
        return {}
    src = parse_gov(target["from"])
    if isinstance(src, tuple):
        from .govs import account_of
        return {"funds": transfers.funds_quote(account_of(*src), target["amount"])}
    return {}


def _plan_preview(player, now, bal, target) -> Dict[str, Any]:
    city = target.get("city") if isinstance(target, dict) else None
    if not is_int(city):
        return {}
    view = plans.plan_view(city, target.get("period"), now) if is_int(target.get("period", 0)) else None
    return {} if view is None else {"plan": view}


def register() -> None:
    register_action(
        ActionDescriptor(id=TRANSFER_ID, name="Repassar verba a outro governo",
                         requirements=("INVALID_PARAMS", "INVALID_AMOUNT", "INVALID_REASON", "INVALID_GOVERNMENT", "GOVERNMENT_NOT_FOUND", "PLAYER_NOT_FOUND",
                                       "TRANSFER_NOT_ALLOWED", "MUNICIPALITY_NOT_IN_STATE", "NO_OFFICE_HOLDER", "NOT_OFFICE_HOLDER", "OFFICE_CONFLICT",
                                       "INSUFFICIENT_FUNDS"),
                         cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("budget_transferred", "decision_recorded")),
        check=lambda player, now, bal, target: None if target is None else transfers.transfer_refusal(player.pk, target),
        execute=transfers.transfer_budget, preview=_transfer_preview)
    register_action(
        ActionDescriptor(id=SET_PLAN_ID, name="Montar plano orçamentário municipal",
                         requirements=("INVALID_PARAMS", "INVALID_LINES", "INVALID_AREA", "AREA_NOT_MUNICIPAL", "INVALID_AMOUNT", "INVALID_PERIOD",
                                       "PERIOD_ENDED", "PLAYER_NOT_FOUND", "GOVERNMENT_NOT_FOUND", "NO_OFFICE_HOLDER", "NOT_OFFICE_HOLDER",
                                       "OFFICE_CONFLICT", "PLAN_CONFIRMED"),
                         cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("budget_plan_drafted",)),
        check=lambda player, now, bal, target: None if target is None else plans.set_plan_refusal(player.pk, target),
        execute=plans.set_plan, preview=_plan_preview)
    register_action(
        ActionDescriptor(id=CONFIRM_PLAN_ID, name="Confirmar plano orçamentário municipal",
                         requirements=("INVALID_PARAMS", "INVALID_PERIOD", "PERIOD_ENDED", "PLAYER_NOT_FOUND", "GOVERNMENT_NOT_FOUND", "NO_OFFICE_HOLDER",
                                       "NOT_OFFICE_HOLDER", "OFFICE_CONFLICT", "PLAN_NOT_FOUND", "PLAN_CONFIRMED", "FLOOR_NOT_MET",
                                       "FLOORS_EXCEED_100_PERCENT", "PLAN_EXCEEDS_AVAILABLE"),
                         cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("budget_plan_confirmed", "decision_recorded")),
        check=lambda player, now, bal, target: None if target is None else plans.confirm_refusal(player.pk, target),
        execute=plans.confirm_plan, preview=_plan_preview)
