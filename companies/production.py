"""
Produção empresarial (design/02 §5-8, §13, §18-20; 22 como fonte de produtos e receitas).

  - **Um produto por vez**, escolhido só pelo Dono (§5.1). Trocar custa setup (empresa fora de operação, ninguém trabalha) e
    cooldown (§5.3). A primeira escolha é livre e instantânea `[PROV]` (o §5.3 fala em "mudar o produto").
  - **O Trabalho do funcionário de produção** (`WORKER`) produz (§6-7): unidades = base × fator da skill relevante × fator da
    especialização × rendimento do catálogo (`raw_yield` da Matriz ou `yield_quantity` da receita). A produção por trabalho é
    fracionária e o estoque é inteiro: a fração sobra em `carry` e nada se perde. Faltou insumo ou espaço: produz o que cabe
    ("reduzido, não bloqueado", como o limite de salário 01 §1.7); sem nada possível a ação é BLOQUEADA ANTES (provedor de bloqueio),
    sem gastar Energia.
  - **Insumos** vêm do estoque da empresa e são consumidos pela receita (§5, §20): `ceil(unidades × quantidade / rendimento)`.
    Materiais operacionais continuam fora desta etapa (limitação conhecida da primeira implementação, Q10).
  - **Qualidade** (§8): cada unidade entra com a skill relevante de quem trabalhou; o estoque guarda a média por unidade (média
    ponderada pelo trabalho); o teto da estrela se aplica na leitura: `MIN(qualidade, teto da estrela)`.
  - **Matriz**: a categoria vem do terreno (§2.1), que pertence a Imóveis (P1.07c: localização da empresa num lote rural). Sem terreno,
    escolher produto de Matriz é recusado (`MATRIX_SITE_UNDEFINED`); terreno sem tipo definido para a categoria: `TERRAIN_TYPE_UNDEFINED`;
    produto fora dos recursos do lote: `PRODUCT_NOT_IN_TERRAIN`. O Trabalho da Matriz também confere o terreno (`COMPANY_SITE_INVALID`).
    Nada é inventado.
  - **Troca com custo**: o §5.3 diz "custo fixo", mas o `24` não tem natureza nem destino para esse dinheiro: o valor `[PROV]` é
    0 e qualquer valor > 0 é recusado (`PRODUCTION_CHANGE_COST_UNDEFINED`) até o GD definir (CHANGELOG_DEV, 2026-10-20).

PROTOCOLO: jogador → empresa (trava a linha, o estoque e a produção da empresa) → registro monetário.
"""
from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any, Callable, Dict, FrozenSet, List, Optional

from django.db import transaction

from catalog import services as catalog
from catalog.constants import RAW_SECTORS, Sector
from catalog.models import Product
from core import clock as game_clock
from core.breakdown import Calc, Explained
from players.actions import Action
from players.hooks import ActionHookContext, register_action_hook, register_block_provider
from players.models import Player
from players.services import ActionResult
from skills.balance import get_skill_balance
from skills.rules import production_multiplier
from skills.services import get_levels, specialization_value

from . import gates, params, stock
from .constants import CompanyType, PositionKind, StockOperation
from .jobs import current_job, relevant_skill
from .models import Company, Position, ProductionChange, ProductionLine, StockItem, WorkWage
from .services import owner_of

BLOCK_PROVIDER = "companies_production"
ACTION_HOOK = "companies_production"
_INT64 = 2 ** 63

SiteProvider = Callable[[int], Optional[FrozenSet[Sector]]]
SiteProductProvider = Callable[[int], Optional[FrozenSet[str]]]
_site_providers: Dict[str, SiteProvider] = {}
_site_product_providers: Dict[str, SiteProductProvider] = {}


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


# --- terreno da Matriz (P1.07) --------------------------------------------------------------------------------------------

def register_site_provider(name: str, fn: SiteProvider) -> None:
    """Imóveis (P1.07) informa as categorias de matéria-prima que o terreno da empresa permite; None = sem localização."""
    if name in _site_providers:
        raise ValueError(f"Provedor de terreno duplicado: {name}")
    _site_providers[name] = fn


def unregister_site_provider(name: str) -> None:      # para testes
    _site_providers.pop(name, None)


def site_categories(company_id: int) -> Optional[FrozenSet[Sector]]:
    for name in sorted(_site_providers):
        out = _site_providers[name](company_id)
        if out is not None:
            return out
    return None


def register_site_product_provider(name: str, fn: SiteProductProvider) -> None:
    """
    Imóveis informa, além das categorias, os PRODUTOS que o terreno da empresa permite (08 §12: os recursos minerais "não são escolhidos
    livremente"; o terreno os define). None = o terreno não restringe por produto.
    """
    if name in _site_product_providers:
        raise ValueError(f"Provedor de produtos do terreno duplicado: {name}")
    _site_product_providers[name] = fn


def unregister_site_product_provider(name: str) -> None:      # para testes
    _site_product_providers.pop(name, None)


def site_products(company_id: int) -> Optional[FrozenSet[str]]:
    for name in sorted(_site_product_providers):
        out = _site_product_providers[name](company_id)
        if out is not None:
            return out
    return None


def site_refusal(company: Company, product_key: str) -> Optional[ActionResult]:
    """O terreno da Matriz permite este produto (02 §2.1, §5.2)? Só LÊ. None = sim."""
    producer = catalog.producer_sector_of(product_key)
    categories = site_categories(company.pk)
    if categories is None:
        return _refuse("MATRIX_SITE_UNDEFINED", company=company.pk, why="a Matriz não tem terreno (localização de empresa: Imóveis, 10 §29)")
    if not categories:
        return _refuse("TERRAIN_TYPE_UNDEFINED", company=company.pk,
                       why="o terreno não tem tipo definido para esta categoria de produto (design/10a, G12)")
    if producer not in categories:
        return _refuse("PRODUCT_OUTSIDE_TERRAIN_CATEGORY", product=product_key, sector=getattr(producer, "value", None),
                       allowed=sorted(c.value for c in categories))
    allowed = site_products(company.pk)
    if allowed is not None and product_key not in allowed:
        return _refuse("PRODUCT_NOT_IN_TERRAIN", product=product_key, allowed=sorted(allowed))
    return None


# --- curva [PROV] de skill → produção --------------------------------------------------------------------------------------

def _linear_prov(level: Decimal) -> Explained:
    return Calc("neutral", 1).add("skill_level_bonus", Decimal(level) * params.SKILL_PRODUCTION_PER_LEVEL).result()


def skill_factor(level: Decimal, at: Optional[int] = None) -> Explained:
    """
    Fator de produção da skill (01 §1.6). Usa a curva do balanceamento de Skills; em "none" (padrão), a `[PROV]` das Empresas, com
    o mesmo detalhamento. A curva `[PROV]` NÃO entra no registro de curvas de Skills (o padrão de lá é só a neutra).
    """
    bal = get_skill_balance()
    if bal.production_curve != "none":
        return production_multiplier(Decimal(level), bal, at)
    return Calc("neutral_multiplier", 1).mul("production_curve", _linear_prov(Decimal(level)).value,
                                             detail=_linear_prov(Decimal(level))).result(at)


# --- leitura -----------------------------------------------------------------------------------------------------------------

def line_of(company_id: int) -> Optional[ProductionLine]:
    return ProductionLine.objects.filter(company_id=company_id).select_related("product").first()


def active_product_key(company_id: int, now: int) -> Optional[str]:
    """Produto em produção AGORA (escolhido e fora do setup), ou None."""
    line = line_of(company_id)
    if line is None or line.product_id is None or (line.setup_until is not None and now < line.setup_until):
        return None
    return line.product.key


def quality_cap(stars: int) -> Decimal:
    return params.QUALITY_CAP_PER_STAR[stars]


def effective_quality(company: Company, quality: Optional[Decimal]) -> Optional[Explained]:
    """`MIN(qualidade, teto da estrela)` (02 §8) com o detalhamento; None se a qualidade é desconhecida (NULL ≠ 0)."""
    if quality is None:
        return None
    return Calc("production_quality", quality).cap("star_cap", quality_cap(company.stars)).result(game_clock.now())


def output_per_work(product_key: str, level: Decimal, specialization: Decimal, at: Optional[int] = None,
                    engineering_bonus: Optional[Explained] = None) -> Explained:
    """
    Unidades (fracionárias) por trabalho (02 §7, §9.1) com os fatores (20): base × skill × especialização × (1 + bônus diário do
    Engenheiro) × rendimento do catálogo. Sem Engenheiro trabalhando no dia, o bônus é 0 e o fator é 1.
    """
    product = catalog.get_product(product_key)
    recipe = catalog.recipe_of(product_key)
    yield_q = (product.raw_yield if product.sector in {s.value for s in RAW_SECTORS} else
               (recipe.yield_quantity if recipe is not None else None))
    if yield_q is None:
        raise ValueError(f"rendimento não especificado para {product_key} (check_production_ready deveria ter recusado)")
    skill = skill_factor(level, at)
    return (Calc("units_per_work_base", params.UNITS_PER_WORK_BASE)
            .mul("skill_production", skill.value, detail=skill)
            .mul("specialization_production", 1 + Decimal(specialization) * params.SPECIALIZATION_PRODUCTION_PER_POINT)
            .mul("engineering_bonus", 1 + (Decimal(0) if engineering_bonus is None else engineering_bonus.value),
                 detail=engineering_bonus)
            .mul("catalog_yield", yield_q)
            .result(at))


# --- escolher / trocar o produto ------------------------------------------------------------------------------------------

def _eligible(company: Company, product_key: Any) -> Optional[ActionResult]:
    """O produto pode ser produzido por ESTA empresa (tipo, terreno, receita pronta, estrela)? None = sim."""
    if not isinstance(product_key, str):
        return _refuse("INVALID_PARAMS", why="product deve ser texto")
    product = catalog.get_product(product_key)
    if product is None:
        return _refuse("UNKNOWN_PRODUCT", key=product_key[:60])
    ctype = CompanyType(company.type)
    producer = catalog.producer_sector_of(product_key)
    if ctype is CompanyType.MATRIX:
        if producer not in RAW_SECTORS:
            return _refuse("PRODUCT_NOT_FOR_COMPANY_TYPE", product=product_key, company_type=company.type)
        refusal = site_refusal(company, product_key)
        if refusal is not None:
            return refusal
    elif ctype is CompanyType.INDUSTRIAL:
        if producer is None or producer in RAW_SECTORS:
            return _refuse("PRODUCT_NOT_FOR_COMPANY_TYPE", product=product_key, company_type=company.type)
    ready = catalog.check_production_ready(product_key)
    if not ready.ok:
        return _refuse("PRODUCTION_NOT_READY", **ready.detail, reason=ready.code)
    if product.min_stars is not None and product.min_stars > company.stars:
        return _refuse("STARS_TOO_LOW", product=product_key, required=product.min_stars, stars=company.stars)
    return None


def selection_refusal(player_id: int, company_id: Any, product_key: Any, now: Optional[int] = None) -> Optional[ActionResult]:
    """Recusas que só LEEM (a execução usa as mesmas)."""
    now = game_clock.now() if now is None else now
    if isinstance(company_id, bool) or not isinstance(company_id, int) or not -_INT64 <= company_id < _INT64:
        return _refuse("INVALID_PARAMS", company=repr(company_id)[:40])
    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return _refuse("COMPANY_NOT_FOUND", company=company_id)
    if owner_of(company_id) != player_id:
        return _refuse("NOT_OWNER", company=company_id)
    if CompanyType(company.type) not in params.PRODUCING_TYPES:
        return _refuse("COMPANY_TYPE_CANNOT_PRODUCE", company_type=company.type,
                       producing=sorted(t.value for t in params.PRODUCING_TYPES))
    refusal = _eligible(company, product_key)
    if refusal is not None:
        return refusal
    line = line_of(company_id)
    if line is not None and line.product_id is not None:
        if line.product.key == product_key:
            return _refuse("ALREADY_PRODUCING", product=product_key)
        if line.cooldown_until is not None and now < line.cooldown_until:
            return _refuse("COOLDOWN_ACTIVE", until=line.cooldown_until, remaining=line.cooldown_until - now)
        if params.PRODUCTION_CHANGE_COST_CENTS > 0:
            return _refuse("PRODUCTION_CHANGE_COST_UNDEFINED", cost=params.PRODUCTION_CHANGE_COST_CENTS)
    return None


def set_production(player_id: int, company_id: Any, product_key: Any) -> ActionResult:
    """
    O Dono escolhe (primeira vez: livre e instantâneo) ou troca o produto (02 §5): troca = setup (fora de operação) + cooldown;
    o `carry` fracionário da produção anterior é descartado. Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS, COMPANY_NOT_FOUND,
    NOT_OWNER, COMPANY_TYPE_CANNOT_PRODUCE, UNKNOWN_PRODUCT, PRODUCT_NOT_FOR_COMPANY_TYPE, MATRIX_SITE_UNDEFINED,
    PRODUCT_OUTSIDE_TERRAIN_CATEGORY, PRODUCTION_NOT_READY, STARS_TOO_LOW, ALREADY_PRODUCING, COOLDOWN_ACTIVE,
    PRODUCTION_CHANGE_COST_UNDEFINED.
    """
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    with transaction.atomic():
        Player.objects.select_for_update().filter(pk=player_id).first()                        # protocolo: jogador
        if isinstance(company_id, int) and not isinstance(company_id, bool) and -_INT64 <= company_id < _INT64:
            Company.objects.select_for_update().filter(pk=company_id).first()                  # protocolo: empresa
        refusal = selection_refusal(player_id, company_id, product_key)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        product = catalog.get_product(product_key)
        line, _ = ProductionLine.objects.select_for_update().get_or_create(company_id=company_id)
        previous = line.product
        change = previous is not None
        line.product = product
        line.selected_at = now
        line.setup_until = now + params.SETUP_SECONDS if change else None
        line.cooldown_until = now + params.COOLDOWN_SECONDS if change else None
        line.carry = Decimal(0)
        line.changes += 1
        line.save()
        ProductionChange.objects.create(
            company_id=company_id, sequence=line.changes, from_product=previous, to_product=product, at=now, cost=0,
            setup_until=line.setup_until, cooldown_until=line.cooldown_until, actor=player_id,
            explained={"initial": not change, "setup_seconds": params.SETUP_SECONDS if change else 0,
                       "cooldown_seconds": params.COOLDOWN_SECONDS if change else 0})
        return ActionResult(True, "OK", {"company": company_id, "product": product.key, "initial": not change,
                                         "setup_until": line.setup_until, "cooldown_until": line.cooldown_until})


def producible_products(company_id: int) -> List[Dict[str, Any]]:
    """O que o Dono poderia escolher e, para cada produto, se pode e por quê não (explicável, 20). Só informação pública do catálogo."""
    company = Company.objects.filter(pk=company_id).first()
    if company is None or CompanyType(company.type) not in params.PRODUCING_TYPES:
        return []
    rows = []
    for product in Product.objects.order_by("key"):
        refusal = _eligible(company, product.key)
        rows.append({"product": product.key, "name": product.name, "min_stars": product.min_stars,
                     "available": refusal is None, "code": "OK" if refusal is None else refusal.code,
                     "detail": {} if refusal is None else refusal.detail})
    return rows


def status_of(company_id: int, now: Optional[int] = None) -> Dict[str, Any]:
    """Estado da produção com o que ela precisa para operar agora (20)."""
    now = game_clock.now() if now is None else now
    company = Company.objects.get(pk=company_id)
    line = line_of(company_id)
    product = line.product if line is not None else None
    in_setup = bool(line is not None and line.setup_until is not None and now < line.setup_until)
    used = stock.used_of(company_id)
    capacity = stock.capacity_of(company.stars)
    return {"company": company_id, "product": product.key if product else None,
            "in_setup": in_setup, "setup_until": line.setup_until if line else None,
            "cooldown_until": line.cooldown_until if line else None, "carry": line.carry if line else Decimal(0),
            "stock_used": used, "stock_capacity": int(capacity.value), "stock_capacity_explained": capacity,
            "quality_cap": quality_cap(company.stars)}


# --- o Trabalho produz ---------------------------------------------------------------------------------------------------

def _needs(product_key: str):
    """(insumos, rendimento) da receita; ([], None) para matéria-prima."""
    recipe = catalog.recipe_of(product_key)
    if recipe is None:
        return [], None
    return list(recipe.inputs), recipe.yield_quantity


def _inputs_stock(company_id: int, inputs) -> Dict[str, int]:
    keys = [i.key for i in inputs]
    have = {k: 0 for k in keys}
    for row in StockItem.objects.filter(company_id=company_id, product__key__in=keys).select_related("product"):
        have[row.product.key] = row.quantity
    return have


def _max_out_by_inputs(inputs, yield_q: Optional[Decimal], have: Dict[str, int]) -> Optional[int]:
    """Quantas unidades os insumos em estoque permitem; None = não há insumos (matéria-prima)."""
    if not inputs:
        return None
    return min(int((Decimal(have[i.key]) * yield_q / i.quantity).to_integral_value(rounding=ROUND_FLOOR)) for i in inputs)


def work_refusal(job: Position, now: int) -> Optional[str]:
    """Código que impede o Trabalho de produção agora (provedor de bloqueio), ou None. Só LÊ; sem efeito."""
    line = line_of(job.company_id)
    if line is None or line.product_id is None:
        return "COMPANY_NO_PRODUCT"
    if line.setup_until is not None and now < line.setup_until:
        return "COMPANY_IN_SETUP"
    if CompanyType(job.company.type) is CompanyType.MATRIX and site_refusal(job.company, line.product.key) is not None:
        return "COMPANY_SITE_INVALID"                    # a Matriz perdeu o terreno (ou mudou para um que não permite o produto)
    if CompanyType(job.company.type) is CompanyType.INDUSTRIAL:
        gate = gates.operation_refusal(job.company)      # G5: Industrial localizada no prédio industrial, quando `REQUIRE_LOCATION_TO_OPERATE`
        if gate is not None:
            return gate.code
    inputs, yield_q = _needs(line.product.key)
    cap_left = int(stock.capacity_of(job.company.stars).value) - stock.used_of(job.company_id)
    if cap_left <= 0:
        return "STOCK_FULL"
    if inputs:
        out = _max_out_by_inputs(inputs, yield_q, _inputs_stock(job.company_id, inputs))
        if out is not None and out < 1:
            return "MISSING_INPUTS"
    return None


def block_provider(player: Player, action: Action, now: int, activity) -> Optional[str]:
    if action is not Action.WORK:
        return None
    job = current_job(player.pk)
    if job is None or job.kind != PositionKind.WORKER.value or CompanyType(job.company.type) not in params.PRODUCING_TYPES:
        return None                                      # só Matriz e Industrial produzem; os demais tipos têm operação própria
    return work_refusal(job, now)


def produce_on_work(ctx: ActionHookContext) -> Optional[Dict[str, Any]]:
    """Hook de `perform_action`: o Trabalho de um funcionário de produção gera unidades no estoque da empresa."""
    if ctx.action is not Action.WORK:
        return None
    player_id = ctx.player.pk
    job = current_job(player_id)
    if job is None or job.kind != PositionKind.WORKER.value or CompanyType(job.company.type) not in params.PRODUCING_TYPES:
        return None
    company = Company.objects.select_for_update().get(pk=job.company_id)                      # protocolo: jogador → empresa
    line = ProductionLine.objects.select_for_update(of=("self",)).select_related("product").filter(company=company).first()
    if line is None or line.product_id is None:
        return {"company": company.pk, "produced": 0, "limited_by": ["COMPANY_NO_PRODUCT"]}
    if line.setup_until is not None and ctx.now < line.setup_until:
        return {"company": company.pk, "produced": 0, "limited_by": ["COMPANY_IN_SETUP"]}
    if CompanyType(company.type) is CompanyType.MATRIX and site_refusal(company, line.product.key) is not None:
        return {"company": company.pk, "produced": 0, "limited_by": ["COMPANY_SITE_INVALID"]}
    if CompanyType(company.type) is CompanyType.INDUSTRIAL:
        gate = gates.operation_refusal(company)
        if gate is not None:
            return {"company": company.pk, "produced": 0, "limited_by": [gate.code]}
    product = line.product
    level = get_levels(player_id)[relevant_skill(PositionKind.WORKER)]
    spec = specialization_value(player_id, product.key)
    from . import support
    per_work = output_per_work(product.key, level, spec, ctx.now, support.engineering_bonus(company.pk, ctx.now))
    total = line.carry + per_work.value
    whole = int(total.to_integral_value(rounding=ROUND_FLOOR))
    out, limited_by = whole, []
    inputs, yield_q = _needs(product.key)
    have = _inputs_stock(company.pk, inputs)
    by_inputs = _max_out_by_inputs(inputs, yield_q, have)
    if by_inputs is not None and by_inputs < out:
        out, limited_by = by_inputs, limited_by + ["MISSING_INPUTS"]
    free = int(stock.capacity_of(company.stars).value) - stock.used_of(company.pk)
    if free < out:
        out, limited_by = max(0, free), limited_by + ["STOCK_FULL"]
    consumed = {}
    for i in inputs:
        need = int((Decimal(out) * i.quantity / yield_q).to_integral_value(rounding=ROUND_CEILING))
        if need > 0:
            consumed[i.key] = need
    sequence = WorkWage.objects.filter(player_id=player_id).count() + 1      # o MESMO nº do salário desta ação (payroll cria depois)
    key = f"production:{player_id}:{sequence}"
    reference = f"{player_id}:{sequence}"
    result: Dict[str, Any] = {"company": company.pk, "product": product.key, "produced": out, "consumed": consumed,
                              "per_work": per_work, "whole_units": whole, "limited_by": limited_by}
    if out > 0:
        for input_key, need in sorted(consumed.items()):
            moved = stock.apply_locked(
                company, catalog.get_product(input_key), -need, StockOperation.INPUT_CONSUMPTION,
                origin=f"company:{company.pk}", destination=f"production:{product.key}", key=f"{key}:in:{input_key}",
                reference_kind="work_production", reference_id=reference, at=ctx.now, actor=player_id,
                explained={"output": product.key, "units": out, "recipe_yield": str(yield_q)})
            if not moved.ok:
                raise RuntimeError(f"insumo recusado pelo estoque: {moved.code} {moved.detail}")
        made = stock.apply_locked(
            company, product, out, StockOperation.PRODUCTION, origin=f"production:{player_id}",
            destination=f"company:{company.pk}", key=key, reference_kind="work_production", reference_id=reference,
            at=ctx.now, actor=player_id, quality=level,
            explained={"per_work": per_work.to_dict(), "carry_before": str(line.carry), "limited_by": limited_by,
                       "consumed": consumed})
        if not made.ok:
            raise RuntimeError(f"produção recusada pelo estoque: {made.code} {made.detail}")
        result["quality"] = made.detail["quality"]
    line.carry = (total - whole).quantize(Decimal("0.000001"))
    line.save(update_fields=["carry"])
    result["carry"] = line.carry
    return result


def register() -> None:
    register_block_provider(BLOCK_PROVIDER, block_provider)
    register_action_hook(ACTION_HOOK, produce_on_work)
