"""
Registro da ação Viajar no Action Registry (players.registry; design/21 §20). Nenhuma regra nova: a disponibilidade vem de
`travel.services.travel_refusal`, a execução é `start_travel` e o custo/tempo são os de `quote_travel`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from players.actions import Action  # noqa: F401  (Viajar NÃO entra no enum Action: não tem custo de Energia, 04 §2.2)
from players.registry import TARGET_LOT, ActionDescriptor, TargetSpec, register_action
from players.services import ActionResult

from . import services
from .models import PlayerLocation

TRAVEL_ID = "travel"


def payment_status(amount) -> str:
    """
    Como o custo monetário será tratado, SEM cobrar nada: NOT_REQUIRED (custo zero), NO_PAYMENT_SYSTEM (calculado e
    registrado, mas não cobrado: o sistema de dinheiro não existe) ou WOULD_CHARGE (há handler de pagamento).
    """
    if amount == 0:
        return "NOT_REQUIRED"
    return "WOULD_CHARGE" if services.has_payment_handler() else "NO_PAYMENT_SYSTEM"


def _check(player, now, bal, target) -> Optional[ActionResult]:
    origin = PlayerLocation.objects.select_related("lot").get(player=player).lot
    destination, refusal = services.travel_refusal(player, origin, target)
    if refusal is not None or destination is None:
        return refusal
    # Mesma fonte do custo de `start_travel`; só CONSULTA o saldo (nada é cobrado aqui).
    return services.funds_refusal(player, services.quote_travel(origin, destination, now, player).amount)


def _execute(player_id: int, target: Any) -> ActionResult:
    return services.start_travel(player_id, target)


def _preview(player, now, bal, target) -> Dict[str, Any]:
    """Com destino válido: tempo e custo (Explained). Sem destino ou inválido, não há o que cotar."""
    if target is None:
        return {}
    from geography.models import Lot
    destination = Lot.objects.filter(pk=target).first()
    if destination is None:
        return {}
    origin = PlayerLocation.objects.select_related("lot").get(player=player).lot
    quote = services.quote_travel(origin, destination, now, player)
    return {"travel_time": quote.time, "travel_cost": quote.cost, "duration_seconds": quote.duration_seconds,
            "amount": quote.amount, "payment": payment_status(quote.amount)}


def register() -> None:
    register_action(
        ActionDescriptor(
            id=TRAVEL_ID, name="Viajar",
            requirements=("INVALID_DESTINATION", "ALREADY_TRAVELING", "SAME_LOCATION", "INSUFFICIENT_FUNDS"),
            cost=("time", "money"), target=TargetSpec(TARGET_LOT, required=True), effects=("journey_started",)),
        check=_check, execute=_execute, preview=_preview)
