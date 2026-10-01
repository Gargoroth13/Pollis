"""
Parâmetros do estado do jogador (design/04, FINAL — BOT TEST).

Duas categorias, deliberadamente separadas:

  [04]   valor DEFINIDO no documento. Não é decisão minha nem de calibração livre.
  [PROV] parâmetro que o 04 §27 declara CALIBRÁVEL pelo Bot Test e para o qual não há valor.
         O 04 §29.8 pede que permaneçam calibráveis; §27 pede calibrar "com observação de
         comportamento e dados dos Bots em vez de valores arbitrários". Por isso o valor abaixo é só o
         ponto de partida para o sistema rodar, e CADA [PROV] está listado em CHANGELOG_DEV.md.

Sobrescrever sem mexer em código: settings.POLIS_BALANCE = {"nutrition_decay_per_cycle": 1, ...}
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.breakdown import D

_INT_FIELDS = {"burnout_recovery_wait_seconds", "hospitalization_duration_seconds"}


@dataclass(frozen=True)
class Balance:
    # --- Energia (04 §2) --------------------------------------------------
    energy_max: Decimal = D(100)                       # [04 §2.1]
    energy_cost_work: Decimal = D(20)                  # [04 §2.2, §6]
    energy_cost_study: Decimal = D(10)                 # [04 §2.2, §8]
    energy_cost_leisure: Decimal = D(10)               # [04 §2.2, §19]
    energy_regen_per_cycle: Decimal = D(5)             # [04 §2.3] 5 a cada 10 min de jogo
    energy_regen_modifier_cap: Decimal = D("0.10")     # [04 §2.3] modificador de QoL em [-10%, +10%]
    qol_neutral_point: Decimal = D(1)                  # [04 §2.3] QoL = 1,00 => modificador 0%
    energy_regen_qol_sensitivity: Decimal = D(1)       # [PROV 04 §27] relação QoL -> modificador

    # --- QoL (04 §3-4) ----------------------------------------------------
    qol_base_baseline: Decimal = D("0.5")              # [04 §4.1] QoL Base = 0,50 + modificadores estruturais
    burnout_qol_penalty: Decimal = D("0.1")            # [PROV 04 §7.3/§27] penalidade na QoL Base efetiva
    critical_health_qol_debuff: Decimal = D("0.1")     # [PROV 04 §12/§27] debuff na QoL Atual

    # --- Burnout (04 §7) --------------------------------------------------
    burnout_max: Decimal = D(100)                      # [04 §7]
    burnout_gain_work: Decimal = D(5)                  # [04 §7.1]
    burnout_gain_study: Decimal = D(3)                 # [04 §7.1, §8]
    burnout_change_leisure: Decimal = D(-10)           # [04 §7.1, §19]
    burnout_recovery_per_cycle: Decimal = D(5)         # [04 §7.2] -5 a cada 10 min
    burnout_recovery_wait_seconds: int = 3600          # [04 §7.2] só após 1 h sem trabalhar
    burnout_active_enter: Decimal = D(100)             # [04 §7.3] entrada: Burnout = 100
    burnout_active_exit: Decimal = D(50)               # [04 §7.3] saída: Burnout <= 50
    burnout_risk_floor: Decimal = D("0.01")            # [02 §9.2] risco nunca abaixo de 1%

    # --- Saúde (04 §10-14) ------------------------------------------------
    health_max: Decimal = D(100)                       # [04 §10]
    health_initial: Decimal = D(100)                   # [04 §24]
    health_base_recovery_per_cycle: Decimal = D(5)     # [04 §10] "+ 5" a cada 10 min
    health_critical_enter: Decimal = D(20)             # [04 §12] Saúde <= 20
    health_critical_exit: Decimal = D(30)              # [04 §12] Saúde > 30
    health_nutrition_penalty_max: Decimal = D(8)       # [PROV 04 §17/§27] penalidade com Nutrição = 0
    health_burnout_penalty: Decimal = D(0)             # [PROV 04 §10/§27] 0 = "ainda não definida"
    hospitalization_duration_seconds: int = 6 * 3600   # [PROV 04 §14/§27]

    # --- Nutrição (04 §15) ------------------------------------------------
    nutrition_max: Decimal = D(100)                    # [04 §15]
    nutrition_initial: Decimal = D(100)                # [04 §24]
    nutrition_decay_per_cycle: Decimal = D("0.5")      # [PROV 04 §27] "taxa temporal de alteração"

    def validate(self) -> "Balance":
        e = []
        for name in ("energy_max", "health_max", "nutrition_max", "burnout_max"):
            if getattr(self, name) <= 0:
                e.append(f"{name} deve ser > 0")
        for name in ("energy_cost_work", "energy_cost_study", "energy_cost_leisure"):
            if not 0 < getattr(self, name) <= self.energy_max:
                e.append(f"{name} deve estar em (0, energy_max]")
        for name in ("energy_regen_per_cycle", "health_base_recovery_per_cycle", "burnout_recovery_per_cycle",
                     "nutrition_decay_per_cycle", "health_nutrition_penalty_max", "health_burnout_penalty",
                     "burnout_qol_penalty", "critical_health_qol_debuff", "burnout_gain_work",
                     "burnout_gain_study", "energy_regen_qol_sensitivity"):
            if getattr(self, name) < 0:
                e.append(f"{name} não pode ser negativo")
        if not 0 <= self.energy_regen_modifier_cap < 1:
            e.append("energy_regen_modifier_cap deve estar em [0, 1)")
        if not 0 <= self.health_critical_enter < self.health_critical_exit <= self.health_max:
            e.append("histerese da Saúde Crítica: 0 <= enter < exit <= health_max")
        if not 0 <= self.burnout_active_exit < self.burnout_active_enter <= self.burnout_max:
            e.append("histerese do Burnout Ativo: 0 <= exit < enter <= burnout_max")
        if not 0 < self.burnout_risk_floor <= 1:
            e.append("burnout_risk_floor deve estar em (0, 1]")
        if self.burnout_gain_study > self.burnout_gain_work:
            e.append("estudo deve gerar menos burnout que trabalho (04 §7.1)")
        if self.burnout_change_leisure > 0:
            e.append("lazer deve reduzir (ou não alterar) o Burnout (04 §19)")
        if self.burnout_recovery_wait_seconds < 0 or self.hospitalization_duration_seconds <= 0:
            e.append("durações inválidas")
        if not 0 <= self.nutrition_initial <= self.nutrition_max:
            e.append("nutrition_initial fora de 0..nutrition_max")
        if not 0 <= self.health_initial <= self.health_max:
            e.append("health_initial fora de 0..health_max")
        if e:
            raise ImproperlyConfigured("POLIS_BALANCE inválido: " + "; ".join(e))
        return self


_FIELD_NAMES = {f.name for f in fields(Balance)}


def get_balance() -> Balance:
    """Balance padrão + sobrescritas de settings.POLIS_BALANCE (validado a cada chamada)."""
    overrides = getattr(settings, "POLIS_BALANCE", None) or {}
    unknown = set(overrides) - _FIELD_NAMES
    if unknown:
        raise ImproperlyConfigured(f"POLIS_BALANCE tem chaves desconhecidas: {sorted(unknown)}")
    converted = {k: int(v) if k in _INT_FIELDS else D(str(v) if isinstance(v, float) else v)
                 for k, v in overrides.items()}
    return replace(Balance(), **converted).validate()
