"""
Processamento de ticks (design/04 §23-25: simulação atrasada por eventos).

Duas peças:
1. Registro de handlers: cada sistema declara QUE tipo de tick o move, em que
   escopo, e com que prioridade. (A classificação sistema -> tick é decisão de
   design ainda em aberto no 04 §27; este módulo só dá o mecanismo.)
2. process_ticks(): roda, em ordem determinística, os handlers de um escopo
   para todos os ticks de um intervalo (start, end].

Escopos: "world" (global: ciclo semanal de leis, orçamento...) e escopos por
entidade (ex.: "player"), processados sob demanda quando a entidade é
acessada ("catch-up" lazy) -- quem chama guarda o seu próprio ponteiro
`processed_until`.

Ordem em um mesmo instante (provisória, ver CHANGELOG_DEV.md):
    (TickKind, priority, name)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

from django.db import transaction

from . import clock as game_clock
from .models import WorldClock
from .timeline import Tick, TickKind, ticks_between

WORLD = "world"

Handler = Callable[[Tick, Any], None]


@dataclass(frozen=True)
class _Registration:
    scope: str
    kind: TickKind
    name: str
    priority: int
    fn: Handler


class TickRegistry:
    def __init__(self):
        self._by_key: Dict[tuple, List[_Registration]] = defaultdict(list)

    def register(self, scope: str, kind: TickKind, name: str, priority: int = 100):
        """Decorator. `name` é único por (scope, kind) e entra no desempate."""

        def deco(fn: Handler) -> Handler:
            regs = self._by_key[(scope, kind)]
            if any(r.name == name for r in regs):
                raise ValueError(f"Handler duplicado: {scope}/{kind.name}/{name}")
            regs.append(_Registration(scope, kind, name, priority, fn))
            regs.sort(key=lambda r: (r.priority, r.name))
            return fn

        return deco

    def handlers_for(self, scope: str, kind: TickKind) -> List[_Registration]:
        return list(self._by_key.get((scope, kind), ()))

    def kinds_for(self, scope: str) -> List[TickKind]:
        return sorted(k for (s, k), regs in self._by_key.items() if s == scope and regs)

    def clear(self) -> None:
        self._by_key.clear()


registry = TickRegistry()
register = registry.register


@dataclass(frozen=True)
class ProcessResult:
    ticks_processed: int
    processed_until: int  # novo ponteiro: tudo <= este valor está processado
    complete: bool  # False se parou por `limit`; chame de novo para continuar


def process_ticks(
    scope: str,
    start: int,
    end: int,
    context: Any = None,
    *,
    limit: Optional[int] = None,
    reg: Optional[TickRegistry] = None,
) -> ProcessResult:
    """
    Executa os handlers de `scope` para cada tick em (start, end].

    - `limit`: máximo aproximado de ticks por chamada (ausências longas). Ao
      atingi-lo, para na próxima fronteira de instante: `processed_until` fica
      no último instante processado e `complete=False`.
    - Não abre transação: quem chama decide a atomicidade (advance_world abre).
    - Se um handler levantar exceção, ela propaga; o ponteiro NÃO avança
      (quem chama só o persiste após sucesso).
    """
    reg = reg or registry
    if end <= start:
        return ProcessResult(0, start, True)
    kinds = reg.kinds_for(scope)
    if not kinds:
        # Nenhum handler neste escopo: não há o que executar; o ponteiro avança.
        return ProcessResult(0, end, True)

    count = 0
    last_at = start
    for tick in ticks_between(start, end, kinds):
        # Só paramos em FRONTEIRA DE INSTANTE: se vários ticks caem no mesmo
        # instante, todos rodam, senão o ponteiro "tudo <= at processado"
        # mentiria. Logo `limit` pode ser excedido por até (nº de kinds - 1).
        if limit is not None and count >= limit and tick.at != last_at:
            return ProcessResult(count, last_at, False)
        for r in reg.handlers_for(scope, tick.kind):
            r.fn(tick, context)
        count += 1
        last_at = tick.at
    return ProcessResult(count, end, True)


def advance_world(*, limit: Optional[int] = None, reg: Optional[TickRegistry] = None) -> ProcessResult:
    """
    Processa os ticks pendentes do escopo "world" até o tempo de jogo atual.

    Atômico e seguro contra concorrência: trava o WorldClock (select_for_update),
    roda os handlers na mesma transação e só então move `world_processed_until`.
    Falhou => rollback total, nada é marcado como processado, nada se repete.
    """
    with transaction.atomic():
        wc = WorldClock.load(for_update=True)
        target = game_clock.now()
        result = process_ticks(WORLD, wc.world_processed_until, target, None, limit=limit, reg=reg)
        if result.processed_until > wc.world_processed_until:
            wc.world_processed_until = result.processed_until
            wc.save(update_fields=["world_processed_until"])
    return result


def catch_up(
    scope: str,
    processed_until: int,
    context: Any,
    *,
    until: Optional[int] = None,
    limit: Optional[int] = None,
    reg: Optional[TickRegistry] = None,
) -> ProcessResult:
    """
    Catch-up lazy de uma entidade: processa (processed_until, until] com
    `context` = a entidade. `until` padrão = tempo de jogo atual.
    O chamador persiste `result.processed_until` na entidade, na mesma
    transação em que persiste os efeitos dos handlers.
    """
    return process_ticks(
        scope,
        processed_until,
        game_clock.now() if until is None else until,
        context,
        limit=limit,
        reg=reg,
    )
