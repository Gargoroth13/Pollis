"""
Handler do escopo "player" no ciclo de 10 minutos de jogo (design/04 §22-23).

Um único handler que delega para rules.advance_cycle: a ORDEM interna do ciclo é regra do
design (04 §23) e vive em um lugar só, em vez de espalhada em handlers com prioridades.

O contexto carrega o Balance já validado: um catch-up longo roda dezenas de milhares de ciclos
e não deve revalidar a configuração em cada um.
"""
from dataclasses import dataclass, field
from typing import Any, Dict

from core.ticks import register
from core.timeline import TickKind

from . import rules
from .balance import Balance
from .models import Player

PLAYER = "player"


@dataclass
class CycleContext:
    player: Player
    bal: Balance
    # Memória de UM catch-up: um handler de outro sistema que precisa consultar o banco o faz uma vez e guarda aqui,
    # em vez de repetir a consulta a cada ciclo (uma ausência longa processa dezenas de milhares de ciclos).
    cache: Dict[str, Any] = field(default_factory=dict)


@register(PLAYER, TickKind.TEN_MINUTES, "cycle", priority=10)
def _cycle(tick, ctx: CycleContext):
    rules.advance_cycle(ctx.player, tick.at, ctx.bal)
