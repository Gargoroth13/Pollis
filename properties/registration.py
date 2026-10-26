"""
Ações dos Imóveis no Action Registry (players.registry; design/21 §20). Nenhuma regra vive aqui: a disponibilidade vem das MESMAS
funções de recusa que a execução usa. Bots e jogadores usam o mesmo caminho (CLAUDE.md §5.4). Abrir leilão NÃO é ação de jogador
(lacuna registrada em `design/10a`): é ferramenta do sistema (`services.open_auction`, comando `open_auctions`).

  bid_auction      Dar lance no leilão     alvo = {"auction": id, "bidder": {"kind","id"}, "amount": centavos}
  list_property    Anunciar imóvel         alvo = {"lot": id, "owner": {"kind","id"}, "price": centavos}
  unlist_property  Retirar anúncio         alvo = {"listing": id, "party": {"kind","id"}}
  buy_property     Comprar imóvel          alvo = {"listing": id, "party": {"kind","id"}}
  set_residence    Definir residência ativa alvo = {"unit": id | null}  (null = moradia inicial)
  list_rent        Anunciar unidade p/ aluguel  alvo = {"unit": id, "owner": {"kind","id"}, "amount": centavos, "frequency": "daily|weekly|monthly",
                                                       ["penalty": centavos, "max_failures": n]}
  unlist_rent      Retirar anúncio de aluguel   alvo = {"listing": id, "owner": {"kind","id"}}
  rent_unit        Alugar unidade anunciada     alvo = {"listing": id, "tenant": {"kind","id"}, "starts_on": dia, "ends_on": dia}
  (o contrato `rent` em si usa as ações de contrato: propose/accept/decline/withdraw/break_contract)
A obra com lote usa a ação de iniciar obra da Construtora (`start_construction`), com o parâmetro opcional `lot`.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from players.registry import TARGET_PARAMS, ActionDescriptor, TargetSpec, register_action
from players.services import ActionResult

from . import housing, rent, services

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


SET_RESIDENCE_ID, LIST_RENT_ID, UNLIST_RENT_ID, RENT_UNIT_ID = "set_residence", "list_rent", "unlist_rent", "rent_unit"


def _register_housing() -> None:
    def residence_check(player, now, bal, target):
        if target is None:
            return None
        if not isinstance(target, dict) or set(target) != {"unit"}:
            return _invalid(SET_RESIDENCE_ID, {"unit"}, target)
        return housing.residence_refusal(player.pk, target["unit"])

    def residence_run(player_id, target):
        if not isinstance(target, dict) or set(target) != {"unit"}:
            return _invalid(SET_RESIDENCE_ID, {"unit"}, target)
        return housing.set_residence(player_id, target["unit"])

    def residence_preview(player, now, bal, target):
        return {"residence": housing.residence_view(player.pk)}

    register_action(
        ActionDescriptor(id=SET_RESIDENCE_ID, name="Definir residência ativa",
                         requirements=("INVALID_PARAMS", "PLAYER_NOT_FOUND", "UNIT_NOT_FOUND", "ALREADY_RESIDENT", "UNIT_OCCUPIED",
                                       "NOT_ENTITLED_TO_UNIT"),
                         cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("residence_changed", "qol_base_changed")),
        check=residence_check, execute=residence_run, preview=residence_preview)

    def simple(action_id, name, refusal, execute, requirements, effects):
        def check(player, now, bal, target):
            return None if target is None else refusal(player.pk, target)

        def preview(player, now, bal, target):
            unit = target.get("unit") if isinstance(target, dict) else None
            view = housing.unit_view(unit) if isinstance(unit, int) and not isinstance(unit, bool) else None
            return {} if view is None else {"unit": view}

        register_action(
            ActionDescriptor(id=action_id, name=name, requirements=requirements, cost=(),
                             target=TargetSpec(TARGET_PARAMS, required=True), effects=effects),
            check=check, execute=lambda pid, target: execute(pid, target), preview=preview)

    simple(LIST_RENT_ID, "Anunciar unidade para aluguel", rent.list_rent_refusal, rent.list_rent,
           ("INVALID_PARAMS", "PLAYER_NOT_FOUND", "INVALID_PARTY", "INVALID_FREQUENCY", "INVALID_PENALTY", "INVALID_MAX_FAILURES",
            "UNIT_NOT_FOUND", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER", "COMPANY_NOT_FOUND", "NOT_LOT_OWNER", "UNIT_LEASED", "UNIT_OCCUPIED",
            "ALREADY_LISTED_FOR_RENT"), ("rent_listed",))
    simple(UNLIST_RENT_ID, "Retirar anúncio de aluguel", rent.unlist_rent_refusal, rent.unlist_rent,
           ("INVALID_PARAMS", "PLAYER_NOT_FOUND", "INVALID_PARTY", "RENT_LISTING_NOT_FOUND", "NOT_PARTY_REPRESENTATIVE", "NOT_OWNER",
            "COMPANY_NOT_FOUND", "RENT_LISTING_NOT_OPEN", "NOT_SELLER"), ("rent_unlisted",))
    simple(RENT_UNIT_ID, "Alugar unidade anunciada", rent.rent_refusal, rent.rent_unit,
           ("INVALID_PARAMS", "PLAYER_NOT_FOUND", "INVALID_PARTY", "RENT_LISTING_NOT_FOUND", "RENT_LISTING_NOT_OPEN", "TENANT_MUST_BE_PLAYER",
            "NOT_PARTY_REPRESENTATIVE", "SELF_RENT", "LANDLORD_NOT_OWNER", "LANDLORD_WITHOUT_OWNER", "INVALID_SCHEDULE", "INVALID_TERMS",
            "TOO_MANY_OCCURRENCES", "INVALID_PENALTY", "UNIT_LEASED", "UNIT_OCCUPIED", "STARTS_ON_PASSED"),
           ("rent_contract_active", "unit_leased"))


def register() -> None:
    _register_housing()
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
