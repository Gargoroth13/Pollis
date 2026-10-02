"""
Decadência diária da Especialização (02 §13), no mesmo processamento lazy do jogador (players: 04 §22).

Roda no tick DIÁRIO (00:00 local do jogo). No tick que ABRE o dia X, o dia que acabou é X-1: se a
especialização não foi usada em X-1, decai. Assim "dia sem uso" é exatamente o que o design chama de
decadência diária, e acessar o jogo a mais não muda o resultado (mesmos ticks, mesma ordem).
"""
from core.ticks import register
from core.timeline import TickKind

from . import rules
from .balance import get_skill_balance
from .models import Specialization

PLAYER = "player"


@register(PLAYER, TickKind.DAILY, "specialization_decay", priority=20)
def _specialization_decay(tick, ctx):
    ended_day = rules.day_index(tick.at) - 1
    unused = list(Specialization.objects.filter(player=ctx.player, last_used_day__lt=ended_day).order_by("key"))
    if not unused:
        return
    sbal = get_skill_balance()
    for row in unused:
        decayed = rules.apply_daily_decay(row.value, row.historic_max, sbal)
        if decayed != row.value:
            row.value = decayed
            row.save(update_fields=["value"])
