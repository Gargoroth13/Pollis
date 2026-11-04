"""Ligação dos Rankings aos sistemas de origem. Chamada por `RankingsConfig.ready` (idempotente)."""
from __future__ import annotations

from core import ticks
from core.timeline import Tick, TickKind
from ledger import hooks as ledger_hooks
from players import registry

from . import activity, params, records

OBSERVER_ACTIVITY = "rankings_activity"
LEDGER_HOOK_NET_WORTH = "rankings_net_worth"
TICK_RETRY = "rankings_net_worth_retry"
TICK_SWEEP = "rankings_net_worth_sweep"


def _on_action_activity(player_id, action_id, result) -> None:
    activity.record_action(player_id)


def hourly_retry(tick: Tick, context) -> None:
    """Reaplica candidatos de recorde de patrimônio que não puderam ser gravados no fim da operação do ledger."""
    records.drain_net_worth_candidates()


def daily_sweep(tick: Tick, context) -> None:
    """Reconciliação diária do recorde de patrimônio (o recorde em si é mantido pelo gancho do ledger)."""
    records.sweep_net_worth_record(tick.at)


def _has_tick(kind: TickKind, name: str) -> bool:
    return any(r.name == name for r in ticks.registry.handlers_for(ticks.WORLD, kind))


def connect() -> None:
    if OBSERVER_ACTIVITY not in registry.action_observer_names():
        registry.register_action_observer(OBSERVER_ACTIVITY, _on_action_activity)
    if LEDGER_HOOK_NET_WORTH not in ledger_hooks.operation_hook_names():
        ledger_hooks.register_operation_hook(LEDGER_HOOK_NET_WORTH, records.on_ledger_operation)
    if not _has_tick(TickKind.HOURLY, TICK_RETRY):
        ticks.register(ticks.WORLD, TickKind.HOURLY, TICK_RETRY, params.DAILY_TICK_PRIORITY)(hourly_retry)
    if not _has_tick(TickKind.DAILY, TICK_SWEEP):
        ticks.register(ticks.WORLD, TickKind.DAILY, TICK_SWEEP, params.DAILY_TICK_PRIORITY)(daily_sweep)
