"""
Serviços do estado do jogador: ÚNICO ponto de entrada para mudar este estado.

Jogadores reais e bots chamam as mesmas funções (design/21). Cada serviço:
  1. abre transação e trava a linha do jogador (select_for_update);
  2. faz o catch-up lazy até AGORA (04 §22: "On Access processa o estado lazy antes de novas ações");
  3. valida e aplica a regra (rules.py);
  4. devolve ActionResult estruturado. Recusa de regra NÃO é exceção: é um código
     (INSUFFICIENT_ENERGY, BURNOUT_ACTIVE...), para que bots e UI reajam sem try/except.

O tempo vem SEMPRE de core.clock (injetável), lido uma vez por chamada.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction

from core import clock as game_clock
from core.breakdown import D, Explained
from core.ticks import catch_up

from . import hooks, rules
from .balance import get_balance
from .hooks import ActionHookContext, ActivityContext
from .models import FOOD, LEISURE, Player, QolEffect
from .qol import qol_base, qol_base_effective, qol_current
from .rules import Action, q
from .tick_handlers import PLAYER, CycleContext


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    code: str  # "OK" ou um código de recusa
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectSpec:
    """Efeito temporário de QoL que acompanha uma ação (ex.: o buff de uma atividade de Lazer)."""
    source: str
    amount: Decimal
    duration_seconds: int


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def _locked(player_id: int) -> Player:
    return Player.objects.select_for_update().get(pk=player_id)


def _catch_up(player: Player, now: int) -> None:
    """Processa os ciclos de 10 min pendentes (lazy, 04 §22) e roda os hooks de acesso (On Access)."""
    ctx = CycleContext(player, get_balance())
    result = catch_up(PLAYER, player.processed_until, ctx, until=now)
    player.processed_until = max(player.processed_until, result.processed_until)
    hooks.run_access_hooks(player, now)  # ex.: concluir o que venceu entre o último ciclo e `now`


@contextmanager
def locked_player(player_id: int):
    """
    Sessão de serviço para OUTROS sistemas (ex.: viagem): transação atômica, linha do jogador travada e catch-up até
    AGORA; salva o jogador ao sair. Dá a eles o mesmo caminho de perform_action, sem duplicar a lógica.
    Devolve (player, now, bal).
    """
    with transaction.atomic():
        player = _locked(player_id)
        now = game_clock.now()
        _catch_up(player, now)
        yield player, now, get_balance()
        player.save()


def _block_reasons(player: Player, action: Action, now: int, bal, activity) -> List[str]:
    """Motivos do próprio players (04) + os acrescentados por outros sistemas via provedores de bloqueio."""
    reasons = rules.block_reasons(player, action, now, bal)
    return reasons + [r for r in hooks.run_block_providers(player, action, now, activity) if r not in reasons]


def _apply_effect(player: Player, category: str, spec: EffectSpec, now: int) -> None:
    """Um efeito por categoria; o novo SUBSTITUI o anterior, nunca soma (04 §4.4)."""
    if spec.duration_seconds <= 0:
        raise ValueError("duration_seconds deve ser > 0")
    QolEffect.objects.update_or_create(
        player=player, category=category,
        defaults={"source": spec.source, "amount": D(spec.amount),
                  "starts_at": now, "expires_at": now + spec.duration_seconds},
    )


@transaction.atomic
def create_player(user, *, now: Optional[int] = None) -> Player:
    """Estado inicial do 04 §24. Outros sistemas inicializam o seu estado via hooks de criação."""
    bal = get_balance()
    now = game_clock.now() if now is None else now
    player = Player(
        user=user, energy=bal.energy_max, health=bal.health_initial, nutrition=bal.nutrition_initial,
        burnout=Decimal(0), processed_until=now, created_at_game=now,
    )
    rules.update_health_flags(player, now, bal)
    player.save()
    hooks.run_player_created_hooks(player, now)
    return player


@transaction.atomic
def sync_player(player_id: int) -> Player:
    """Atualiza o jogador até o momento atual (idempotente) e o devolve."""
    player = _locked(player_id)
    _catch_up(player, game_clock.now())
    player.save()
    return player


@dataclass(frozen=True)
class PlayerSnapshot:
    """Leitura completa e EXPLICADA do estado (observável por UI e bots)."""
    at: int
    energy: Decimal
    health: Decimal
    nutrition: Decimal
    burnout: Decimal
    burnout_active: bool
    health_critical: bool
    hospitalized: bool
    work_blocked_by: List[str]
    study_blocked_by: List[str]
    leisure_blocked_by: List[str]
    qol_base: Explained
    qol_base_effective: Explained
    qol_current: Explained
    energy_regen_per_cycle: Explained
    health_change_per_cycle: Explained


def get_snapshot(player_id: int) -> PlayerSnapshot:
    bal = get_balance()
    with transaction.atomic():
        player = _locked(player_id)
        now = game_clock.now()
        _catch_up(player, now)
        player.save()
        structural = qol_base(player, now, bal)
        effective = qol_base_effective(player, now, bal, structural=structural)
        return PlayerSnapshot(
            at=now, energy=player.energy, health=player.health, nutrition=player.nutrition,
            burnout=player.burnout, burnout_active=player.burnout_active,
            health_critical=player.health_critical, hospitalized=player.is_hospitalized(now),
            work_blocked_by=_block_reasons(player, Action.WORK, now, bal, None),
            study_blocked_by=_block_reasons(player, Action.STUDY, now, bal, None),
            leisure_blocked_by=_block_reasons(player, Action.LEISURE, now, bal, None),
            qol_base=structural, qol_base_effective=effective,
            qol_current=qol_current(player, now, bal, effective=effective),
            energy_regen_per_cycle=rules.energy_regen(player, now, bal),
            health_change_per_cycle=rules.health_change(player, now, bal),
        )


@transaction.atomic
def perform_action(player_id: int, action: Action, *, burnout_risk=1,
                   effect: Optional[EffectSpec] = None,
                   activity: Optional[ActivityContext] = None) -> ActionResult:
    """
    Trabalhar, Estudar ou Lazer: custo FIXO de Energia (04 §2.2: o jogador não escolhe quanto gastar),
    alteração de Burnout (+5/+3/-10) e, no Lazer, o efeito temporário da atividade (categoria Lazer).
    `burnout_risk`: multiplicador de risco de Burnout (02 §9.2), 1 = 100%.
    `activity`: o que a atividade oferece a OUTROS sistemas (ex.: skills que desenvolve). Os hooks
    registrados (players.hooks) reagem a ela dentro desta mesma transação, depois do sucesso da ação.
    """
    bal = get_balance()
    risk = D(burnout_risk)
    player = _locked(player_id)
    now = game_clock.now()
    _catch_up(player, now)

    if effect is not None and action is not Action.LEISURE:
        raise ValueError("Só a ação de Lazer aplica efeito de QoL próprio (04 §19).")
    reasons = _block_reasons(player, action, now, bal, activity)
    if reasons:
        player.save()
        return _refuse(reasons[0], reasons=reasons)
    cost = rules.energy_cost(action, bal)
    if player.energy < cost:
        player.save()
        return _refuse("INSUFFICIENT_ENERGY", energy=str(player.energy), required=str(cost))

    player.energy = q(player.energy - cost)
    change = rules.burnout_change(action, risk, bal)
    rules.apply_burnout_change(player, change.value, bal)
    if action is Action.WORK:
        player.last_work_at = now
    if effect is not None:
        _apply_effect(player, LEISURE, effect, now)
    hook_results = hooks.run_action_hooks(ActionHookContext(player, action, now, bal, activity))
    player.save()
    return ActionResult(True, "OK", {
        "energy": player.energy, "energy_spent": cost, "burnout": player.burnout,
        "burnout_active": player.burnout_active, "burnout_change": change, "hooks": hook_results,
    })


@transaction.atomic
def consume_food(player_id: int, nutrition_gain, *, effect: Optional[EffectSpec] = None) -> ActionResult:
    """
    Efeito de um alimento: Nutrição + eventual efeito temporário da categoria Comida (04 §15-16).
    O item, o inventário e o catálogo de ganhos pertencem a seus próprios sistemas.
    """
    gain = D(nutrition_gain)
    if gain < 0:
        return _refuse("INVALID_AMOUNT")
    player = _locked(player_id)
    now = game_clock.now()
    _catch_up(player, now)
    rules.apply_food(player, gain, get_balance())
    if effect is not None:
        _apply_effect(player, FOOD, effect, now)
    player.save()
    return ActionResult(True, "OK", {"nutrition": player.nutrition})


@transaction.atomic
def change_health(player_id: int, delta, source: str) -> ActionResult:
    """Dano/cura vindos de outros sistemas (tratamento, eventos, condições). `source` identifica a origem."""
    player = _locked(player_id)
    now = game_clock.now()
    _catch_up(player, now)
    rules.apply_health_change(player, D(delta), now, get_balance())
    player.save()
    return ActionResult(True, "OK", {
        "health": player.health, "health_critical": player.health_critical,
        "hospitalized": player.is_hospitalized(now), "source": source,
    })


@transaction.atomic
def apply_temporary_effect(player_id: int, category: str, source: str, amount, duration_seconds: int) -> ActionResult:
    """Buff/debuff temporário de QoL de qualquer sistema (serviços, condições). Substitui o da mesma categoria."""
    if duration_seconds <= 0:
        return _refuse("INVALID_DURATION")
    player = _locked(player_id)
    now = game_clock.now()
    _catch_up(player, now)
    player.save()
    _apply_effect(player, category, EffectSpec(source, D(amount), duration_seconds), now)
    return ActionResult(True, "OK", {"category": category, "expires_at": now + duration_seconds})
