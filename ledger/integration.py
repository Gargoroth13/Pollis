"""
Ligação do registro monetário com os sistemas existentes (design/24 §24.18). Sem importar módulos futuros (empresas, milícia).

  - jogador criado → conta do jogador + dotação do cenário ATIVO (zero explícito vale; ausente recusa);
  - viagem → `PLAYER → UNION`, natureza `TRAVEL_FEE`; só cobra enquanto houver cenário monetário ativo (sem ele, a viagem
    se comporta como antes: custo calculado e registrado, não cobrado).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from .constants import Nature
from . import services as ledger
from .money import from_reais

HANDLER_NAME = "ledger"
PLAYER_ROLE = "player"


def on_player_created(player, now: int) -> None:
    account = ledger.player_account(player.pk)
    result = ledger.grant_for_role(account.pk, PLAYER_ROLE, at=now)
    if not result.ok:        # SCENARIO_GRANT_UNSPECIFIED: o cenário ativo não declarou a dotação do jogador
        raise ledger.LedgerRefusal(result)


def _travel_key(player_id: int, ctx: Dict[str, Any]) -> str:
    return f"travel:{player_id}:{ctx['at']}:{ctx['origin'].pk}:{ctx['destination'].pk}"


def pay_travel(player, amount: Decimal, ctx: Dict[str, Any]) -> bool:
    """Handler de `travel.services`: roda dentro da transação do jogador travado; falhar aqui desfaz tudo."""
    cents = from_reais(amount)
    key = _travel_key(player.pk, ctx)
    result = ledger.transfer(
        ledger.player_account(player.pk).pk, ledger.union_account().pk, cents, Nature.TRAVEL_FEE, key=key,
        reference_kind="travel", reference_id=key.split(":", 1)[1], at=ctx["at"], actor=f"player:{player.pk}",
        category="travel", operation="start_travel",
        explained={"origin": ctx["origin"].pk, "destination": ctx["destination"].pk, "amount": cents})
    return result.ok


def check_travel_funds(player, amount: Decimal) -> Optional[Dict[str, Any]]:
    """Consulta sem cobrar: None se o jogador pode pagar; senão o detalhamento (saldo bruto, reservado, disponível, falta)."""
    quote = ledger.quote(ledger.player_account(player.pk).pk, from_reais(amount))
    return None if quote.ok else dict(quote.detail)


def travel_system_active() -> bool:
    return ledger.active_scenario() is not None


def register_travel_payment() -> None:
    from travel import services as travel
    if travel.has_payment_handler() or travel._payment_handler is not None:
        return          # já registrado (recarga do app em testes)
    travel.register_payment_handler(HANDLER_NAME, pay_travel, active=travel_system_active, check_funds=check_travel_funds)
