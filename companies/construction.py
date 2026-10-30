"""
Construtora: a obra (design/02 §12; 10 §5-6, §28).

  - **Uma obra ativa por vez**, escolhida e iniciada só pelo Dono (§12). O projeto é um tipo de imóvel residencial com a Construtora
    mínima de `10` §6 (estrela). Índice único parcial no banco: nunca duas ativas.
  - **Cada Trabalhar de funcionário de produção da Construtora faz a obra andar** em percentual (0% → 100%): `100 / trabalhos do
    projeto × skill (Físico) × especialização (no projeto) × (1 + bônus diário do Engenheiro)` (§12 lista skill, especialização,
    Engenheiro; a quantidade de funcionários já pesa por somarem trabalhos). Sem obra ativa o Trabalho é BLOQUEADO antes de gastar
    Energia (como a produção sem produto escolhido); a sobra além de 100% se perde (a obra acaba).
  - **Conclusão**: com 100% a obra termina e a Construtora pode iniciar outra. O imóvel, o lote e a propriedade (10 §28: a Construtora
    é prestadora, não recebe o imóvel) são de Imóveis (P1.07) e do contrato com o dono do lote (P1.07/P1.09/18): esta camada só
    expõe `register_completion_hook` e grava a conclusão. Nada de dinheiro aqui; o pagamento da obra é do contrato.
  - Não há cancelamento nem abandono de obra no design (lacuna registrada em CHANGELOG_DEV).
  - Materiais de obra (G5, GD 2026-10-29): consumo CONFIGURÁVEL (`params.CONSTRUCTION_CONSUMES_MATERIALS`/`CONSTRUCTION_MATERIALS_PER_WORK`; o design não define
    quantidades, 02 §10, então a tabela nasce vazia); custo real e preços: P1.05b.

PROTOCOLO: jogador → empresa (serializa a obra e o progresso) → registro monetário (o salário, depois).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from django.db import transaction

from core import clock as game_clock
from core.breakdown import Calc, Explained
from players.actions import Action
from players.hooks import ActionHookContext, register_action_hook, register_block_provider
from players.models import Player
from players.services import ActionResult
from skills.services import get_levels, specialization_value

from catalog import services as catalog

from . import params, production, stock, support
from .constants import CompanyType, PositionKind, ProjectStatus, StockOperation
from .jobs import current_job, relevant_skill
from .models import Company, ConstructionJob, ConstructionWork, StockItem, WorkWage
from .services import owner_of

BLOCK_PROVIDER = "companies_construction"
ACTION_HOOK = "companies_construction"
_INT64 = 2 ** 63
_Q = Decimal("0.000001")

CompletionHook = Callable[[ConstructionJob], None]
_completion_hooks: Dict[str, CompletionHook] = {}


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def register_completion_hook(name: str, fn: CompletionHook) -> None:
    """Imóveis (P1.07) reage à obra concluída, na MESMA transação do Trabalhar que a concluiu."""
    if name in _completion_hooks:
        raise ValueError(f"Hook de conclusão de obra duplicado: {name}")
    _completion_hooks[name] = fn


def unregister_completion_hook(name: str) -> None:   # para testes
    _completion_hooks.pop(name, None)


StartValidator = Callable[[int, int, str, Any], Optional[ActionResult]]
StartHook = Callable[[ConstructionJob, Any], None]
_start_validators: Dict[str, StartValidator] = {}
_start_hooks: Dict[str, StartHook] = {}


def register_start_validator(name: str, fn: StartValidator) -> None:
    """Imóveis (P1.07) valida o lote da obra (`fn(player_id, company_id, project_key, lot_id)`: recusa ou None). Só LÊ."""
    if name in _start_validators:
        raise ValueError(f"Validador de início de obra duplicado: {name}")
    _start_validators[name] = fn


def unregister_start_validator(name: str) -> None:   # para testes
    _start_validators.pop(name, None)


def register_start_hook(name: str, fn: StartHook) -> None:
    """Imóveis (P1.07) liga a obra recém-criada ao lote (`fn(job, lot_id)`), na MESMA transação de `start_construction`."""
    if name in _start_hooks:
        raise ValueError(f"Hook de início de obra duplicado: {name}")
    _start_hooks[name] = fn


def unregister_start_hook(name: str) -> None:        # para testes
    _start_hooks.pop(name, None)


def active_job(company_id: int) -> Optional[ConstructionJob]:
    return ConstructionJob.objects.filter(company_id=company_id, status=ProjectStatus.ACTIVE.value).first()


def specialization_key_of(project: str) -> str:
    return f"construction:{project}"


def active_project_key(company_id: int) -> Optional[str]:
    job = active_job(company_id)
    return job.project if job is not None else None


def progress_per_work(project_key: str, level: Decimal, specialization: Decimal, bonus: Optional[Explained] = None,
                      at: Optional[int] = None) -> Explained:
    """Pontos percentuais por trabalho, com os fatores (20)."""
    project = params.CONSTRUCTION_PROJECTS[project_key]
    skill = production.skill_factor(level, at)
    return (Calc("progress_base_per_work", Decimal(100) / project.work_units)
            .mul("skill_production", skill.value, detail=skill)
            .mul("specialization_production", 1 + Decimal(specialization) * params.SPECIALIZATION_PRODUCTION_PER_POINT)
            .mul("engineering_bonus", 1 + (Decimal(0) if bonus is None else bonus.value), detail=bonus)
            .result(at))


def projects() -> List[Dict[str, Any]]:
    return [{"project": p.key, "name": p.name, "min_stars": p.min_stars, "work_units": p.work_units}
            for p in params.CONSTRUCTION_PROJECTS.values()]


# --- iniciar a obra -----------------------------------------------------------------------------------------------------

def start_refusal(player_id: int, company_id: Any, project_key: Any, lot_id: Any = None) -> Optional[ActionResult]:
    """Recusas que só LEEM (a execução usa as mesmas). `lot_id` (opcional): o lote da obra, validado por Imóveis (P1.07)."""
    if isinstance(company_id, bool) or not isinstance(company_id, int) or not -_INT64 <= company_id < _INT64:
        return _refuse("INVALID_PARAMS", company=repr(company_id)[:40])
    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return _refuse("COMPANY_NOT_FOUND", company=company_id)
    if owner_of(company_id) != player_id:
        return _refuse("NOT_OWNER", company=company_id)
    if CompanyType(company.type) is not CompanyType.CONSTRUCTION:
        return _refuse("COMPANY_TYPE_CANNOT_BUILD", company_type=company.type)
    if not isinstance(project_key, str):
        return _refuse("INVALID_PARAMS", why="project deve ser texto")
    project = params.CONSTRUCTION_PROJECTS.get(project_key)
    if project is None:
        return _refuse("UNKNOWN_PROJECT", project=project_key[:60], allowed=sorted(params.CONSTRUCTION_PROJECTS))
    if company.stars < project.min_stars:
        return _refuse("STARS_TOO_LOW", project=project_key, required=project.min_stars, stars=company.stars)
    current = active_job(company_id)
    if current is not None:
        return _refuse("CONSTRUCTION_ACTIVE", project=current.project, progress=str(current.progress))
    if lot_id is not None:
        if not _start_validators:
            return _refuse("LOT_NOT_SUPPORTED", why="o sistema de Imóveis não está ativo")
        for name in sorted(_start_validators):
            refusal = _start_validators[name](player_id, company_id, project_key, lot_id)
            if refusal is not None:
                return refusal
    return None


def start_construction(player_id: int, company_id: Any, project_key: Any, lot_id: Any = None) -> ActionResult:
    """
    O Dono escolhe e inicia a obra (02 §12). `lot_id` opcional: com ele a obra tem lote (10 §5, §28) e a conclusão gera o imóvel;
    sem ele a obra é a "obra sem lote" do P1.04e (lacuna registrada: não gera imóvel). Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS,
    COMPANY_NOT_FOUND, NOT_OWNER, COMPANY_TYPE_CANNOT_BUILD, UNKNOWN_PROJECT, STARS_TOO_LOW, CONSTRUCTION_ACTIVE, LOT_NOT_SUPPORTED
    e as do lote (Imóveis).
    """
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    with transaction.atomic():
        Player.objects.select_for_update().filter(pk=player_id).first()                      # protocolo: jogador → empresa
        if isinstance(company_id, int) and not isinstance(company_id, bool) and -_INT64 <= company_id < _INT64:
            Company.objects.select_for_update().filter(pk=company_id).first()
        refusal = start_refusal(player_id, company_id, project_key, lot_id)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        sequence = ConstructionJob.objects.filter(company_id=company_id).count() + 1
        job = ConstructionJob.objects.create(company_id=company_id, sequence=sequence, project=project_key,
                                             status=ProjectStatus.ACTIVE.value, progress=0, started_at=now, actor=player_id)
        if lot_id is not None:
            for name in sorted(_start_hooks):
                _start_hooks[name](job, lot_id)
        project = params.CONSTRUCTION_PROJECTS[project_key]
        return ActionResult(True, "OK", {"job": job.pk, "company": company_id, "project": project_key, "name": project.name,
                                         "sequence": sequence, "work_units": project.work_units, "lot": lot_id})


def status_of(company_id: int, now: Optional[int] = None) -> Dict[str, Any]:
    now = game_clock.now() if now is None else now
    job = active_job(company_id)
    last = ConstructionJob.objects.filter(company_id=company_id).order_by("-sequence").first()
    return {"company": company_id, "active": None if job is None else {"project": job.project, "progress": job.progress,
                                                                       "started_at": job.started_at},
            "last_completed": (last.project if last is not None and last.status == ProjectStatus.COMPLETED.value else None),
            "engineering_bonus": support.engineering_bonus(company_id, now)}


# --- o Trabalho constrói --------------------------------------------------------------------------------------------------

def _builder_job(player_id: int):
    job = current_job(player_id)
    if (job is None or job.kind != PositionKind.WORKER.value or CompanyType(job.company.type) is not CompanyType.CONSTRUCTION):
        return None
    return job


def materials_per_work(project_key: str) -> Dict[str, int]:
    """Unidades por Trabalhar do projeto (configuráveis, G5); vazio quando o consumo está desligado ou o projeto não tem linha na tabela."""
    if not params.CONSTRUCTION_CONSUMES_MATERIALS:
        return {}
    return {k: v for k, v in params.CONSTRUCTION_MATERIALS_PER_WORK.get(project_key, {}).items() if v > 0}


def _missing_materials(company_id: int, project_key: str) -> Dict[str, Dict[str, int]]:
    need = materials_per_work(project_key)
    if not need:
        return {}
    have = {k: 0 for k in need}
    for row in StockItem.objects.filter(company_id=company_id, product__key__in=list(need)).select_related("product"):
        have[row.product.key] = row.quantity
    return {k: {"required": q, "have": have[k]} for k, q in need.items() if have[k] < q}


def block_provider(player: Player, action: Action, now: int, activity) -> Optional[str]:
    if action is not Action.WORK:
        return None
    job = _builder_job(player.pk)
    if job is None:
        return None
    obra = active_job(job.company_id)
    if obra is None:
        return "COMPANY_NO_PROJECT"
    return "CONSTRUCTION_NO_MATERIALS" if _missing_materials(job.company_id, obra.project) else None


def build_on_work(ctx: ActionHookContext) -> Optional[Dict[str, Any]]:
    """Hook de `perform_action`: o Trabalho de um funcionário da Construtora faz a obra andar."""
    if ctx.action is not Action.WORK:
        return None
    player_id = ctx.player.pk
    job = _builder_job(player_id)
    if job is None:
        return None
    Company.objects.select_for_update().get(pk=job.company_id)                              # protocolo: jogador → empresa
    obra = ConstructionJob.objects.select_for_update().filter(company_id=job.company_id, status=ProjectStatus.ACTIVE.value).first()
    if obra is None:
        return {"company": job.company_id, "progress_added": 0, "limited_by": ["COMPANY_NO_PROJECT"]}
    missing = _missing_materials(job.company_id, obra.project)
    if missing:
        return {"company": job.company_id, "project": obra.project, "progress_added": 0, "limited_by": ["CONSTRUCTION_NO_MATERIALS"], "missing": missing}
    level = get_levels(player_id)[relevant_skill(PositionKind.WORKER)]
    spec = specialization_value(player_id, specialization_key_of(obra.project))
    gain = progress_per_work(obra.project, level, spec, support.engineering_bonus(job.company_id, ctx.now), ctx.now)
    before = obra.progress
    after = min(Decimal(100), (before + gain.value).quantize(_Q))
    added = after - before
    sequence = WorkWage.objects.filter(player_id=player_id).count() + 1                      # o MESMO nº do salário desta ação
    consumed = {}
    company_row = Company.objects.get(pk=job.company_id)
    for product_key, quantity in sorted(materials_per_work(obra.project).items()):               # G5: materiais configuráveis, pela trilha imutável de estoque
        moved = stock.apply_locked(company_row, catalog.get_product(product_key), -quantity, StockOperation.INPUT_CONSUMPTION, origin=f"company:{job.company_id}",
                                   destination="construction", key=f"construction:{obra.pk}:work:{sequence}:{player_id}:{product_key}",
                                   reference_kind="construction_work", reference_id=f"{obra.pk}:{sequence}", at=ctx.now, actor=player_id)
        if not moved.ok:                                                                          # impossível: a empresa está travada desde a checagem
            raise RuntimeError(f"estoque de materiais da obra mudou sob a trava da empresa: {moved.code} {moved.detail}")
        consumed[product_key] = quantity
    ConstructionWork.objects.create(job=obra, player_id=player_id, sequence=sequence, at=ctx.now, progress_added=added,
                                    progress_after=after, explained={**gain.to_dict(), "materials_consumed": consumed} if consumed else gain.to_dict())
    obra.progress = after
    completed = after >= 100
    if completed:
        obra.status, obra.completed_at = ProjectStatus.COMPLETED.value, ctx.now
    obra.save(update_fields=["progress", "status", "completed_at"])
    if completed:
        for name in sorted(_completion_hooks):
            _completion_hooks[name](obra)
    return {"company": job.company_id, "project": obra.project, "progress_added": added, "progress": after, "completed": completed,
            "per_work": gain}


def register() -> None:
    register_block_provider(BLOCK_PROVIDER, block_provider)
    register_action_hook(ACTION_HOOK, build_on_work)
