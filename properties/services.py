"""
Imóveis (design/10): propriedade de lotes, leilão público (10 §4), venda entre proprietários (10 §8) e a obra com lote (10 §5, §28).

Quem age por uma empresa é o seu Dono (02 §16); por si, o próprio jogador. Dinheiro só se move por lançamentos do registro
monetário: arrematação = `AUCTION_PAYMENT` do arrematante ao Município do lote (24 Q2); venda de imóvel = `SALE` entre as partes,
SEM imposto (24 §24.7). Nenhum dinheiro é criado ou apagado aqui.

PROTOCOLO de trava: jogador(es) (crescente) → empresa(s) (crescente) → lote → leilão/anúncio → registro monetário.
Idempotência: chaves `auction:{id}:payment` e `listing:{id}:sale`; o encerramento do leilão só age sobre leilão aberto e vencido.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from django.db import transaction
from django.db.models import Max

from companies import construction
from companies import services as company_services
from companies.models import Company
from core import clock as game_clock
from core import ticks
from core.timeline import TickKind
from geography.constants import Category, Occupation
from geography.models import Lot
from geography import zoning
from ledger import services as ledger
from ledger.constants import AccountKind, Nature
from market.constants import PartyKind as MarketPartyKind
from market.recording import party_account_id
from players.models import Player
from players.services import ActionResult

from . import housing, params, rent, sites
from players import qol
from .constants import AuctionStatus, ListingStatus, OwnerKind, SiteStatus, TitleReason
from .models import Auction, AuctionBid, Building, CompanyLocation, ConstructionSite, Listing, LotTitle, TitleEvent

from . import common
from .common import (PRIVATE_KINDS, acting_player, is_int as _is_int, lock as _lock, parse_party, positive as _positive,
                     refuse as _refuse)
from .common import account as _account
from .common import authority as _authority
from .titles import owner_of_lot

TICK_NAME = "properties_close_auctions"
HOOK_NAME = "properties"
BID_KEYS = frozenset({"auction", "bidder", "amount"})
LIST_KEYS = frozenset({"lot", "owner", "price"})
LISTING_KEYS = frozenset({"listing", "party"})

Eligibility = Callable[[OwnerKind, int, Lot], Optional[ActionResult]]
_eligibility: Dict[str, Eligibility] = {}


def register_eligibility(name: str, fn: Eligibility) -> None:
    """Leis futuras (10 §4.1 'requisitos legais') podem barrar quem dá lance/compra: `fn(kind, id, lot)` → recusa ou None. Só LÊ."""
    if name in _eligibility:
        raise ValueError(f"Regra de elegibilidade duplicada: {name}")
    _eligibility[name] = fn


def unregister_eligibility(name: str) -> None:       # para testes
    _eligibility.pop(name, None)


def _eligibility_refusal(kind: OwnerKind, entity_id: int, lot: Lot) -> Optional[ActionResult]:
    for name in sorted(_eligibility):
        res = _eligibility[name](kind, entity_id, lot)
        if res is not None:
            return res
    return None


def _record_title(lot: Lot, to_kind: OwnerKind, to_id: int, reason: TitleReason, price: int, ledger_key: str, ref_kind: str,
                  ref_id: Any, at: int) -> TitleEvent:
    """Transfere o título e registra a aquisição. O lote deve estar travado por quem chama."""
    from_kind, from_id = owner_of_lot(lot.pk)
    seq = (TitleEvent.objects.filter(lot=lot).aggregate(m=Max("sequence"))["m"] or 0) + 1
    event = TitleEvent.objects.create(lot=lot, sequence=seq, reason=reason.value, from_kind=from_kind.value, from_id=from_id,
                                      to_kind=to_kind.value, to_id=to_id, price_cents=price, ledger_key=ledger_key,
                                      reference_kind=ref_kind, reference_id=str(ref_id), at=at)
    title = LotTitle.objects.select_for_update().filter(lot=lot).first()
    if title is None:
        LotTitle.objects.create(lot=lot, owner_kind=to_kind.value, owner_id=to_id, since=at)
    else:
        title.owner_kind, title.owner_id, title.since = to_kind.value, to_id, at
        title.save(update_fields=["owner_kind", "owner_id", "since"])
    return event


def _lot_state_refusal(lot: Lot) -> Optional[ActionResult]:
    """Impedimentos de um lote para mudar de mãos / ir a leilão."""
    if ConstructionSite.objects.filter(lot=lot, status=SiteStatus.ACTIVE.value).exists():
        return _refuse("LOT_HAS_ACTIVE_SITE", lot=lot.pk)
    return None


# --- leilão (10 §4) ------------------------------------------------------------------------------------------------------

def open_auction_refusal(lot_id: Any, min_bid_cents: Any, duration_seconds: Any = None) -> Optional[ActionResult]:
    if not _positive(lot_id) or not _positive(min_bid_cents):
        return _refuse("INVALID_PARAMS", lot=repr(lot_id)[:30], min_bid_cents=repr(min_bid_cents)[:30])
    if duration_seconds is not None and not _positive(duration_seconds):
        return _refuse("INVALID_PARAMS", duration_seconds=repr(duration_seconds)[:30])
    lot = Lot.objects.filter(pk=lot_id).first()
    if lot is None:
        return _refuse("LOT_NOT_FOUND", lot=lot_id)
    if owner_of_lot(lot.pk)[0] is not OwnerKind.GOVERNMENT:
        return _refuse("LOT_NOT_GOVERNMENT_OWNED", lot=lot_id)
    if Category(lot.category) not in params.AUCTIONABLE_CATEGORIES:
        return _refuse("LOT_NOT_AUCTIONABLE", category=lot.category, allowed=sorted(c.value for c in params.AUCTIONABLE_CATEGORIES))
    if lot.occupation != Occupation.EMPTY.value:
        return _refuse("LOT_OCCUPIED", lot=lot_id)
    if Auction.objects.filter(lot=lot, status=AuctionStatus.OPEN.value).exists():
        return _refuse("AUCTION_OPEN", lot=lot_id)
    return None


def open_auction(lot_id: Any, min_bid_cents: Any, *, duration_seconds: Optional[int] = None, at: Optional[int] = None) -> ActionResult:
    """
    Abre o leilão público de um lote do governo (ferramenta do sistema/Dev: quem decide abrir leilões é lacuna registrada em
    `design/10a`). Recusas: INVALID_PARAMS, LOT_NOT_FOUND, LOT_NOT_GOVERNMENT_OWNED, LOT_NOT_AUCTIONABLE, LOT_OCCUPIED, AUCTION_OPEN.
    """
    with transaction.atomic():
        if _positive(lot_id):
            Lot.objects.select_for_update().filter(pk=lot_id).first()
        refusal = open_auction_refusal(lot_id, min_bid_cents, duration_seconds)
        if refusal is not None:
            return refusal
        now = game_clock.now() if at is None else at
        duration = params.AUCTION_DURATION_SECONDS if duration_seconds is None else duration_seconds
        auction = Auction.objects.create(lot_id=lot_id, min_bid_cents=min_bid_cents, starts_at=now, base_ends_at=now + duration,
                                         ends_at=now + duration)
        return ActionResult(True, "OK", {"auction": auction.pk, "lot": lot_id, "min_bid_cents": min_bid_cents, "ends_at": auction.ends_at})


def bid_refusal(actor_id: Any, auction_id: Any, bidder: Any, amount: Any, now: Optional[int] = None) -> Optional[ActionResult]:
    """Recusas de um lance que só LEEM (a execução usa a mesma, de novo, com tudo travado)."""
    if not _positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    if not _positive(auction_id) or not _positive(amount):
        return _refuse("INVALID_PARAMS", auction=repr(auction_id)[:30], amount=repr(amount)[:30])
    party = parse_party(bidder)
    if isinstance(party, ActionResult):
        return party
    kind, entity_id = party
    auction = Auction.objects.filter(pk=auction_id).first()
    if auction is None:
        return _refuse("AUCTION_NOT_FOUND", auction=auction_id)
    authority = _authority(actor_id, kind, entity_id)
    if authority is not None:
        return authority
    now = game_clock.now() if now is None else now
    if auction.status != AuctionStatus.OPEN.value:
        return _refuse("AUCTION_NOT_OPEN", status=auction.status)
    if now >= auction.ends_at:
        return _refuse("AUCTION_ENDED", ends_at=auction.ends_at)
    eligibility = _eligibility_refusal(kind, entity_id, auction.lot)
    if eligibility is not None:
        return eligibility
    if auction.top_bid_cents is not None and (auction.top_bidder_kind, auction.top_bidder_id) == (kind.value, entity_id):
        return _refuse("ALREADY_TOP_BIDDER", top_bid_cents=auction.top_bid_cents)
    needed = auction.min_bid_cents if auction.top_bid_cents is None else auction.top_bid_cents + params.MIN_BID_INCREMENT_CENTS
    if amount < needed:
        return _refuse("BID_TOO_LOW", amount=amount, needed=needed)
    account = _account(kind, entity_id)
    available = ledger.available_of(account)
    if available < amount:
        return _refuse("INSUFFICIENT_FUNDS", amount=amount, available=available)
    return None


def bid(actor_id: Any, auction_id: Any, bidder: Any, amount: Any) -> ActionResult:
    """
    Dá um lance (10 §4.1). Sem reserva de fundos: o saldo é conferido agora e de novo no encerramento (10 §4.4). Um lance nos
    últimos `EXTENSION_WINDOW_SECONDS` estende o encerramento (10 §4.3). Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS, INVALID_PARTY,
    AUCTION_NOT_FOUND, NOT_PARTY_REPRESENTATIVE, NOT_OWNER, COMPANY_NOT_FOUND, AUCTION_NOT_OPEN, AUCTION_ENDED, ALREADY_TOP_BIDDER,
    BID_TOO_LOW, INSUFFICIENT_FUNDS e as de elegibilidade.
    """
    if not _positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    party = parse_party(bidder)
    parties = [] if isinstance(party, ActionResult) else [party]
    with transaction.atomic():
        _lock(actor_id, parties)
        if _positive(auction_id):
            Auction.objects.select_for_update().filter(pk=auction_id).first()
        now = game_clock.now()                                  # DEPOIS da trava: o relógio é o da ordem real dos lances
        refusal = bid_refusal(actor_id, auction_id, bidder, amount, now)
        if refusal is not None:
            return refusal
        kind, entity_id = party
        auction = Auction.objects.get(pk=auction_id)
        seq = auction.bids + 1
        extended = auction.ends_at - now <= params.EXTENSION_WINDOW_SECONDS
        AuctionBid.objects.create(auction=auction, sequence=seq, bidder_kind=kind.value, bidder_id=entity_id, amount_cents=amount,
                                  at=now, extended=extended, acted_by=actor_id)
        auction.top_bid_cents, auction.top_bidder_kind, auction.top_bidder_id, auction.bids = amount, kind.value, entity_id, seq
        if extended:
            auction.ends_at += params.EXTENSION_SECONDS
            auction.extensions += 1
        auction.save(update_fields=["top_bid_cents", "top_bidder_kind", "top_bidder_id", "bids", "ends_at", "extensions"])
        return ActionResult(True, "OK", {"auction": auction.pk, "lot": auction.lot_id, "bid": seq, "amount": amount,
                                         "extended": extended, "ends_at": auction.ends_at})


def close_auction(auction_id: int, now: Optional[int] = None) -> ActionResult:
    """
    Encerra UM leilão vencido (idempotente: leilão que não está aberto, ou ainda não venceu, não muda). Sem lances → UNSOLD.
    O arrematante paga ao Município do lote (`AUCTION_PAYMENT`) e recebe o título; se não puder pagar, a arrematação é
    INVALIDADA (10 §4.4: o design diz que o vencedor deve ter fundos; o que acontece se não tiver é lacuna registrada) e o lote
    segue do governo — nenhum dinheiro se move.
    """
    now = game_clock.now() if now is None else now
    for _ in range(5):
        with transaction.atomic():
            seen = Auction.objects.filter(pk=auction_id).first()
            if seen is None:
                return _refuse("AUCTION_NOT_FOUND", auction=auction_id)
            if seen.status != AuctionStatus.OPEN.value or seen.ends_at > now:
                return ActionResult(True, "OK", {"auction": auction_id, "closed": False, "status": seen.status})
            parties = ([] if seen.top_bidder_id is None else [(OwnerKind(seen.top_bidder_kind), seen.top_bidder_id)])
            if parties:
                pk = parties[0][1]
                if parties[0][0] is OwnerKind.PLAYER:
                    list(Player.objects.select_for_update().filter(pk=pk))
                else:
                    list(Company.objects.select_for_update().filter(pk=pk))
            lot = Lot.objects.select_for_update().select_related("neighborhood").get(pk=seen.lot_id)
            auction = Auction.objects.select_for_update().get(pk=auction_id)
            if (auction.top_bidder_kind, auction.top_bidder_id) != (seen.top_bidder_kind, seen.top_bidder_id):
                continue                                          # um lance entrou entre a leitura e a trava: recomeça
            if auction.status != AuctionStatus.OPEN.value or auction.ends_at > now:
                return ActionResult(True, "OK", {"auction": auction_id, "closed": False, "status": auction.status})
            auction.closed_at = now
            if auction.top_bid_cents is None:
                auction.status = AuctionStatus.UNSOLD.value
                auction.save(update_fields=["status", "closed_at"])
                return ActionResult(True, "OK", {"auction": auction_id, "closed": True, "status": auction.status})
            kind, winner = OwnerKind(auction.top_bidder_kind), auction.top_bidder_id
            key = f"auction:{auction.pk}:payment"
            paid = ledger.transfer(_account(kind, winner), ledger.get_or_create_account(AccountKind.MUNICIPALITY, lot.neighborhood.city_id).pk,
                                   auction.top_bid_cents, Nature.AUCTION_PAYMENT, key=key, reference_kind="auction",
                                   reference_id=auction.pk, at=now, category="auction", operation="winning_bid",
                                   explained={"auction": auction.pk, "lot": lot.pk, "bids": auction.bids,
                                              "winning_bid_cents": auction.top_bid_cents})
            if not paid.ok:
                auction.status, auction.result_note = AuctionStatus.INVALIDATED.value, paid.code[:80]
                auction.save(update_fields=["status", "closed_at", "result_note"])
                return ActionResult(True, "OK", {"auction": auction_id, "closed": True, "status": auction.status, "reason": paid.code})
            _record_title(lot, kind, winner, TitleReason.AUCTION, auction.top_bid_cents, key, "auction", auction.pk, now)
            auction.status, auction.ledger_key = AuctionStatus.SOLD.value, key
            auction.save(update_fields=["status", "closed_at", "ledger_key"])
            return ActionResult(True, "OK", {"auction": auction_id, "closed": True, "status": auction.status, "winner": [kind.value, winner],
                                             "price_cents": auction.top_bid_cents})
    return _refuse("AUCTION_BUSY", auction=auction_id)


def close_due(now: Optional[int] = None) -> int:
    """Encerra todos os leilões abertos vencidos até `now` (ordem de id). Devolve quantos mudaram de estado."""
    now = game_clock.now() if now is None else now
    closed = 0
    for pk in list(Auction.objects.filter(status=AuctionStatus.OPEN.value, ends_at__lte=now).order_by("id").values_list("pk", flat=True)):
        res = close_auction(pk, now)
        closed += 1 if res.ok and res.detail.get("closed") else 0
    return closed


# --- venda entre proprietários (10 §8) --------------------------------------------------------------------------------------

def list_refusal(actor_id: Any, lot_id: Any, owner: Any, price_cents: Any) -> Optional[ActionResult]:
    if not _positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    if not _positive(lot_id) or not _positive(price_cents):
        return _refuse("INVALID_PARAMS", lot=repr(lot_id)[:30], price=repr(price_cents)[:30])
    party = parse_party(owner)
    if isinstance(party, ActionResult):
        return party
    kind, entity_id = party
    lot = Lot.objects.filter(pk=lot_id).first()
    if lot is None:
        return _refuse("LOT_NOT_FOUND", lot=lot_id)
    authority = _authority(actor_id, kind, entity_id)
    if authority is not None:
        return authority
    if owner_of_lot(lot.pk) != (kind, entity_id):
        return _refuse("NOT_LOT_OWNER", lot=lot_id)
    state = _lot_state_refusal(lot)
    if state is not None:
        return state
    if Listing.objects.filter(lot=lot, status=ListingStatus.OPEN.value).exists():
        return _refuse("ALREADY_LISTED", lot=lot_id)
    return None


def list_property(actor_id: Any, lot_id: Any, owner: Any, price_cents: Any) -> ActionResult:
    """O proprietário anuncia o imóvel pelo preço que escolher (10 §8). Recusas: ver `list_refusal`."""
    if not _positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    party = parse_party(owner)
    with transaction.atomic():
        _lock(actor_id, [] if isinstance(party, ActionResult) else [party])
        if _positive(lot_id):
            Lot.objects.select_for_update().filter(pk=lot_id).first()
        refusal = list_refusal(actor_id, lot_id, owner, price_cents)
        if refusal is not None:
            return refusal
        kind, entity_id = party
        listing = Listing.objects.create(lot_id=lot_id, seller_kind=kind.value, seller_id=entity_id, price_cents=price_cents,
                                         listed_at=game_clock.now())
        return ActionResult(True, "OK", {"listing": listing.pk, "lot": lot_id, "price_cents": price_cents})


def _listing_party_refusal(actor_id: Any, listing_id: Any, party_value: Any, *, seller: bool):
    if not _positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    if not _positive(listing_id):
        return _refuse("INVALID_PARAMS", listing=repr(listing_id)[:30])
    party = parse_party(party_value)
    if isinstance(party, ActionResult):
        return party
    listing = Listing.objects.filter(pk=listing_id).first()
    if listing is None:
        return _refuse("LISTING_NOT_FOUND", listing=listing_id)
    authority = _authority(actor_id, *party)
    if authority is not None:
        return authority
    if listing.status != ListingStatus.OPEN.value:
        return _refuse("LISTING_NOT_OPEN", status=listing.status)
    is_seller = (listing.seller_kind, listing.seller_id) == (party[0].value, party[1])
    if seller and not is_seller:
        return _refuse("NOT_SELLER", listing=listing_id)
    if not seller and is_seller:
        return _refuse("SELF_PURCHASE", listing=listing_id)
    return listing


def unlist_refusal(actor_id: Any, listing_id: Any, party: Any) -> Optional[ActionResult]:
    res = _listing_party_refusal(actor_id, listing_id, party, seller=True)
    return res if isinstance(res, ActionResult) else None


def unlist_property(actor_id: Any, listing_id: Any, party: Any) -> ActionResult:
    """O vendedor retira o anúncio. Recusas: ver `_listing_party_refusal` + NOT_SELLER."""
    parsed = parse_party(party)
    if not _positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    with transaction.atomic():
        _lock(actor_id, [] if isinstance(parsed, ActionResult) else [parsed])
        if _positive(listing_id):
            Listing.objects.select_for_update().filter(pk=listing_id).first()
        refusal = unlist_refusal(actor_id, listing_id, party)
        if refusal is not None:
            return refusal
        Listing.objects.filter(pk=listing_id).update(status=ListingStatus.CANCELLED.value, closed_at=game_clock.now())
        return ActionResult(True, "OK", {"listing": listing_id, "status": ListingStatus.CANCELLED.value})


def buy_refusal(actor_id: Any, listing_id: Any, buyer: Any) -> Optional[ActionResult]:
    res = _listing_party_refusal(actor_id, listing_id, buyer, seller=False)
    if isinstance(res, ActionResult):
        return res
    listing = res
    kind, entity_id = parse_party(buyer)
    lot = Lot.objects.get(pk=listing.lot_id)
    if owner_of_lot(lot.pk) != (OwnerKind(listing.seller_kind), listing.seller_id):
        return _refuse("LISTING_STALE", lot=lot.pk)
    state = _lot_state_refusal(lot)
    if state is not None:
        return state
    eligibility = _eligibility_refusal(kind, entity_id, lot)
    if eligibility is not None:
        return eligibility
    available = ledger.available_of(_account(kind, entity_id))
    if available < listing.price_cents:
        return _refuse("INSUFFICIENT_FUNDS", price=listing.price_cents, available=available)
    return None


def buy_property(actor_id: Any, listing_id: Any, buyer: Any) -> ActionResult:
    """
    Compra o imóvel anunciado pelo preço do dono (10 §8): `SALE` do comprador ao vendedor (sem imposto, 24 §24.7) e o título
    muda de mãos no mesmo ato. Recusas: ver `_listing_party_refusal` + SELF_PURCHASE, LISTING_STALE, LOT_HAS_ACTIVE_SITE,
    INSUFFICIENT_FUNDS e as de elegibilidade.
    """
    if not _positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    parsed = parse_party(buyer)
    with transaction.atomic():
        seller_parties: List[Tuple[OwnerKind, int]] = []
        peek = Listing.objects.filter(pk=listing_id).first() if _positive(listing_id) else None
        if peek is not None:
            seller_parties.append((OwnerKind(peek.seller_kind), peek.seller_id))
        _lock(actor_id, ([] if isinstance(parsed, ActionResult) else [parsed]) + seller_parties)
        if peek is not None:
            Lot.objects.select_for_update().filter(pk=peek.lot_id).first()
            Listing.objects.select_for_update().filter(pk=listing_id).first()
        refusal = buy_refusal(actor_id, listing_id, buyer)
        if refusal is not None:
            return refusal
        kind, entity_id = parsed
        listing = Listing.objects.get(pk=listing_id)
        lot = Lot.objects.get(pk=listing.lot_id)
        now = game_clock.now()
        key = f"listing:{listing.pk}:sale"
        paid = ledger.transfer(_account(kind, entity_id), _account(OwnerKind(listing.seller_kind), listing.seller_id), listing.price_cents,
                               Nature.SALE, key=key, reference_kind="listing", reference_id=listing.pk, at=now, category="property",
                               operation="sale", explained={"listing": listing.pk, "lot": lot.pk, "price_cents": listing.price_cents})
        if not paid.ok:
            return paid
        _record_title(lot, kind, entity_id, TitleReason.SALE, listing.price_cents, key, "listing", listing.pk, now)
        carried = rent.on_property_sold(lot, (kind, entity_id), "property_sale", f"listing:{listing.pk}", now)    # 10 §13
        dropped_company = sites.drop_location_of_lot(lot.pk)                                                      # a empresa deixa o lote vendido
        if dropped_company is not None:
            carried = {**carried, "company_location_dropped": dropped_company}
        listing.status, listing.closed_at, listing.buyer_kind, listing.buyer_id, listing.ledger_key = (
            ListingStatus.SOLD.value, now, kind.value, entity_id, key)
        listing.save(update_fields=["status", "closed_at", "buyer_kind", "buyer_id", "ledger_key"])
        return ActionResult(True, "OK", {"listing": listing.pk, "lot": lot.pk, "price_cents": listing.price_cents,
                                         "buyer": [kind.value, entity_id], "seller": [listing.seller_kind, listing.seller_id], **carried})


# --- obra com lote (10 §5, §28) ----------------------------------------------------------------------------------------------

def _start_validator(player_id: int, company_id: int, project_key: str, lot_id: Any) -> Optional[ActionResult]:
    """A Construtora constrói no lote QUE É DELA (10 §28), vazio, onde o zoneamento permite moradia (10 §5-6, 08 §7)."""
    if not _positive(lot_id):
        return _refuse("INVALID_PARAMS", lot=repr(lot_id)[:30])
    lot = Lot.objects.filter(pk=lot_id).first()
    if lot is None:
        return _refuse("LOT_NOT_FOUND", lot=lot_id)
    if project_key not in params.BUILDING_TYPES:
        return _refuse("UNKNOWN_PROJECT", project=str(project_key)[:60], allowed=sorted(params.BUILDING_TYPES))
    if owner_of_lot(lot.pk) != (OwnerKind.COMPANY, company_id):
        return _refuse("LOT_NOT_OWNED_BY_BUILDER", lot=lot_id, company=company_id)
    if lot.occupation != Occupation.EMPTY.value or Building.objects.filter(lot=lot).exists():
        return _refuse("LOT_OCCUPIED", lot=lot_id)
    if (ConstructionSite.objects.filter(lot=lot, status=SiteStatus.ACTIVE.value).exists()
            or Listing.objects.filter(lot=lot, status=ListingStatus.OPEN.value).exists()):
        return _refuse("LOT_RESERVED", lot=lot_id)
    if not zoning.is_use_allowed(lot, Category.RESIDENTIAL):
        return _refuse("LOT_USE_NOT_ALLOWED", lot=lot_id, category=lot.category, use=Category.RESIDENTIAL.value)
    return None


def _start_hook(job, lot_id: Any) -> None:
    Lot.objects.select_for_update().filter(pk=lot_id).first()
    ConstructionSite.objects.create(job_id=job.pk, lot_id=lot_id, company_id=job.company_id, project=job.project, created_at=job.started_at)


def _completion_hook(job) -> None:
    """Obra concluída → o imóvel nasce no lote (mesma transação do Trabalho que concluiu). Obra sem lote não gera imóvel."""
    site = ConstructionSite.objects.select_for_update().filter(job_id=job.pk).first()
    if site is None:
        return
    Lot.objects.select_for_update().filter(pk=site.lot_id).first()
    kind = params.BUILDING_TYPES[job.project]
    building = Building.objects.create(lot_id=site.lot_id, kind=kind.key, units=kind.units, qol_bonus=kind.qol_bonus,
                                       builder_company_id=job.company_id, job_id=job.pk, completed_at=job.completed_at)
    housing.create_units(building)                                   # 10 §6.1: as unidades independentes do imóvel
    Lot.objects.filter(pk=site.lot_id).update(occupation=Occupation.OCCUPIED.value)
    site.status, site.completed_at = SiteStatus.COMPLETED.value, job.completed_at
    site.save(update_fields=["status", "completed_at"])


def _close_tick(tick, ctx) -> None:
    close_due(tick.at)


def register() -> None:
    rent.register()                                                  # tipo `rent` do motor de contratos (10 §9-13)
    sites.register()                                                 # terreno da Matriz (02 §2.1; 10 §29)
    qol.register_qol_base_provider(housing.PROVIDER_NAME, housing.qol_bonus)    # 10 §7: o imóvel da residência ativa soma à QoL Base
    construction.register_start_validator(HOOK_NAME, _start_validator)
    construction.register_start_hook(HOOK_NAME, _start_hook)
    construction.register_completion_hook(HOOK_NAME, _completion_hook)
    ticks.register(ticks.WORLD, TickKind.TEN_MINUTES, TICK_NAME, priority=50)(_close_tick)


# --- leitura ----------------------------------------------------------------------------------------------------------------

def auction_view(auction_id: int) -> Optional[Dict[str, Any]]:
    a = Auction.objects.filter(pk=auction_id).first()
    if a is None:
        return None
    return {"id": a.pk, "lot": a.lot_id, "status": a.status, "min_bid_cents": a.min_bid_cents, "starts_at": a.starts_at,
            "base_ends_at": a.base_ends_at, "ends_at": a.ends_at, "extensions": a.extensions, "top_bid_cents": a.top_bid_cents,
            "top_bidder": None if a.top_bidder_id is None else [a.top_bidder_kind, a.top_bidder_id], "bids": a.bids,
            "closed_at": a.closed_at, "result_note": a.result_note,
            "history": [{"sequence": b.sequence, "bidder": [b.bidder_kind, b.bidder_id], "amount_cents": b.amount_cents, "at": b.at,
                         "extended": b.extended} for b in a.bid_rows.order_by("sequence")]}


def lot_view(lot_id: int) -> Optional[Dict[str, Any]]:
    """Retrato da propriedade de um lote (10 §3, §31): dono, imóvel, obra, leilão/anúncio abertos e histórico de aquisição."""
    lot = Lot.objects.filter(pk=lot_id).first()
    if lot is None:
        return None
    kind, owner = owner_of_lot(lot.pk)
    building = Building.objects.filter(lot=lot).first()
    auction = Auction.objects.filter(lot=lot, status=AuctionStatus.OPEN.value).first()
    listing = Listing.objects.filter(lot=lot, status=ListingStatus.OPEN.value).first()
    site = ConstructionSite.objects.filter(lot=lot, status=SiteStatus.ACTIVE.value).first()
    located = CompanyLocation.objects.filter(lot=lot).values_list("company_id", flat=True).first()
    return {"lot": lot.pk, "category": lot.category, "occupation": lot.occupation, "owner": [kind.value, owner], "company": located,
            "building": None if building is None else {"kind": building.kind, "units": building.units, "qol_bonus": str(building.qol_bonus)},
            "units": [] if building is None else list(building.unit_rows.order_by("index").values_list("pk", flat=True)),
            "open_auction": None if auction is None else auction.pk,
            "open_listing": None if listing is None else {"id": listing.pk, "price_cents": listing.price_cents},
            "active_site": None if site is None else {"job": site.job_id, "project": site.project},
            "history": [{"sequence": e.sequence, "reason": e.reason, "from": [e.from_kind, e.from_id], "to": [e.to_kind, e.to_id],
                         "price_cents": e.price_cents, "at": e.at} for e in lot.title_events.order_by("sequence")]}
