"""
Quem ocupa os cargos que o processo legislativo consulta (design/07 §07.3, §07.7, §07.12; 06 — Política, REVIEW).

Os CARGOS e a composição da Câmara pertencem a `06` e à P1.11 (não implementada). A legislação NÃO inventa quem é Presidente ou Deputado: consulta
PROVEDORES (gancho técnico, como `budget.authority`). Sem provedor: não há Presidente, não há Câmara, ninguém propõe e os prazos ficam suspensos
(07 §07.19: "prazos legislativos ficam suspensos enquanto não houver Câmara"). Dois provedores que discordam falham (`ProviderConflict`).

Um provedor é um objeto com três consultas:
  president()   -> id do jogador ou None (vago)
  deputies()    -> lista de ids das cadeiras OCUPADAS (07 §07.9: cadeira vaga não entra no quórum); vazia = Câmara não constituída
  suggesters()  -> ids de Governadores e Prefeitos (07 §07.3: só podem SUGERIR ao Presidente)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, List, Optional


class ProviderConflict(Exception):
    """Dois provedores apontam ocupantes diferentes; o design não define precedência."""


@dataclass(frozen=True)
class OfficeProvider:
    president: Callable[[], Optional[int]]
    deputies: Callable[[], List[int]]
    suggesters: Callable[[], FrozenSet[int]] = lambda: frozenset()


_providers: Dict[str, OfficeProvider] = {}


def register_provider(name: str, provider: OfficeProvider) -> None:
    if name in _providers:
        raise ValueError(f"Provedor legislativo duplicado: {name}")
    _providers[name] = provider


def unregister_provider(name: str) -> None:       # para testes
    _providers.pop(name, None)


def clear_providers() -> None:                    # para testes
    _providers.clear()


def president() -> Optional[int]:
    found = {n: p.president() for n, p in sorted(_providers.items())}
    found = {n: v for n, v in found.items() if v is not None}
    if len(set(found.values())) > 1:
        raise ProviderConflict(f"president -> {found}")
    return next(iter(found.values()), None)


def deputies() -> List[int]:
    """Cadeiras ocupadas (ordenadas, sem repetição). Vazia = não há Câmara constituída."""
    seats = set()
    for _, p in sorted(_providers.items()):
        seats.update(p.deputies())
    return sorted(seats)


def suggesters() -> FrozenSet[int]:
    out = set()
    for _, p in sorted(_providers.items()):
        out.update(p.suggesters())
    return frozenset(out)


def chamber_constituted() -> bool:
    return bool(deputies())
