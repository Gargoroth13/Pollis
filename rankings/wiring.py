"""Ligação dos Rankings aos sistemas de origem. Chamada por `RankingsConfig.ready` (idempotente)."""
from __future__ import annotations

from core import ticks
from core.timeline import Tick, TickKind
from players import registry

from . import activity, params, records

OBSERVER_ACTIVITY = "rankings_activity"
OBSERVER_NET_WORTH = "rankings_net_worth"
TICK_NAME = "rankings_net_worth_sweep"


def _on_action_activity(player_id, action_id, result) -> None:
    activity.record_action(player_id)


def _on_action_net_worth(player_id, action_id, result) -> None:
    records.check_net_worth_record(player_id)


def daily_sweep(tick: Tick, context) -> None:
    """Varredura diária do recorde de patrimônio: cobre picos que não passaram por uma ação do próprio jogador."""
    records.sweep_net_worth_record(tick.at)


def connect() -> None:
    names = registry.action_observer_names()
    if OBSERVER_ACTIVITY not in names:
        registry.register_action_observer(OBSERVER_ACTIVITY, _on_action_activity)
    if OBSERVER_NET_WORTH not in names:
        registry.register_action_observer(OBSERVER_NET_WORTH, _on_action_net_worth)
    if not any(r.name == TICK_NAME for r in ticks.registry.handlers_for(ticks.WORLD, TickKind.DAILY)):
        ticks.register(ticks.WORLD, TickKind.DAILY, TICK_NAME, params.DAILY_TICK_PRIORITY)(daily_sweep)
