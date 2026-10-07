"""
Regras puras de viagem (design/04 §6, §20, §21). Não tocam o banco.

Geografia fornece a DISTÂNCIA; este módulo só compõe o tempo-base e decide o que depende de presença. Veículos,
infraestrutura e transporte público (04 §21) não existem: quando existirem, entram como novos passos multiplicativos
do detalhamento, sobre o tempo-base.
"""
from __future__ import annotations

from decimal import ROUND_CEILING, Decimal
from typing import Optional

from core.breakdown import Calc, Explained
from players.actions import Action
from players.hooks import ActivityContext
from players.models import Player

from .balance import TravelBalance


def travel_time(distance: Decimal, minutes_per_unit: Decimal, at: Optional[int] = None) -> Explained:
    """
    tempo-base de viagem (minutos de jogo) = distância em grid × minutos_por_unidade   (04 §21)
    Detalhamento estruturado (doc 20): quem consome (interface, bots) vê os dois componentes.
    """
    return Calc("distance", distance).mul("minutes_per_unit", minutes_per_unit).result(at)


def duration_seconds(minutes: Decimal) -> int:
    """
    Minutos -> segundos de jogo inteiros (o motor de tempo usa segundos inteiros). Arredonda PARA CIMA: a viagem nunca
    chega antes do tempo calculado. Mínimo de 1 s para manter a invariante "chega depois de partir". O design não define o
    arredondamento; é decisão técnica registrada no CHANGELOG_DEV.md.
    """
    return max(1, int((minutes * 60).to_integral_value(rounding=ROUND_CEILING)))


def requires_presence(action: Action, activity: Optional[ActivityContext], bal: TravelBalance) -> bool:
    """A atividade informa; se não informar, vale o padrão da ação (configuração [ABERTO])."""
    if activity is not None and activity.requires_presence is not None:
        return activity.requires_presence
    return bal.presence_dependent_by_default[action.value]


def departure_block(player: Player, now: int, bal: TravelBalance) -> Optional[str]:
    """Estado do jogador que impede PARTIR (configuração [ABERTO]; vazia por padrão)."""
    for state in bal.travel_blocking_states:
        if state == "hospitalized" and player.is_hospitalized(now):
            return "HOSPITALIZED"
        if state == "health_critical" and player.health_critical:
            return "HEALTH_CRITICAL"
        if state == "burnout_active" and player.burnout_active:
            return "BURNOUT_ACTIVE"
    return None
