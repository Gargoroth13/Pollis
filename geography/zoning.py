"""
Zoneamento (design/08 §16, §23.4; consumido por 10 §22).

  - Cada lote tem regras PADRÃO de uso: sem outras regras, a categoria do lote admite o seu próprio uso. A MISTURA de
    usos é permitida CONFORME O ZONEAMENTO (decisão do Game Director, 2026-10-03; 08 §16 diz "relativamente separados"):
    a matriz é parametrizável (Scenario.zoning_permissions) e as misturas entram por ela ou por overrides de lei.
    NÃO existe regra de DISTÂNCIA entre tipos de uso (ex.: "indústria a X do residencial"): a decisão sobre um lote
    depende só do lote e do uso. Restrições assim virão de leis/zoneamento quando esse sistema existir.
  - O zoneamento NÃO é imutável: leis, projetos públicos e mecânicas políticas poderão alterar permissões
    (liberar, restringir, criar exceções territoriais). Por isso há um PONTO DE EXTENSÃO: provedores de override.
    O sistema de leis (P1.12) ainda não existe e não há regra de precedência entre leis no design, então esta
    camada NÃO inventa uma: se dois provedores discordarem, falha em vez de decidir sozinha.
  - O sistema imobiliário (10) deve CONSULTAR este módulo, não duplicar a regra (10 §22).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, Optional, Tuple

from .balance import Scenario, get_scenario
from .constants import CATEGORIES, Category
from .models import Lot

Override = Callable[[Lot, Category], Optional[bool]]
_overrides: Dict[str, Override] = {}


class ZoningConflict(Exception):
    """Dois provedores de override discordam e o design ainda não define precedência entre eles."""


def register_zoning_override(name: str, fn: Override) -> None:
    """
    Uma lei/projeto altera o zoneamento: `fn(lot, use)` devolve True (libera), False (proíbe) ou None (não opina).
    """
    if name in _overrides:
        raise ValueError(f"Override de zoneamento duplicado: {name}")
    _overrides[name] = fn


def unregister_zoning_override(name: str) -> None:  # para testes
    _overrides.pop(name, None)


def base_permissions(sc: Optional[Scenario] = None) -> Dict[Category, FrozenSet[Category]]:
    """Matriz padrão: categoria do lote -> usos permitidos."""
    sc = sc or get_scenario()
    if sc.zoning_permissions is None:
        return {c: frozenset({c}) for c in CATEGORIES}
    return {c: frozenset(sc.zoning_permissions.get(c, (c,))) for c in CATEGORIES}


@dataclass(frozen=True)
class ZoningDecision:
    allowed: bool
    base_allowed: bool                        # o que o zoneamento padrão diria
    overridden_by: Tuple[Tuple[str, bool], ...]  # (provedor, decisão) dos que opinaram


def decide(lot: Lot, use: Category, sc: Optional[Scenario] = None) -> ZoningDecision:
    """O uso `use` é permitido neste lote? Zoneamento padrão + overrides de leis/projetos."""
    use = use if isinstance(use, Category) else Category(use)
    base = use in base_permissions(sc)[Category(lot.category)]
    opinions = tuple((name, verdict) for name in sorted(_overrides)
                     if (verdict := _overrides[name](lot, use)) is not None)
    verdicts = {v for _, v in opinions}
    if len(verdicts) > 1:
        raise ZoningConflict(f"Overrides discordam para o lote {lot.pk} e uso '{use.value}': {opinions}. "
                             f"O design ainda não define a precedência entre leis.")
    return ZoningDecision(verdicts.pop() if verdicts else base, base, opinions)


def is_use_allowed(lot: Lot, use: Category, sc: Optional[Scenario] = None) -> bool:
    return decide(lot, use, sc).allowed
