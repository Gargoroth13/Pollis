"""
Parâmetros de Skills (design/01, status REVIEW).

Categorias, deliberadamente separadas (mesmo padrão de players/balance.py):

  [01]/[02] valor ou regra DEFINIDO no documento.
  [PROV]    valor NUMÉRICO provisório: o documento manda parametrizar e calibrar com os Bots, mas o
            sistema precisa de um número para rodar. NÃO é decisão de design; fica listado em
            CHANGELOG_DEV.md, junto com sugestões, e é sobrescrevível sem mexer em código.
  [ABERTO]  DECISÃO DE DESIGN não fechada (o 01 §2 a lista como aberta). Fica como configuração, com o
            padrão mais neutro possível, e NUNCA como regra definitiva.

Sobrescrever: settings.POLIS_SKILLS_BALANCE = {"initial_level": 10, "base_gain": {"work": {"physical": "0.4"}}}
(`base_gain` é mesclado por atividade e skill).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields, replace
from decimal import Decimal
from typing import Dict

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.breakdown import D
from . import curves
from .constants import SKILL_NAMES


def _default_base_gain() -> Dict[str, Dict[str, Decimal]]:
    return {
        # [PROV] 01 §1.3 só dá "ganho base 1.0" como EXEMPLO conceitual; aqui 1 é apenas a unidade de referência.
        "study": {s: D(1) for s in sorted(SKILL_NAMES)},
        # [PROV] 01 §1.2 define só que o ganho do Trabalho é MENOR que o do estudo (validado abaixo); 0,5 é um ponto de partida.
        "work": {s: D("0.5") for s in sorted(SKILL_NAMES)},
        # Lazer: o 01 não define ganho de skill para nenhuma atividade de lazer: sem padrão (informar por atividade).
    }


@dataclass(frozen=True)
class SkillBalance:
    # --- Estado inicial ---------------------------------------------------
    initial_level: Decimal = D(0)                       # [PROV] 01 §1: o nível inicial vem do contexto de nascimento
                                                        #        (sistema de criação ainda inexistente); 0 é o neutro

    # --- Ganho (01 §1.3) --------------------------------------------------
    # ganho_base = QoL_base × qualidade_da_escola × ganho_base_da_atividade   [01 §1.3]
    # Decisões do Game Director (2026-10-02): QoL_base = QoL Base ESTRUTURAL (não a efetiva nem a Atual);
    # a qualidade da escola só entra em atividades educacionais (nas demais o fator é 1).
    base_gain: Dict[str, Dict[str, Decimal]] = field(default_factory=_default_base_gain)  # [PROV] por atividade e skill
    progress_curve: str = "none"                        # [ABERTO] 01 §1.5: fórmula do diminishing returns NÃO fechada ("none" = fator 1)

    # --- Produção e salário (01 §1.6-1.7) ---------------------------------
    production_curve: str = "none"                      # [ABERTO] 01 §1.6: relação skill -> produção NÃO definida
    salary_cap_multiplier: Decimal = D("1.5")           # [PROV] 01 §1.7: "multiplicador atual considerado"; §2: NÃO definitivo
                                                        #        (pode virar parâmetro de lei)

    # --- Especialização (02 §13) ------------------------------------------
    specialization_floor_ratio: Decimal = D("0.5")      # [02 §13] não cai abaixo de 50% do maior valor histórico
    specialization_recovery_multiplier: Decimal = D("1.5")  # [02 §13] recuperação a 1,5× a velocidade normal
    specialization_gain_per_work: Decimal = D(1)        # [PROV] 02 §13: "valores exatos de ganho ... balanceamento"
    specialization_decay_per_day: Decimal = D("0.1")    # [PROV] 02 §13: "decadência diária baixa"; a FORMA (pontos/dia) é suposição

    def validate(self) -> "SkillBalance":
        e = []
        if self.initial_level < 0:
            e.append("initial_level não pode ser negativo")
        for activity, per_skill in self.base_gain.items():
            if not set(per_skill) <= SKILL_NAMES:
                e.append(f"base_gain[{activity}] tem skill desconhecida: {sorted(set(per_skill) - SKILL_NAMES)}")
            if any(v < 0 for v in per_skill.values()):
                e.append(f"base_gain[{activity}] não pode ter ganho negativo")
        work, study = self.base_gain.get("work", {}), self.base_gain.get("study", {})
        for skill in set(work) & set(study):
            if not work[skill] < study[skill]:
                e.append(f"01 §1.2: o ganho do Trabalho deve ser MENOR que o do Estudo ({skill})")
        if self.progress_curve not in curves.progress_curve_names():
            e.append(f"progress_curve desconhecida: {self.progress_curve}")
        if self.production_curve not in curves.production_curve_names():
            e.append(f"production_curve desconhecida: {self.production_curve}")
        if self.salary_cap_multiplier < 0:
            e.append("salary_cap_multiplier não pode ser negativo")
        if not 0 <= self.specialization_floor_ratio <= 1:
            e.append("specialization_floor_ratio deve estar em [0, 1]")
        if self.specialization_recovery_multiplier < 1:
            e.append("specialization_recovery_multiplier deve ser >= 1 (02 §13: recuperação MAIS rápida)")
        if self.specialization_gain_per_work < 0 or self.specialization_decay_per_day < 0:
            e.append("ganho/decadência de especialização não podem ser negativos")
        if e:
            raise ImproperlyConfigured("POLIS_SKILLS_BALANCE inválido: " + "; ".join(e))
        return self


_FIELDS = {f.name for f in fields(SkillBalance)}


def get_skill_balance() -> SkillBalance:
    """Padrão + sobrescritas de settings.POLIS_SKILLS_BALANCE, validado a cada chamada."""
    overrides = getattr(settings, "POLIS_SKILLS_BALANCE", None) or {}
    unknown = set(overrides) - _FIELDS
    if unknown:
        raise ImproperlyConfigured(f"POLIS_SKILLS_BALANCE tem chaves desconhecidas: {sorted(unknown)}")
    changes = {}
    for key, value in overrides.items():
        if key == "base_gain":
            merged = deepcopy(_default_base_gain())
            for activity, per_skill in value.items():
                merged.setdefault(activity, {}).update({k: D(str(v) if isinstance(v, float) else v) for k, v in per_skill.items()})
            changes[key] = merged
        elif key in ("progress_curve", "production_curve"):
            changes[key] = value
        else:
            changes[key] = D(str(v) if isinstance((v := value), float) else v)
    return replace(SkillBalance(), **changes).validate()
