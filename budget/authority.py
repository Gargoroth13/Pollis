"""
Quem ocupa os cargos executivos (09 §3-§5, §27): Presidente → caixa federal, Governador → caixa do Estado, Prefeito → caixa do Município.

Os CARGOS pertencem a `06 — Política` (REVIEW) e à P1.11 (não implementada). O Orçamento NÃO inventa quem ocupa cada cargo: consulta PROVEDORES de
ocupante (gancho técnico, como o zoneamento e a elegibilidade de lance). Sem provedor, ninguém tem autoridade (`NO_OFFICE_HOLDER`), nunca "qualquer um".
A P1.11 (e o cenário do Bot Test, `21`/`09` §37: bots já começam no cargo) registram o provedor. Dois provedores que discordam falham, em vez de decidir
sozinhos (o design não define precedência; mesma regra do zoneamento).
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from players.models import Player
from players.services import ActionResult

from .constants import Level

OfficeProvider = Callable[[Level, int], Optional[int]]      # (nível, id do território; União = 0) → id do jogador ocupante, ou None
_providers: Dict[str, OfficeProvider] = {}

OFFICE_NAMES = {Level.UNION: "president", Level.STATE: "governor", Level.MUNICIPALITY: "mayor"}


class OfficeConflict(Exception):
    """Dois provedores apontam ocupantes diferentes para o mesmo cargo; o design não define precedência."""


def register_office_provider(name: str, fn: OfficeProvider) -> None:
    if name in _providers:
        raise ValueError(f"Provedor de ocupante de cargo duplicado: {name}")
    _providers[name] = fn


def unregister_office_provider(name: str) -> None:       # para testes
    _providers.pop(name, None)


def clear_office_providers() -> None:                    # para testes
    _providers.clear()


def holder_of(level: Level, territory_id: int) -> Optional[int]:
    """O jogador que ocupa o cargo executivo do governo, ou None (vago ou sem provedor)."""
    found = {}
    for name in sorted(_providers):
        holder = _providers[name](level, territory_id)
        if holder is not None:
            found[name] = holder
    if len(set(found.values())) > 1:
        raise OfficeConflict(f"{level.value}:{territory_id} -> {found}")
    return next(iter(found.values()), None)


def authority_refusal(actor_id: int, level: Level, territory_id: int) -> Optional[ActionResult]:
    """Só o ocupante do cargo age pelo governo. Recusas: PLAYER_NOT_FOUND, OFFICE_CONFLICT, NO_OFFICE_HOLDER, NOT_OFFICE_HOLDER."""
    if not Player.objects.filter(pk=actor_id).exists():
        return ActionResult(False, "PLAYER_NOT_FOUND", {"player": actor_id})
    try:
        holder = holder_of(level, territory_id)
    except OfficeConflict as exc:
        return ActionResult(False, "OFFICE_CONFLICT", {"office": OFFICE_NAMES[level], "why": str(exc)})
    if holder is None:
        return ActionResult(False, "NO_OFFICE_HOLDER", {"office": OFFICE_NAMES[level], "level": level.value, "territory": territory_id})
    if holder != actor_id:
        return ActionResult(False, "NOT_OFFICE_HOLDER", {"office": OFFICE_NAMES[level], "level": level.value, "territory": territory_id})
    return None
