"""
Regras de Skills (design/01 REVIEW; Especialização: 02 §13 FINAL). Funções PURAS: não tocam o banco.

O que é regra aqui é só o que o design JÁ definiu. Os pontos que ele deixa em aberto ficam em
skills/curves.py (diminishing returns, skill -> produção) e em skills/balance.py (valores).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Mapping, Optional, Tuple, Union

from core.breakdown import Calc, Explained, D
from core.timeline import local_dt
from players.rules import q
from . import curves
from .balance import SkillBalance
from .constants import SKILLS, Skill

SkillKey = Union[Skill, str]


def as_skill(key: SkillKey) -> Skill:
    try:
        return key if isinstance(key, Skill) else Skill(key)
    except ValueError:
        raise ValueError(f"Skill desconhecida: {key!r}. Existem exatamente 3: {[s.value for s in SKILLS]}") from None


# --- Ganho (01 §1.3, §1.5) -------------------------------------------------

def skill_gain(base_gain: Decimal, qol: Explained, school_quality: Decimal, level: Decimal,
               bal: SkillBalance, at: Optional[int] = None) -> Explained:
    """
    ganho = ganho_base_da_atividade × QoL_base × qualidade_da_escola × diminishing_returns(nível)   (01 §1.3, §1.5)

    O diminishing returns usa o nível ATUAL da skill que está crescendo. A curva é plugável e o padrão
    ("none") vale 1: o 01 diz que a fórmula "ainda não está fechada" e que "não deve ser tratada como definitiva".
    Sem teto: nada aqui limita o nível resultante.
    """
    dr = curves.progress_curve(bal.progress_curve)(level)
    if dr.value <= 0:
        raise ValueError(f"A curva '{bal.progress_curve}' devolveu fator <= 0 ({dr.value}): a skill pararia de crescer.")
    return (Calc("activity_base_gain", base_gain)
            .mul("qol_base", qol.value, detail=qol)
            .mul("school_quality", school_quality)
            .mul("diminishing_returns", dr.value, detail=dr)
            .result(at))


# --- Requisitos (01 §1.9) --------------------------------------------------

@dataclass(frozen=True)
class RequirementDetail:
    skill: Skill
    required: Decimal
    current: Decimal
    met: bool
    shortfall: Decimal  # quanto falta (0 se atendido)


@dataclass(frozen=True)
class RequirementCheck:
    met: bool
    details: Tuple[RequirementDetail, ...]

    def to_dict(self) -> Dict:
        return {"met": self.met, "details": [
            {"skill": d.skill.value, "required": str(d.required), "current": str(d.current),
             "met": d.met, "shortfall": str(d.shortfall)} for d in self.details]}


@dataclass(frozen=True)
class SkillRequirement:
    """
    Nível mínimo de uma OU MAIS skills, todas exigidas (01 §1.9: "INT ≥ 100, FIS ≥ 75").
    Para ser reutilizado pelo sistema de requisitos de cargos (Empresas) e por outras atividades.
    """
    minimums: Tuple[Tuple[Skill, Decimal], ...]

    @classmethod
    def of(cls, minimums: Mapping[SkillKey, Union[int, str, Decimal]]) -> "SkillRequirement":
        parsed: Dict[Skill, Decimal] = {}
        for key, minimum in minimums.items():
            minimum = D(minimum)
            if minimum < 0:
                raise ValueError("O nível mínimo não pode ser negativo.")
            parsed[as_skill(key)] = minimum
        return cls(tuple((s, parsed[s]) for s in SKILLS if s in parsed))  # ordem determinística


def check_requirements(levels: Mapping[Skill, Decimal], requirement: SkillRequirement) -> RequirementCheck:
    details = []
    for skill, required in requirement.minimums:
        current = levels.get(skill, Decimal(0))
        met = current >= required
        details.append(RequirementDetail(skill, required, current, met, max(Decimal(0), required - current)))
    return RequirementCheck(all(d.met for d in details), tuple(details))


# --- Skill como multiplicador de produção e limite salarial (01 §1.6-1.7) --

def production_multiplier(level: Decimal, bal: SkillBalance, at: Optional[int] = None) -> Explained:
    """
    Skill relevante -> eficiência produtiva (01 §1.6). A relação exata NÃO está definida: a curva é plugável
    e o padrão ("none") vale 1. Quem consome (Empresas) multiplica a produção por este valor.
    """
    curve = curves.production_curve(bal.production_curve)(level)
    if curve.value < 0:
        raise ValueError(f"A curva de produção '{bal.production_curve}' devolveu fator negativo ({curve.value}).")
    # O multiplicador É o fator da curva (o nível é só a entrada dela, e fica no detalhamento da curva).
    return Calc("neutral_multiplier", 1).mul("production_curve", curve.value, detail=curve).result(at)


def salary_cap(level: Decimal, bal: SkillBalance, at: Optional[int] = None) -> Explained:
    """
    salário máximo = nível da skill relevante × multiplicador salarial (01 §1.7).
    O multiplicador (1,5) é só o valor "atualmente considerado": NÃO definitivo e talvez político (§1.7, §2).
    O limite é DIÁRIO, com contador de recebido no dia; esse contador pertence ao sistema de pagamento (dinheiro),
    que ainda não existe. Aqui só existe o cálculo do teto.
    """
    return Calc("skill_level", level).mul("salary_multiplier", bal.salary_cap_multiplier).result(at)


# --- Perfil emergente (01 §1.1) --------------------------------------------

@dataclass(frozen=True)
class SpecializationProfile:
    """
    Leitura DESCRITIVA de como as skills se distribuem. O 01 §1.1 diz que a especialização "deve surgir
    naturalmente das atividades escolhidas": não há mecânica nem limiar; isto só torna o resultado observável
    (para a interface, para os Bots e para a calibração de 01 §1.12).
    """
    total: Decimal
    shares: Dict[Skill, Decimal]      # fração do total (0 se total = 0)
    leading: Tuple[Skill, ...]        # skills com o maior nível (vazio se total = 0)


def specialization_profile(levels: Mapping[Skill, Decimal]) -> SpecializationProfile:
    total = sum((levels.get(s, Decimal(0)) for s in SKILLS), Decimal(0))
    shares = {s: (levels.get(s, Decimal(0)) / total if total > 0 else Decimal(0)) for s in SKILLS}
    top = max((levels.get(s, Decimal(0)) for s in SKILLS), default=Decimal(0))
    leading = tuple(s for s in SKILLS if total > 0 and levels.get(s, Decimal(0)) == top)
    return SpecializationProfile(total, shares, leading)


# --- Especialização por atividade/produto (02 §13) ------------------------

def day_index(t: int) -> int:
    """Dia de calendário do jogo (ordinal na time zone do jogo)."""
    return local_dt(t).date().toordinal()


def specialization_floor(historic_max: Decimal, bal: SkillBalance) -> Decimal:
    """02 §13: a especialização não pode cair abaixo de 50% do maior valor histórico atingido."""
    return q(historic_max * bal.specialization_floor_ratio)


def specialization_gain(value: Decimal, historic_max: Decimal, bal: SkillBalance, at: Optional[int] = None) -> Explained:
    """
    Ganho por trabalho. Enquanto a especialização está ABAIXO do seu máximo histórico (voltou a atuar após
    decair), a recuperação é 1,5× a velocidade normal (02 §13). Os valores de ganho são calibráveis.
    """
    calc = Calc("gain_per_work", bal.specialization_gain_per_work)
    recovering = value < historic_max
    calc.mul("recovery_multiplier", bal.specialization_recovery_multiplier if recovering else 1)
    return calc.result(at)


def apply_daily_decay(value: Decimal, historic_max: Decimal, bal: SkillBalance) -> Decimal:
    """Um dia sem uso: decadência, sem nunca ir abaixo do piso (02 §13). Nunca AUMENTA o valor."""
    floor = specialization_floor(historic_max, bal)
    if value <= floor:
        return value
    return q(max(floor, value - bal.specialization_decay_per_day))
