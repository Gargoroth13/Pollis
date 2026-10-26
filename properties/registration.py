"""
Ações dos Imóveis no Action Registry (players.registry; design/21 §20). Nenhuma regra vive aqui: a disponibilidade vem das MESMAS
funções de recusa que a execução usa. Bots e jogadores usam o mesmo caminho (CLAUDE.md §5.4). Abrir leilão NÃO é ação de jogador
(lacuna registrada em `design/10a`): é ferramenta do sistema (`services.open_auction`, comando `open_auctions`).

  bid_auction      Dar lance no leilão     alvo = {"auction": id, "bidder": {"kind","id"}, "amount": centavos}
  list_property    Anunciar imóvel         alvo = {"lot": id, "owner": {"kind","id"}, "price": centavos}
  unlist_property  Retirar anúncio         alvo = {"listing": id, "party": {"kind","id"}}
  buy_property     Comprar imóvel          alvo = {"listing": id, "party": {"kind","id"}}
A obra com lote usa a ação de iniciar obra da Construtora (`start_construction`), com o parâmetro opcional `lot`.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from players.registry import TARGET_PARAMS, ActionDescriptor, TargetSpec, register_action
from players.services import ActionResult

from . import services

BID_ID, LIST_ID, UNLIST_ID, BUY_ID = "bid_auction", "list_property", "unlist_property", "buy_property"
BID_KEYS, LIST_KEYS, LISTING_KEYS = services.BID_KEYS, services.LIST_KEYS, services.LISTING_KEYS


def _invalid(action: str, keys, target) -> ActionResult:
    return ActionResult(False, "INVALID_PARAMS", {"action": action, "expected": sorted(keys), "target": repr(target)[:80]})


def _params(target, keys) -> Optional[dict]:
    return target if isinstance(target, dict) and set(target) == keys else None


def _make(action_id: str, keys, refusal: Callable, execute: Callable, order: tuple, view: Callable):
    def args(p):
        return [p[k] for k in order]

    def check(player, now, bal, target):
        if target is None:
            return None
        p = _params(target, keys)
        if p is None:
            return _invalid(action_id, keys, target)
        return refusal(player.pk, *args(p))

    def run(player_id, target):
        p = _params(target, keys)
        return _invalid(action_id, keys, target) if p is None else execute(player_id, *args(p))

    def preview(player, now, bal, target):
        p = _params(target, keys) if target is not None else None
        return {} if p is None else view(p)

    return check, run, preview


def _auction_preview(p) -> Dict[str, Any]:
    v = services.auction_view(p["auction"]) if isinstance(p["auction"], int) and not isinstance(p["auction"], bool) else None
    return {} if v is None else {"auction": v}


def _lot_preview(p) -> Dict[str, Any]:
    v = services.lot_view(p["lot"]) if isinstance(p["lot"], int) and not isinstance(p["lot"], bool) else None
    return {} if v is None else {"lot": v}


def _listing_preview(p) -> Dict[str, Any]:
    from .models import Listing
    pk = p["listing"]
    row = Listing.objects.filter(pk=pk).first() if isinstance(pk, int) and not isinstance(pk, bool) else None
    return {} if row is None else {"listing": {"id": row.pk, "lot": row.lot_id, "price_cents": row.price_cents, "status": row.status}}


def register() -> None:
    for action_id, name, keys, refusal, execute, order, view, requirements, effects, cost in (
        (BID_ID, "Dar lance em leilão", BID_KEYS, services.bid_refusal, services.bid, ("auction", "bidder", "amount"), _auction_preview,
         ("INVALID_PARAMS", "PLAYER_NOT_FOUND", "INVALID_PARTY", "AUCTION_NOT_FOUND", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER",
          "COMPANY_NOT_FOUND", "AUCTION_NOT_OPEN", "AUCTION_ENDED", "ALREADY_TOP_BIDDER", "BID_TOO_LOW", "INSUFFICIENT_FUNDS"),
         ("auction_bid", "auction_extended"), ("money",)),
        (LIST_ID, "Anunciar imóvel à venda", LIST_KEYS, services.list_refusal, services.list_property, ("lot", "owner", "price"), _lot_preview,
         ("INVALID_PARAMS", "PLAYER_NOT_FOUND", "INVALID_PARTY", "LOT_NOT_FOUND", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER",
          "COMPANY_NOT_FOUND", "NOT_LOT_OWNER", "LOT_HAS_ACTIVE_SITE", "ALREADY_LISTED"), ("property_listed",), ()),
        (UNLIST_ID, "Retirar anúncio de imóvel", LISTING_KEYS, services.unlist_refusal, services.unlist_property, ("listing", "party"),
         _listing_preview,
         ("INVALID_PARAMS", "PLAYER_NOT_FOUND", "INVALID_PARTY", "LISTING_NOT_FOUND", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER",
          "COMPANY_NOT_FOUND", "LISTING_NOT_OPEN", "NOT_SELLER"), ("property_unlisted",), ()),
        (BUY_ID, "Comprar imóvel anunciado", LISTING_KEYS, services.buy_refusal, services.buy_property, ("listing", "party"), _listing_preview,
         ("INVALID_PARAMS", "PLAYER_NOT_FOUND", "INVALID_PARTY", "LISTING_NOT_FOUND", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER",
          "COMPANY_NOT_FOUND", "LISTING_NOT_OPEN", "SELF_PURCHASE", "LISTING_STALE", "LOT_HAS_ACTIVE_SITE", "INSUFFICIENT_FUNDS"),
         ("property_bought", "title_transferred"), ("money",)),
    ):
        check, run, preview = _make(action_id, keys, refusal, execute, order, view)
        register_action(
            ActionDescriptor(id=action_id, name=name, requirements=requirements, cost=cost,
                             target=TargetSpec(TARGET_PARAMS, required=True), effects=effects),
            check=check, execute=run, preview=preview)
