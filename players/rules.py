"""
Transições de estado do jogador. Fonte ÚNICA das regras do design/04.

Funções operam sobre uma instância de Player em memória e NÃO tocam o banco: o chamador
(handler de tick ou service) persiste. O mesmo código serve ao processamento lazy por ciclos
(04 §22) e às ações imediatas, sem duplicar regra.

Todo valor gravado é quantizado a 6 casas: o estado em memória é idêntico ao persistido.
"""
from __future__ import annotations

import enum
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Callable, Dict, List, Optional

from core.breakdown import Calc, Explained
from .balance import Balance
from .models import Player
from .qol import qol_base_effective

_Q = Decimal("0.000001")


def q(x: Decimal) -> Decimal:
    return x.quantize(_Q, rounding=ROUND_HALF_EVEN)


def clamp(x: Decimal, low: Decimal, high: Decimal) -> Decimal:
    return max(low, min(high, x))


class Action(str, enum.Enum):
    """Ações com custo fixo de Energia (04 §2.2). Tratamento depende do sistema de dinheiro: ver CHANGELOG."""
    WORK = "work"
    STUDY = "study"
    LEISURE = "leisure"


def energy_cost(action: Action, bal: Balance) -> Decimal:
    return {Action.WORK: bal.energy_cost_work, Action.STUDY: bal.energy_cost_study,
            Action.LEISURE: bal.energy_cost_leisure}[action]


# --- Bloqueios (04 §6, §7.3, §12, §14) -------------------------------------

def block_reasons(player: Player, action: Action, at: int) -> List[str]:
    """Motivos pelos quais a ação não pode ser feita agora, em ordem fixa (determinística)."""
    reasons: List[str] = []
    if action is Action.WORK:
        if player.is_hospitalized(at):
            reasons.append("HOSPITALIZED")
        if player.health_critical:
            reasons.append("HEALTH_CRITICAL")
        if player.burnout_active:
            reasons.append("BURNOUT_ACTIVE")
        # Viagem (04 §6) entra aqui quando o sistema de Geografia/Viagem existir.
    elif action is Action.STUDY:
        if player.burnout_active:
            reasons.append("BURNOUT_ACTIVE")
    return reasons  # Lazer continua permitido em Burnout Ativo (04 §7.3)


# --- Energia (04 §2.3) ------------------------------------------------------

def energy_regen(player: Player, at: int, bal: Balance) -> Explained:
    """
    regeneração por ciclo (10 min) = base × (1 + modificador de QoL), modificador em [-10%, +10%].
    Usa a QoL Base EFETIVA, não a Atual (04 §2.3). Exemplo do 04 §25: 5,00 base, QoL +5% => 5,25.
    A relação QoL -> modificador é calibrável (04 §27): aqui, linear em torno de qol_neutral_point.
    """
    effective = qol_base_effective(player, at, bal)
    cap = bal.energy_regen_modifier_cap
    modifier = (Calc("qol_delta", effective.value - bal.qol_neutral_point, detail=effective)
                .mul("sensitivity", bal.energy_regen_qol_sensitivity)
                .floor("modifier_min", -cap).cap("modifier_max", cap)
                .result(at))
    return (Calc("regen_base", bal.energy_regen_per_cycle)
            .mul("qol_modifier", 1 + modifier.value, detail=modifier)
            .floor("regen_floor", 0)
            .result(at))


# --- Burnout (04 §7) --------------------------------------------------------

def update_burnout_active(player: Player, bal: Balance) -> None:
    """Histerese: entra com Burnout = 100; só sai com Burnout <= 50 (04 §7.3)."""
    if not player.burnout_active and player.burnout >= bal.burnout_active_enter:
        player.burnout_active = True
    elif player.burnout_active and player.burnout <= bal.burnout_active_exit:
        player.burnout_active = False


def burnout_change(action: Action, risk: Decimal, bal: Balance) -> Explained:
    """
    Trabalhar +5, Estudar +3, Lazer -10 (04 §7.1). `risk` = multiplicador de risco (1 = 100%):
    efeitos como o do Advogado (02 §9.2) o reduzem, nunca abaixo de `burnout_risk_floor` (1%).
    O risco só modula GANHOS; a redução do Lazer não é afetada.
    """
    if action is Action.LEISURE:
        return Calc("leisure_change", bal.burnout_change_leisure).result()
    base = bal.burnout_gain_work if action is Action.WORK else bal.burnout_gain_study
    risk_ex = Calc("risk", risk).floor("risk_floor", bal.burnout_risk_floor).result()
    return Calc("action_gain", base).mul("risk", risk_ex.value, detail=risk_ex).result()


def apply_burnout_change(player: Player, delta: Decimal, bal: Balance) -> None:
    player.burnout = q(clamp(player.burnout + delta, Decimal(0), bal.burnout_max))
    update_burnout_active(player, bal)


def apply_burnout_recovery(player: Player, at: int, bal: Balance) -> None:
    """-5 por ciclo, mas só depois de 1 h sem trabalhar (04 §7.2). Continua valendo em Burnout Ativo (§7.3)."""
    waited = player.last_work_at is None or at - player.last_work_at >= bal.burnout_recovery_wait_seconds
    if waited and player.burnout > 0:
        apply_burnout_change(player, -bal.burnout_recovery_per_cycle, bal)


# --- Saúde (04 §10-14) ------------------------------------------------------

_regional_providers: Dict[str, Callable[[Player, int], Optional[Decimal]]] = {}


def register_regional_recovery_provider(name: str, fn: Callable[[Player, int], Optional[Decimal]]) -> None:
    """
    Recuperação Regional (04 §11): vem do sistema de saúde/médicos da região, consolidada no Daily Tick.
    Esse sistema ainda não existe; quando existir, registra aqui. Enquanto isso o componente vale 0.
    """
    if name in _regional_providers:
        raise ValueError(f"Provedor de Recuperação Regional duplicado: {name}")
    _regional_providers[name] = fn


def clear_regional_recovery_providers() -> None:  # para testes
    _regional_providers.clear()


def health_change(player: Player, at: int, bal: Balance) -> Explained:
    """
    variação de Saúde por ciclo = Recuperação Regional + 5 - Penalidades (04 §10); pode ser negativa.
    Lê o estado do INÍCIO do ciclo (04 §23). A penalidade de Nutrição é calibrável (§17, §27).
    """
    regional = sum((fn(player, at) or Decimal(0) for _, fn in sorted(_regional_providers.items())), Decimal(0))
    calc = (Calc("base_recovery", bal.health_base_recovery_per_cycle)
            .add("regional_recovery", regional)
            .add("penalty:nutrition", -bal.health_nutrition_penalty_max * (1 - player.nutrition / bal.nutrition_max)))
    if player.burnout_active:
        calc.add("penalty:burnout", -bal.health_burnout_penalty)
    return calc.result(at)


def update_health_flags(player: Player, at: int, bal: Balance) -> None:
    """
    Saúde Crítica com histerese: entra com Saúde <= 20; só sai com Saúde > 30 (04 §12).
    Hospitalização: Saúde = 0 (04 §14), estado distinto da Saúde Crítica.
    """
    if not player.health_critical and player.health <= bal.health_critical_enter:
        player.health_critical = True
    elif player.health_critical and player.health > bal.health_critical_exit:
        player.health_critical = False
    if player.hospitalized_until is not None and at >= player.hospitalized_until:
        player.hospitalized_until = None
    if player.health == 0 and not player.is_hospitalized(at):
        player.hospitalized_until = at + bal.hospitalization_duration_seconds


def apply_health_change(player: Player, delta: Decimal, at: int, bal: Balance) -> None:
    player.health = q(clamp(player.health + delta, Decimal(0), bal.health_max))
    update_health_flags(player, at, bal)


# --- Nutrição (04 §15) ------------------------------------------------------

def apply_food(player: Player, nutrition_gain: Decimal, bal: Balance) -> None:
    player.nutrition = q(min(bal.nutrition_max, player.nutrition + nutrition_gain))


# --- Ciclo de 10 minutos de jogo (04 §2.3, §7.2, §10, §23) -----------------

def advance_cycle(player: Player, at: int, bal: Balance) -> None:
    """
    Um ciclo. Ordem do 04 §23: "estado no início do período -> calcula Saúde -> calcula QoL com base
    no novo estado -> consolida", sem recalcular em cadeia.

      1. Saúde      a partir do estado do INÍCIO (Nutrição e Burnout Ativo anteriores)
      2. Burnout    recuperação natural + histerese
      3. Nutrição   alteração temporal (calibrável; lazy)
      4. Energia    regenera usando a QoL Base efetiva do NOVO estado (Burnout Ativo já atualizado)
    """
    apply_health_change(player, health_change(player, at, bal).value, at, bal)
    apply_burnout_recovery(player, at, bal)
    player.nutrition = q(max(Decimal(0), player.nutrition - bal.nutrition_decay_per_cycle))
    player.energy = q(min(bal.energy_max, player.energy + energy_regen(player, at, bal).value))
