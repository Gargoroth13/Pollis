"""
Serviços de Skills.

NÃO existe aqui uma ação de "treinar" nem de "ganhar skill": a skill cresce porque o jogador FEZ uma atividade.
`on_action` é um hook de `players.services.perform_action`, executado na mesma transação e só quando a ação
teve sucesso. Jogadores reais e bots usam, portanto, exatamente a mesma regra (design/21).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from django.db import transaction

from core import clock as game_clock
from core.breakdown import D, Explained
from players import services as player_services
from players.actions import Action
from players.hooks import ActionHookContext
from players.models import Player
from players.qol import qol_base
from players.rules import q

from . import rules
from .balance import SkillBalance, get_skill_balance
from .constants import SKILLS, Skill
from .models import PlayerSkill, Specialization
from .rules import SpecializationProfile, SkillRequirement, RequirementCheck

InitialLevelProvider = Callable[[Player], Mapping[str, Decimal]]
_initial_providers: Dict[str, InitialLevelProvider] = {}


def register_initial_level_provider(name: str, fn: InitialLevelProvider) -> None:
    """
    O nível inicial das skills vem do contexto de nascimento: bairro/faixa de renda (01 §1). Esse sistema de
    criação do jogador ainda não existe; quando existir, registra aqui o ACRÉSCIMO por skill.
    """
    if name in _initial_providers:
        raise ValueError(f"Provedor de nível inicial duplicado: {name}")
    _initial_providers[name] = fn


def clear_initial_level_providers() -> None:  # para testes
    _initial_providers.clear()


# --- criação e leitura -----------------------------------------------------

def ensure_skill_rows(player: Player) -> Dict[Skill, PlayerSkill]:
    """Garante os 3 registros do jogador (nunca mais, nunca menos) e os devolve."""
    existing = {r.skill: r for r in PlayerSkill.objects.filter(player=player)}
    sbal = get_skill_balance()
    rows: Dict[Skill, PlayerSkill] = {}
    for skill in SKILLS:
        row = existing.get(skill.value)
        if row is None:
            level = sbal.initial_level
            for name in sorted(_initial_providers):
                level += D(_initial_providers[name](player).get(skill.value, 0))
            row = PlayerSkill.objects.create(player=player, skill=skill.value, level=q(max(Decimal(0), level)))
        rows[skill] = row
    return rows


def on_player_created(player: Player, now: int) -> None:
    ensure_skill_rows(player)


def get_levels(player_id: int) -> Dict[Skill, Decimal]:
    player = Player.objects.get(pk=player_id)
    return {s: r.level for s, r in ensure_skill_rows(player).items()}


# --- hook de ação ----------------------------------------------------------

def _resolve_skills(ctx: ActionHookContext) -> Tuple[Skill, ...]:
    """
    Quais skills a atividade desenvolve. O jogador NÃO escolhe (01 §1.1): quem define é a atividade.
      - a atividade informa as suas skills (cargo, curso...): vale o que ela informar;
      - Estudar, sem informação: as 3 skills (01 §1.4; 03 §15);
      - Trabalhar/Lazer, sem informação: nenhuma (o cargo / a atividade ainda precisa dizer qual skill é a relevante).
    """
    act = ctx.activity
    if act is not None and act.skills is not None:
        wanted = {rules.as_skill(n) for n in act.skills}
    elif ctx.action is Action.STUDY:
        wanted = set(SKILLS)
    else:
        wanted = set()
    return tuple(s for s in SKILLS if s in wanted)  # ordem determinística


def _base_gain(ctx: ActionHookContext, skill: Skill, sbal: SkillBalance) -> Decimal:
    act = ctx.activity
    if act is not None and act.base_gain is not None and skill.value in act.base_gain:
        gain = D(act.base_gain[skill.value])
    else:
        gain = sbal.base_gain.get(ctx.action.value, {}).get(skill.value)
        if gain is None:
            raise ValueError(
                f"Não há ganho base de {skill.value} para a ação '{ctx.action.value}': o design não o define. "
                f"Informe ActivityContext.base_gain.")
    if gain < 0:
        raise ValueError("O ganho base não pode ser negativo.")
    return gain


def _school_quality(ctx: ActionHookContext) -> Decimal:
    """
    A qualidade da escola só participa de atividades EDUCACIONAIS (hoje, a ação Estudar). Para Trabalho e
    qualquer outra atividade o fator é neutro (1): informar outro valor é erro de quem chama, não é ignorado
    em silêncio.
    """
    requested = D(ctx.activity.school_quality) if ctx.activity is not None else D(1)
    if requested < 0:
        raise ValueError("school_quality não pode ser negativa.")
    if ctx.action is not Action.STUDY:
        if requested != 1:
            raise ValueError("A qualidade da escola só vale para atividades educacionais (Estudar); "
                             "para as demais o fator é neutro (1).")
        return D(1)
    return requested


def _use_specialization(ctx: ActionHookContext, key: str, sbal: SkillBalance) -> Dict[str, Any]:
    if not key or len(key) > 64:
        raise ValueError("specialization_key deve ter de 1 a 64 caracteres.")
    today = rules.day_index(ctx.now)
    row, _ = Specialization.objects.get_or_create(
        player=ctx.player, key=key, defaults={"value": Decimal(0), "historic_max": Decimal(0), "last_used_day": today})
    gain = rules.specialization_gain(row.value, row.historic_max, sbal, ctx.now)
    row.value = q(row.value + gain.value)
    row.historic_max = max(row.historic_max, row.value)
    row.last_used_day = today
    row.save(update_fields=["value", "historic_max", "last_used_day"])
    return {"key": key, "gain": gain, "value": row.value, "historic_max": row.historic_max}


def on_action(ctx: ActionHookContext) -> Optional[Dict[str, Any]]:
    """Hook de players.services.perform_action: skills crescem pela ATIVIDADE (01 §1.1)."""
    sbal = get_skill_balance()
    act = ctx.activity
    skills = _resolve_skills(ctx)
    gains: Dict[str, Any] = {}
    if skills:
        school_quality = _school_quality(ctx)
        # Decisão do Game Director: o ganho usa a QoL BASE ESTRUTURAL, nunca a Base efetiva (Burnout) nem a Atual
        # (buffs/debuffs temporários, Saúde Crítica).
        qol = qol_base(ctx.player, ctx.now, ctx.bal)
        rows = ensure_skill_rows(ctx.player)
        for skill in skills:
            row = rows[skill]
            before = row.level
            explained = rules.skill_gain(_base_gain(ctx, skill, sbal), qol, school_quality, before, sbal, ctx.now)
            row.level = q(before + explained.value)
            row.save(update_fields=["level"])
            gains[skill.value] = {"gain": explained, "level_before": before, "level_after": row.level}
    specialization = None
    if ctx.action is Action.WORK and act is not None and act.specialization_key is not None:
        specialization = _use_specialization(ctx, act.specialization_key, sbal)
    if not gains and specialization is None:
        return None
    return {"gains": gains, "specialization": specialization}


# --- leitura / consultas para outros sistemas -------------------------------

@dataclass(frozen=True)
class SpecializationState:
    value: Decimal
    historic_max: Decimal
    floor: Decimal
    recovering: bool  # abaixo do máximo histórico: ganha a 1,5× (02 §13)


@dataclass(frozen=True)
class SkillSnapshot:
    at: int
    levels: Dict[Skill, Decimal]
    profile: SpecializationProfile
    specializations: Dict[str, SpecializationState]


def get_skill_snapshot(player_id: int) -> SkillSnapshot:
    """Sincroniza o jogador (aplica a decadência diária pendente) e devolve skills, perfil e especializações."""
    with transaction.atomic():
        player = player_services.sync_player(player_id)
        sbal = get_skill_balance()
        levels = {s: r.level for s, r in ensure_skill_rows(player).items()}
        specs = {
            r.key: SpecializationState(r.value, r.historic_max, rules.specialization_floor(r.historic_max, sbal),
                                       r.value < r.historic_max)
            for r in Specialization.objects.filter(player=player).order_by("key")}
    return SkillSnapshot(game_clock.now(), levels, rules.specialization_profile(levels), specs)


def meets_requirements(player_id: int, requirement: SkillRequirement) -> RequirementCheck:
    """Requisito mínimo de skill (01 §1.9) para cargos e atividades. Com detalhamento do que falta."""
    return rules.check_requirements(get_levels(player_id), requirement)


def production_multiplier_for(player_id: int, skill: Skill) -> Explained:
    return rules.production_multiplier(get_levels(player_id)[skill], get_skill_balance(), game_clock.now())


def salary_cap_for(player_id: int, skill: Skill) -> Explained:
    return rules.salary_cap(get_levels(player_id)[skill], get_skill_balance(), game_clock.now())
