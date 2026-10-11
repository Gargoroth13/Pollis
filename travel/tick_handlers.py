"""
Chegada da viagem no ciclo de 10 minutos de jogo do jogador (design/04 §22: processamento lazy por ciclos).

Conclui a viagem no primeiro ciclo em que `arrives_at <= tick.at`, para que ciclos POSTERIORES à chegada já
vejam o jogador no destino, em ordem. A chegada exata entre dois ciclos é tratada pelo hook de acesso
(travel.services.settle_arrivals). Os dois levam ao MESMO estado final.

A viagem ativa é consultada UMA vez por catch-up (ctx.cache), não a cada ciclo.
"""
from core.ticks import register
from core.timeline import TickKind

from . import services
from .models import Journey

_KEY = "travel.active_journey"


@register("player", TickKind.TEN_MINUTES, "travel_arrival", priority=20)
def _arrival(tick, ctx):
    if _KEY not in ctx.cache:
        ctx.cache[_KEY] = Journey.objects.filter(player=ctx.player, completed=False).first()
    journey = ctx.cache[_KEY]
    if journey is not None and journey.arrives_at <= tick.at:
        services.complete_journey(journey)
        ctx.cache[_KEY] = None
