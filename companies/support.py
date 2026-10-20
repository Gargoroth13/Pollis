"""
Cargos de suporte (design/02 §9): Engenheiro e Advogado.

Os dois trabalham (consomem Energia, recebem o salário do cargo, desenvolvem a skill relevante) e cada trabalho soma uma
contribuição ao efeito DIÁRIO da empresa (§9.1-9.2: "o bônus/efeito é diário e é reiniciado a cada novo ciclo diário"):

  - **Engenheiro** → bônus de eficiência produtiva do dia: a produção por trabalho dos funcionários de produção é multiplicada por
    `1 + bônus do dia` (`production.produce_on_work`). O §9.1 não põe teto artificial: o limite é estrutural (estrela × nº de
    Engenheiros × Energia).
  - **Advogado** → multiplicador de risco de Burnout dos funcionários da empresa (`1 − redução do dia`; piso de 1% aplicado por
    `players.rules`, §9.2), sobre os ganhos de Trabalhar e Estudar (não sobre o Lazer). Provedor registrado em `players.hooks`: vale
    para jogadores reais e Bots pelo mesmo caminho e aparece no detalhamento do Burnout da ação (20).

Cada contribuição é um `SupportWork` imutável; o efeito do dia é a SOMA por (empresa, cargo, dia): reinicia sozinho no dia seguinte.
`contribution = base × fator de skill × fator de especialização` (mesma curva `[PROV]` da produção; números em `params`).

Quem se beneficia do Advogado: os OCUPANTES de cargos da empresa que não são o Dono (os "funcionários", 02 §9.2; o Dono não é um
emprego contratado, §16) — `[PROV]`, registrado em CHANGELOG_DEV. O efeito do dia vale para as ações que acontecem depois da
contribuição (a ordem das ações dentro do dia importa; a própria ação do Advogado usa o efeito acumulado até então).

PROTOCOLO: o hook roda com o jogador travado e trava a empresa (como os demais hooks de Trabalho) antes de gravar.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from django.db.models import Count, Sum

from core.breakdown import Calc, Explained
from ledger.money import competence_day_of
from players.actions import Action
from players.hooks import ActionHookContext, register_action_hook, register_burnout_risk_provider
from players.models import Player
from skills.services import get_levels, specialization_value

from . import params, production
from .constants import SUPPORT_POSITION_KINDS, PositionKind
from .jobs import current_job, relevant_skill
from .models import Company, SupportWork, WorkWage

SUPPORT_VALUES = SUPPORT_POSITION_KINDS
ACTION_HOOK = "companies_support"
RISK_PROVIDER = "companies_lawyer"
_BASE = {PositionKind.ENGINEER.value: params.ENGINEER_BONUS_PER_WORK, PositionKind.LAWYER.value: params.LAWYER_REDUCTION_PER_WORK}


def specialization_key_of(kind: str, company_id: int, now: int) -> Optional[str]:
    """Especialização do cargo de suporte (02 §13): o Engenheiro, no produto da empresa; o Advogado, na própria atividade `[PROV]`."""
    if kind == PositionKind.ENGINEER.value:
        return production.active_product_key(company_id, now)
    if kind == PositionKind.LAWYER.value:
        return params.LAWYER_SPECIALIZATION_KEY
    return None


def contribution_of(kind: str, level: Decimal, specialization: Decimal, at: Optional[int] = None) -> Explained:
    """Contribuição de UM trabalho ao efeito do dia (02 §9), com os fatores (20)."""
    skill = production.skill_factor(level, at)
    return (Calc(f"{kind}_base_per_work", _BASE[kind])
            .mul("skill_effect", skill.value, detail=skill)
            .mul("specialization_effect", 1 + Decimal(specialization) * params.SPECIALIZATION_PRODUCTION_PER_POINT)
            .result(at))


def daily_total(company_id: int, kind: str, day: int) -> Dict[str, Any]:
    """Soma do dia da empresa para o cargo: {"works": n, "total": Decimal}."""
    agg = SupportWork.objects.filter(company_id=company_id, kind=kind, competence_day=day).aggregate(n=Count("id"), total=Sum("contribution"))
    return {"works": agg["n"] or 0, "total": agg["total"] or Decimal(0)}


def engineering_bonus(company_id: int, now: int) -> Explained:
    """Bônus de produção do dia: `total` do Engenheiro (0 sem trabalho). O multiplicador da produção é `1 + valor`."""
    day = competence_day_of(now)
    d = daily_total(company_id, PositionKind.ENGINEER.value, day)
    return (Calc("engineering_bonus_base", 0).add("engineer_works_today", d["total"]).result(now)
            if d["works"] else Calc("engineering_bonus_base", 0).result(now))


def lawyer_risk(company_id: int, now: int) -> Optional[Explained]:
    """Multiplicador de risco de Burnout do dia (1 − redução); None se nenhum Advogado trabalhou hoje. O piso de 1% é de `players`."""
    day = competence_day_of(now)
    d = daily_total(company_id, PositionKind.LAWYER.value, day)
    if not d["works"]:
        return None
    return Calc("burnout_risk_base", 1).add("lawyer_reduction_today", -d["total"]).result(now)


def status_of(company_id: int, now: int) -> Dict[str, Any]:
    """Estado dos cargos de suporte da empresa no dia (20)."""
    day = competence_day_of(now)
    return {"day": day, "engineer": daily_total(company_id, PositionKind.ENGINEER.value, day),
            "lawyer": daily_total(company_id, PositionKind.LAWYER.value, day),
            "engineering_bonus": engineering_bonus(company_id, now), "burnout_risk": lawyer_risk(company_id, now)}


def risk_provider(player: Player, action: Action, now: int) -> Optional[Explained]:
    """Provedor de risco de Burnout (players.hooks): o Advogado reduz Trabalhar e Estudar dos funcionários da empresa."""
    if action not in (Action.WORK, Action.STUDY):
        return None
    job = current_job(player.pk)
    if job is None:
        return None
    return lawyer_risk(job.company_id, now)


def record_support_work(ctx: ActionHookContext) -> Optional[Dict[str, Any]]:
    """Hook de `perform_action`: o Trabalho de Engenheiro/Advogado registra a contribuição do dia."""
    if ctx.action is not Action.WORK:
        return None
    player_id = ctx.player.pk
    job = current_job(player_id)
    if job is None or job.kind not in SUPPORT_VALUES:
        return None
    Company.objects.select_for_update().get(pk=job.company_id)                              # protocolo: jogador → empresa
    level = get_levels(player_id)[relevant_skill(job.kind)]
    key = specialization_key_of(job.kind, job.company_id, ctx.now)
    spec = specialization_value(player_id, key) if key else Decimal(0)
    contribution = contribution_of(job.kind, level, spec, ctx.now)
    sequence = WorkWage.objects.filter(player_id=player_id).count() + 1                     # o MESMO nº do salário desta ação
    work = SupportWork.objects.create(
        company_id=job.company_id, player_id=player_id, position=job, kind=job.kind, sequence=sequence,
        competence_day=competence_day_of(ctx.now), at=ctx.now, level=level, specialization=spec,
        contribution=contribution.value, explained=contribution.to_dict())
    return {"company": job.company_id, "kind": job.kind, "contribution": contribution, "support_work": work.pk,
            "day": work.competence_day}


def register() -> None:
    register_action_hook(ACTION_HOOK, record_support_work)
    register_burnout_risk_provider(RISK_PROVIDER, risk_provider)
