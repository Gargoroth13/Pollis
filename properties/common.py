"""Funções comuns dos Imóveis: recusa, validação de partes, autoridade (Dono age pela empresa), contas e travas. Sem regra de negócio."""
from __future__ import annotations

from typing import Any, List, Optional, Tuple, Union

from companies import services as company_services
from companies.models import Company
from market.constants import PartyKind as MarketPartyKind
from market.recording import party_account_id
from players.models import Player
from players.services import ActionResult

from .constants import OwnerKind

_INT64 = 2 ** 63
PRIVATE_KINDS = (OwnerKind.PLAYER, OwnerKind.COMPANY)


def refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and -_INT64 <= v < _INT64


def positive(v: Any) -> bool:
    return is_int(v) and v > 0


def parse_party(value: Any) -> Union[Tuple[OwnerKind, int], ActionResult]:
    if not isinstance(value, dict) or set(value) != {"kind", "id"} or not positive(value["id"]):
        return refuse("INVALID_PARTY", party=repr(value)[:60])
    try:
        kind = OwnerKind(value["kind"])
    except ValueError:
        return refuse("INVALID_PARTY", party=repr(value)[:60])
    if kind not in PRIVATE_KINDS:
        return refuse("INVALID_PARTY", party=repr(value)[:60])
    return kind, value["id"]


def authority(actor_id: int, kind: OwnerKind, entity_id: int) -> Optional[ActionResult]:
    """O jogador age por si; por uma empresa, só o Dono (02 §16)."""
    if kind is OwnerKind.PLAYER:
        if entity_id != actor_id:
            return refuse("NOT_PARTY_REPRESENTATIVE", party=[kind.value, entity_id])
        return None
    if not Company.objects.filter(pk=entity_id).exists():
        return refuse("COMPANY_NOT_FOUND", company=entity_id)
    return None if company_services.owner_of(entity_id) == actor_id else refuse("NOT_OWNER", company=entity_id)


def account(kind: OwnerKind, entity_id: int) -> Optional[int]:
    return party_account_id(MarketPartyKind(kind.value), entity_id)


def acting_player(kind: OwnerKind, entity_id: int) -> Optional[int]:
    """Quem age por essa parte: o próprio jogador, ou o Dono da empresa."""
    return entity_id if kind is OwnerKind.PLAYER else company_services.owner_of(entity_id)


def lock(actor_id: int, parties: List[Tuple[OwnerKind, int]], extra_players: Tuple[int, ...] = ()) -> None:
    """Jogador(es) crescente → empresa(s) crescente."""
    player_ids = sorted({actor_id, *extra_players} | {i for k, i in parties if k is OwnerKind.PLAYER})
    list(Player.objects.select_for_update().filter(pk__in=player_ids).order_by("pk"))
    company_ids = sorted({i for k, i in parties if k is OwnerKind.COMPANY})
    if company_ids:
        list(Company.objects.select_for_update().filter(pk__in=company_ids).order_by("pk"))
