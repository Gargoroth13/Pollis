"""
Ações do Inventário no Action Registry (players.registry; design/21 §20). Nenhuma regra nova vive aqui: a disponibilidade vem das
MESMAS funções de recusa que a execução usa (`consumption_refusal`, `send_refusal`), o efeito é o do serviço dono, e o
feedback vem dos `Explained` (20). Bots e jogadores reais usam o mesmo caminho (CLAUDE.md §5.4).

  consume    Consumir  alvo = chave do produto (alimento do inventário)
  send_item  Correio   alvo = {"recipient": id, "product": chave, "quantity": n}
  auto_consumption  Auto-consumo (04 §16)   alvo = {"enabled": bool, "preferred": chave | None}
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from players.registry import TARGET_PARAMS, TARGET_PRODUCT, ActionDescriptor, TargetSpec, register_action
from players.services import ActionResult

from . import auto, services

CONSUME_ID = "consume"
SEND_ID = "send_item"
SEND_KEYS = frozenset({"recipient", "product", "quantity"})
AUTO_ID = "auto_consumption"
AUTO_KEYS = frozenset({"enabled", "preferred"})


# --- Consumir -----------------------------------------------------------------------------------------------------------

def _consume_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:                      # disponibilidade geral: o alvo ainda não foi escolhido
        return None
    refusal = services.consumption_refusal(target)
    if refusal is not None:
        return refusal
    if services.quantity_of(player.pk, target) < 1:
        return ActionResult(False, "NOT_IN_INVENTORY", {"key": target})
    return None


def _consume_execute(player_id: int, target: Any) -> ActionResult:
    return services.consume(player_id, target)


def _consume_preview(player, now, bal, target) -> Dict[str, Any]:
    if target is None or services.consumption_refusal(target) is not None:
        return {}
    quote = services.consumption_quote(player, target, now)
    return {"nutrition_gain": quote.nutrition,
            "qol_effect": None if quote.qol_effect is None else {
                "source": quote.qol_effect.source, "amount": quote.qol_effect.amount,
                "duration_seconds": quote.qol_effect.duration_seconds},
            "in_inventory": services.quantity_of(player.pk, target)}


# --- Correio ------------------------------------------------------------------------------------------------------------

def _send_params(target) -> Optional[tuple]:
    """(destinatário, produto, quantidade) se o alvo tem exatamente as chaves esperadas; senão None."""
    if not isinstance(target, dict) or set(target) != SEND_KEYS:
        return None
    return target["recipient"], target["product"], target["quantity"]


def _invalid(target) -> ActionResult:
    return ActionResult(False, "INVALID_PARAMS", {"action": SEND_ID, "expected": sorted(SEND_KEYS),
                                                  "target": repr(target)[:80]})


def _send_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    parsed = _send_params(target)
    if parsed is None:
        return _invalid(target)
    recipient, product, quantity = parsed
    if not isinstance(product, str):
        return _invalid(target)
    return services.send_refusal(player.pk, recipient, product, quantity)


def _send_execute(player_id: int, target: Any) -> ActionResult:
    parsed = _send_params(target)
    if parsed is None or not isinstance(parsed[1], str):
        return _invalid(target)
    return services.send_item(player_id, *parsed)


def _send_preview(player, now, bal, target) -> Dict[str, Any]:
    parsed = _send_params(target) if target is not None else None
    if parsed is None or not isinstance(parsed[1], str):
        return {}
    fee, refusal = services.mail_fee(parsed[1], parsed[2])
    return {} if refusal is not None else {"fee": fee, "fee_cents": services.fee_cents(fee)}


# --- Auto-consumo (04 §16) ----------------------------------------------------------------------------------------------

def _auto_params(target) -> Optional[tuple]:
    if not isinstance(target, dict) or set(target) != AUTO_KEYS:
        return None
    return target["enabled"], target["preferred"]


def _auto_invalid(target) -> ActionResult:
    return ActionResult(False, "INVALID_PARAMS", {"action": AUTO_ID, "expected": sorted(AUTO_KEYS), "target": repr(target)[:80]})


def _auto_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    parsed = _auto_params(target)
    return _auto_invalid(target) if parsed is None else auto.configuration_refusal(*parsed)


def _auto_execute(player_id: int, target: Any) -> ActionResult:
    parsed = _auto_params(target)
    return _auto_invalid(target) if parsed is None else auto.configure(player_id, *parsed)


def _auto_preview(player, now, bal, target) -> Dict[str, Any]:
    return {"current": auto.settings_of(player.pk), "threshold": auto.AUTO_CONSUME_BELOW}


def register() -> None:
    register_action(
        ActionDescriptor(
            id=CONSUME_ID, name="Consumir",
            requirements=("UNKNOWN_PRODUCT", "NO_CONSUMPTION_EFFECT", "UNSPECIFIED_DESIGN_VALUE", "NOT_IN_INVENTORY"),
            cost=("item",), target=TargetSpec(TARGET_PRODUCT, required=True),
            effects=("item_consumed", "nutrition", "food_qol_effect")),
        check=_consume_check, execute=_consume_execute, preview=_consume_preview)
    register_action(
        ActionDescriptor(
            id=SEND_ID, name="Enviar item pelo Correio",
            requirements=("INVALID_QUANTITY", "INVALID_PARAMS", "SAME_PLAYER", "RECIPIENT_NOT_FOUND", "UNKNOWN_PRODUCT",
                          "UNSPECIFIED_DESIGN_VALUE", "INSUFFICIENT_QUANTITY", "INSUFFICIENT_FUNDS"),
            cost=("item", "money"), target=TargetSpec(TARGET_PARAMS, required=True),
            effects=("item_transferred", "mail_fee_charged")),
        check=_send_check, execute=_send_execute, preview=_send_preview)
    register_action(
        ActionDescriptor(
            id=AUTO_ID, name="Configurar Auto-consumo",
            requirements=("INVALID_PARAMS", "UNKNOWN_PRODUCT", "NO_CONSUMPTION_EFFECT", "UNSPECIFIED_DESIGN_VALUE"),
            cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("auto_consumption_configured",)),
        check=_auto_check, execute=_auto_execute, preview=_auto_preview)
