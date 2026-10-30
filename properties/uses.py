"""
Uso do lote e mudança de uso (design/10 §21-22; G6, GD 2026-10-29).

  - O USO de um lote é a categoria de zoneamento para a qual ele está DESIGNADO: a categoria do próprio lote (08 §5) ou, depois de uma mudança de uso
    aprovada, a última escolhida (`UseChange`, histórico imutável). Obra e localização de empresa exigem que o uso do prédio/empresa seja o uso designado E
    que o zoneamento o permita (`geography.zoning`; 10 §22). Com o zoneamento padrão (`{c: {c}}`) o uso designado é sempre o da categoria e nada muda; com
    zoneamento misto (cenário ou lei) é a mudança de uso que liga o lote ao novo uso (10 §21: "a mudança não é realizada livremente pelo proprietário").
  - APROVAÇÃO AUTOMÁTICA quando TUDO vale (nenhuma condição é contornada pela aprovação):
      1. o zoneamento vigente (padrão + overrides de lei) permite o novo uso no lote;
      2. o lote não tem imóvel (a mudança de um imóvel construído exigiria um mapeamento de conversão que o design não define: não há demolição/reforma, 10 §23;
         decisão pendente registrada em design/10a §12), nem empresa localizada, nem obra ativa, nem anúncio ou leilão abertos;
      3. nenhuma restrição registrada (`register_use_change_restriction`: restrições do lote, regras especiais, 10 §21) recusa;
      4. nenhum aprovador político registrado (`register_use_change_approver`) nega. O aprovador político só pode NEGAR: nunca aprova o que 1-3 recusam, e sem aprovador
         registrado o pedido é aprovado. As regras de votação e as competências NÃO existem ainda (06/11): o gancho só define a assinatura.
  - CUSTO: zero e configurável (`params.USE_CHANGE_FEE_CENTS`); o `24` não tem natureza monetária para ele, então qualquer valor > 0 é recusado
    (`USE_CHANGE_FEE_UNDEFINED`) em vez de inventar uma natureza ou tirar dinheiro sem rota.
  - Só o dono do lote (jogador, ou o Dono pela empresa) pede a mudança. O governo não é dono privado (lotes do governo vão a leilão).

PROTOCOLO de trava: jogador → empresa → lote.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from django.db import transaction

from core import clock as game_clock
from geography import zoning
from geography.constants import Category
from geography.models import Lot
from players.models import Player
from players.services import ActionResult

from . import params
from .common import authority, lock, parse_party, positive, refuse
from .constants import AuctionStatus, ListingStatus, OwnerKind, SiteStatus
from .models import Auction, Building, CompanyLocation, ConstructionSite, Listing, UseChange
from .titles import owner_of_lot

KEYS = frozenset({"lot", "owner", "use"})

Restriction = Callable[[Lot, Category, Category, Any], Optional[ActionResult]]
Approver = Callable[[Lot, Category, Category, int], Optional[ActionResult]]
_restrictions: Dict[str, Restriction] = {}
_approvers: Dict[str, Approver] = {}


def register_use_change_restriction(name: str, fn: Restriction) -> None:
    """Restrições do lote/regras especiais (10 §21): `fn(lot, old_use, new_use, owner)` → recusa ou None. Só LÊ. Pode recusar; nunca aprova por cima das condições."""
    if name in _restrictions:
        raise ValueError(f"Restrição de mudança de uso duplicada: {name}")
    _restrictions[name] = fn


def unregister_use_change_restriction(name: str) -> None:       # para testes
    _restrictions.pop(name, None)


def register_use_change_approver(name: str, fn: Approver) -> None:
    """Ponto de integração da aprovação POLÍTICA futura (G6): `fn(lot, old_use, new_use, requester_id)` → recusa ou None. Só pode NEGAR. Sem regra de votação ou competência."""
    if name in _approvers:
        raise ValueError(f"Aprovador de mudança de uso duplicado: {name}")
    _approvers[name] = fn


def unregister_use_change_approver(name: str) -> None:          # para testes
    _approvers.pop(name, None)


def use_of_lot(lot: Lot) -> Category:
    """O uso para o qual o lote está designado: o da última mudança aprovada, ou a categoria do lote."""
    last = UseChange.objects.filter(lot_id=lot.pk).order_by("-sequence").values_list("new_use", flat=True).first()
    return Category(last) if last is not None else Category(lot.category)


def use_refusal(lot: Lot, use: Category) -> Optional[ActionResult]:
    """O lote pode receber obra/empresa do uso `use` agora? Zoneamento permite E o uso está designado ao lote. Só LÊ."""
    if not zoning.is_use_allowed(lot, use):
        return refuse("LOT_USE_NOT_ALLOWED", lot=lot.pk, category=lot.category, use=use.value)
    designated = use_of_lot(lot)
    if designated is not use:
        return refuse("LOT_USE_NOT_DESIGNATED", lot=lot.pk, designated=designated.value, use=use.value,
                      why="peça a mudança de uso do lote (aprovação automática quando o zoneamento permite)")
    return None


def change_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    """Recusas que só LEEM (a execução usa as mesmas). O pedido é do dono do lote; o `use` é uma categoria de zoneamento."""
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    if not isinstance(target, dict) or set(target) != KEYS:
        return refuse("INVALID_PARAMS", expected=sorted(KEYS))
    if not positive(target["lot"]):
        return refuse("INVALID_PARAMS", lot=repr(target["lot"])[:30])
    owner = parse_party(target["owner"])
    if isinstance(owner, ActionResult):
        return owner
    try:
        new_use = Category(target["use"])
    except (ValueError, TypeError):
        return refuse("INVALID_USE", use=repr(target["use"])[:30], allowed=[c.value for c in Category])
    if params.USE_CHANGE_FEE_CENTS != 0:
        return refuse("USE_CHANGE_FEE_UNDEFINED", fee_cents=params.USE_CHANGE_FEE_CENTS,
                      why="o custo da mudança de uso não tem natureza monetária definida no 24")
    kind, entity_id = owner
    refusal = authority(actor_id, kind, entity_id)
    if refusal is not None:
        return refusal
    lot = Lot.objects.filter(pk=target["lot"]).first()
    if lot is None:
        return refuse("LOT_NOT_FOUND", lot=target["lot"])
    if owner_of_lot(lot.pk) != (kind, entity_id):
        return refuse("NOT_LOT_OWNER", lot=lot.pk)
    old_use = use_of_lot(lot)
    if new_use is old_use:
        return refuse("USE_UNCHANGED", lot=lot.pk, use=old_use.value)
    decision = zoning.decide(lot, new_use)
    if not decision.allowed:
        return refuse("ZONING_DOES_NOT_ALLOW_USE", lot=lot.pk, category=lot.category, use=new_use.value, base_allowed=decision.base_allowed,
                      overridden_by=[list(o) for o in decision.overridden_by])
    if Building.objects.filter(lot=lot).exists():
        return refuse("USE_CHANGE_BUILDING_PRESENT", lot=lot.pk, why="mudar o uso de um imóvel construído exige conversão (sem demolição/reforma no Bot Test; design/10a §12)")
    if CompanyLocation.objects.filter(lot=lot).exists():
        return refuse("LOT_HAS_COMPANY", lot=lot.pk)
    if (ConstructionSite.objects.filter(lot=lot, status=SiteStatus.ACTIVE.value).exists()
            or Listing.objects.filter(lot=lot, status=ListingStatus.OPEN.value).exists()
            or Auction.objects.filter(lot=lot, status=AuctionStatus.OPEN.value).exists()):
        return refuse("LOT_RESERVED", lot=lot.pk)
    for name in sorted(_restrictions):
        res = _restrictions[name](lot, old_use, new_use, owner)
        if res is not None:
            return res
    for name in sorted(_approvers):
        res = _approvers[name](lot, old_use, new_use, actor_id)
        if res is not None:
            return res
    return None


def change_use(actor_id: Any, target: Any) -> ActionResult:
    """
    O dono pede a mudança de uso do lote; aprovada automaticamente quando as condições valem (módulo). Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS, INVALID_PARTY, INVALID_USE,
    USE_CHANGE_FEE_UNDEFINED, NOT_PARTY_REPRESENTATIVE, NOT_OWNER, COMPANY_NOT_FOUND, LOT_NOT_FOUND, NOT_LOT_OWNER, USE_UNCHANGED, ZONING_DOES_NOT_ALLOW_USE,
    USE_CHANGE_BUILDING_PRESENT, LOT_HAS_COMPANY, LOT_RESERVED e as das restrições/aprovadores registrados.
    """
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    owner = parse_party(target.get("owner")) if isinstance(target, dict) else None
    lot_id = target.get("lot") if isinstance(target, dict) else None
    with transaction.atomic():
        lock(actor_id, [owner] if isinstance(owner, tuple) else [])
        if positive(lot_id):
            list(Lot.objects.select_for_update().filter(pk=lot_id))
        refusal = change_refusal(actor_id, target)
        if refusal is not None:
            return refusal
        lot = Lot.objects.get(pk=lot_id)
        kind, entity_id = owner
        old_use, new_use = use_of_lot(lot), Category(target["use"])
        decision = zoning.decide(lot, new_use)
        now = game_clock.now()
        sequence = UseChange.objects.filter(lot=lot).count() + 1
        row = UseChange.objects.create(
            lot=lot, sequence=sequence, old_use=old_use.value, new_use=new_use.value, requested_by=actor_id, owner_kind=kind.value, owner_id=entity_id,
            fee_cents=0, at=now,
            decision={"rule": "automatic_when_zoning_allows", "zoning": {"allowed": decision.allowed, "base_allowed": decision.base_allowed,
                                                                         "overridden_by": [list(o) for o in decision.overridden_by]},
                      "restrictions_checked": sorted(_restrictions), "approvers_consulted": sorted(_approvers), "fee_cents": 0})
        return ActionResult(True, "OK", {"use_change": row.pk, "lot": lot.pk, "old_use": old_use.value, "new_use": new_use.value, "sequence": sequence,
                                         "fee_cents": 0, "decision": row.decision})


def use_view(lot_id: int) -> Optional[Dict[str, Any]]:
    """Uso designado, categoria, o que o zoneamento permite e o histórico de mudanças (20)."""
    lot = Lot.objects.filter(pk=lot_id).first()
    if lot is None:
        return None
    return {"lot": lot.pk, "category": lot.category, "designated_use": use_of_lot(lot).value,
            "zoning_allows": sorted(c.value for c in Category if zoning.is_use_allowed(lot, c)),
            "history": [{"sequence": u.sequence, "old_use": u.old_use, "new_use": u.new_use, "at": u.at, "by": u.requested_by, "fee_cents": u.fee_cents}
                        for u in UseChange.objects.filter(lot=lot).order_by("sequence")]}
