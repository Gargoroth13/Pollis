"""Identidade e contas dos governos (09 §2): União (singleton), Estado (`geography.State`) e Município (`geography.City`, R8 do 24)."""
from __future__ import annotations

from typing import Any, Optional, Tuple, Union

from geography.models import City, State
from ledger import services as ledger
from ledger.constants import AccountKind
from ledger.models import Account
from players.services import ActionResult

from .constants import Level

_KIND = {Level.UNION: AccountKind.UNION, Level.STATE: AccountKind.STATE, Level.MUNICIPALITY: AccountKind.MUNICIPALITY}


def refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and -(2 ** 63) <= v < 2 ** 63


def parse_gov(value: Any) -> Union[Tuple[Level, int], ActionResult]:
    """`{"level": "union"|"state"|"municipality", "id": n}`; a União tem id 0."""
    if not isinstance(value, dict) or set(value) != {"level", "id"}:
        return refuse("INVALID_GOVERNMENT", government=repr(value)[:80])
    try:
        level = Level(value["level"])
    except ValueError:
        return refuse("INVALID_GOVERNMENT", government=repr(value)[:80])
    ident = value["id"]
    if not is_int(ident) or (level is Level.UNION and ident != 0) or (level is not Level.UNION and ident <= 0):
        return refuse("INVALID_GOVERNMENT", government=repr(value)[:80])
    exists = (level is Level.UNION or (level is Level.STATE and State.objects.filter(pk=ident).exists())
              or (level is Level.MUNICIPALITY and City.objects.filter(pk=ident).exists()))
    return (level, ident) if exists else refuse("GOVERNMENT_NOT_FOUND", level=level.value, id=ident)


def ref(level: Level, ident: int) -> dict:
    return {"level": level.value, "id": ident}


def account_of(level: Level, ident: int) -> Account:
    return ledger.get_or_create_account(_KIND[level], 0 if level is Level.UNION else ident)


def state_of_city(city_id: int) -> Optional[int]:
    return City.objects.filter(pk=city_id).values_list("state_id", flat=True).first()


def ensure_accounts() -> int:
    """Abre as contas de TODOS os governos (União, Estados, Municípios). A janela do teto de déficit conta desde a abertura da conta (24 §24.16):
    abrir tudo de uma vez, na formação do mundo, evita que a idade da conta dependa de quando alguém a usou pela primeira vez."""
    account_of(Level.UNION, 0)
    n = 1
    for sid in State.objects.order_by("pk").values_list("pk", flat=True):
        account_of(Level.STATE, sid)
        n += 1
    for cid in City.objects.order_by("pk").values_list("pk", flat=True):
        account_of(Level.MUNICIPALITY, cid)
        n += 1
    return n
