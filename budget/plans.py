"""
Distribuição do orçamento municipal entre as áreas (09 §5, §27) e pisos legais (11 §11.2.1; 09 45.3).

O Prefeito monta um PLANO por período de 30 dias (rascunho, editável) e o CONFIRMA. Na confirmação se verificam, com `Explained` (20):
  - cada PISO (Educação, Saúde, Infraestrutura): valor planejado da área ≥ piso% × BASE, onde BASE = receitas contáveis do Município nos últimos 30 dias
    (arrecadação própria + transferências efetivamente recebidas; mesma definição de receita do teto de déficit, 24 §24.16);
  - a SOMA dos pisos não passa de 100% (11 §11.2.1);
  - o TOTAL planejado cabe no disponível do Município agora (saldo − comprometido): não se distribui o que o Município não tem (lacuna K4, design/09a).
O que sobra sem destino é RESERVA (09 §32: manter reserva é decisão política, não despesa).
Plano confirmado não muda (decisão registrada e pública, 09 §27). Os pisos só valem no orçamento municipal (União e Estados não têm pisos, 11 §11.2.1).
A dotação por área limita o gasto discricionário daquela área (`area_headroom`); os sistemas que gastam (projetos, escolas, ...) a consultam quando existirem.
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any, Dict, List, Optional

from django.db import transaction

from core import clock as game_clock
from ledger import services as ledger
from ledger.models import Account
from ledger.money import competence_day_of
from players.services import ActionResult

from . import fiscal, params, periods
from .authority import authority_refusal
from .constants import FLOOR_AREAS, MUNICIPAL_AREAS, Area, DecisionKind, Level, PlanStatus
from .govs import account_of, is_int, refuse
from .models import BudgetPlan, BudgetPlanLine, GovernmentDecision

SET_KEYS = frozenset({"city", "lines"})
SET_OPTIONAL = frozenset({"period"})
CONFIRM_KEYS = frozenset({"city"})
CONFIRM_OPTIONAL = frozenset({"period"})


def _city_exists(city_id: Any) -> bool:
    from geography.models import City
    return is_int(city_id) and city_id > 0 and City.objects.filter(pk=city_id).exists()


def _period(target: Dict[str, Any], today: int) -> Any:
    period = target.get("period", periods.period_of(today))
    if not is_int(period):
        return refuse("INVALID_PERIOD", period=repr(period)[:30])
    if period < periods.period_of(today):
        return refuse("PERIOD_ENDED", period=period, current=periods.period_of(today))
    return period


def _lines(value: Any):
    if not isinstance(value, dict):
        return refuse("INVALID_LINES", expected=[a.value for a in MUNICIPAL_AREAS])
    out = {}
    for key, amount in value.items():
        try:
            area = Area(key)
        except ValueError:
            return refuse("INVALID_AREA", area=repr(key)[:30], allowed=[a.value for a in MUNICIPAL_AREAS])
        if area not in MUNICIPAL_AREAS:
            return refuse("AREA_NOT_MUNICIPAL", area=area.value, allowed=[a.value for a in MUNICIPAL_AREAS])
        if not is_int(amount) or amount < 0:
            return refuse("INVALID_AMOUNT", area=area.value, amount=repr(amount)[:30])
        out[area] = amount
    return out


def set_plan_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    if not isinstance(target, dict) or not SET_KEYS <= set(target) or not set(target) <= SET_KEYS | SET_OPTIONAL:
        return refuse("INVALID_PARAMS", expected=sorted(SET_KEYS), optional=sorted(SET_OPTIONAL))
    if not is_int(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    if not _city_exists(target["city"]):
        return refuse("GOVERNMENT_NOT_FOUND", level="municipality", id=repr(target["city"])[:30])
    lines = _lines(target["lines"])
    if isinstance(lines, ActionResult):
        return lines
    today = competence_day_of(game_clock.now())
    period = _period(target, today)
    if isinstance(period, ActionResult):
        return period
    refusal = authority_refusal(actor_id, Level.MUNICIPALITY, target["city"])
    if refusal is not None:
        return refusal
    plan = BudgetPlan.objects.filter(city_id=target["city"], period=period).first()
    if plan is not None and plan.status == PlanStatus.CONFIRMED.value:
        return refuse("PLAN_CONFIRMED", period=period)
    return None


def set_plan(actor_id: Any, target: Any) -> ActionResult:
    """Monta (ou refaz) o rascunho do plano do período; as áreas omitidas ficam em zero. Só o Prefeito."""
    with transaction.atomic():
        if isinstance(target, dict) and _city_exists(target.get("city")):
            account = account_of(Level.MUNICIPALITY, target["city"])
            list(Account.objects.select_for_update().filter(pk=account.pk))              # serializa plano × confirmação do mesmo Município
        refusal = set_plan_refusal(actor_id, target)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        period = target.get("period", periods.period_of(competence_day_of(now)))
        lines = _lines(target["lines"])
        plan, _ = BudgetPlan.objects.get_or_create(city_id=target["city"], period=period, defaults={"created_at": now})
        plan.lines.all().delete()
        BudgetPlanLine.objects.bulk_create([BudgetPlanLine(plan=plan, area=a.value, amount_cents=v) for a, v in sorted(lines.items(), key=lambda x: x[0].value)])
        return ActionResult(True, "OK", {"plan": plan.pk, "period": period, "status": plan.status, "total": sum(lines.values()),
                                         "lines": {a.value: v for a, v in sorted(lines.items(), key=lambda x: x[0].value)}})


def floors_check(plan_lines: Dict[Area, int], base: int, available: int) -> Dict[str, Any]:
    """Confere pisos e total (Explained). `base` = receitas de 30 dias; `available` = disponível do Município. Valor em centavos; piso arredondado PARA CIMA."""
    floors, total_pct = [], 0
    for area in FLOOR_AREAS:
        pct = params.FLOOR_PCT[area]
        total_pct += pct
        required = -((-Fraction(pct) * base) // 100)         # teto da fração: nunca exige menos que o piso
        planned = plan_lines.get(area, 0)
        floors.append({"area": area.value, "floor_pct": str(pct), "base": base, "required": int(required), "planned": planned,
                       "ok": planned >= required, "shortfall": max(0, int(required) - planned)})
    total = sum(plan_lines.values())
    return {"base_revenue_30_days": base, "floors": floors, "floors_total_pct": str(total_pct), "floors_total_valid": total_pct <= 100,
            "planned_total": total, "available": available, "total_fits": total <= available, "reserve": max(0, available - total),
            "ok": all(f["ok"] for f in floors) and total_pct <= 100 and total <= available}


def confirm_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    if not isinstance(target, dict) or not CONFIRM_KEYS <= set(target) or not set(target) <= CONFIRM_KEYS | CONFIRM_OPTIONAL:
        return refuse("INVALID_PARAMS", expected=sorted(CONFIRM_KEYS), optional=sorted(CONFIRM_OPTIONAL))
    if not is_int(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    if not _city_exists(target["city"]):
        return refuse("GOVERNMENT_NOT_FOUND", level="municipality", id=repr(target["city"])[:30])
    now = game_clock.now()
    today = competence_day_of(now)
    period = _period(target, today)
    if isinstance(period, ActionResult):
        return period
    refusal = authority_refusal(actor_id, Level.MUNICIPALITY, target["city"])
    if refusal is not None:
        return refusal
    plan = BudgetPlan.objects.filter(city_id=target["city"], period=period).first()
    if plan is None:
        return refuse("PLAN_NOT_FOUND", period=period)
    if plan.status == PlanStatus.CONFIRMED.value:
        return refuse("PLAN_CONFIRMED", period=period)
    lines = {Area(l.area): l.amount_cents for l in plan.lines.all()}
    account = account_of(Level.MUNICIPALITY, target["city"])
    base = fiscal.flows(account.pk, today - params.PERIOD_DAYS + 1, today).revenue
    check = floors_check(lines, base, ledger.available_of(account.pk))
    if not check["floors_total_valid"]:
        return refuse("FLOORS_EXCEED_100_PERCENT", **check)
    if not all(f["ok"] for f in check["floors"]):
        return refuse("FLOOR_NOT_MET", **check)
    if not check["total_fits"]:
        return refuse("PLAN_EXCEEDS_AVAILABLE", **check)
    return None


def confirm_plan(actor_id: Any, target: Any) -> ActionResult:
    """O Prefeito confirma o plano: confere pisos (base de 30 dias), soma dos pisos e disponível; registra a decisão pública. Plano confirmado não muda."""
    with transaction.atomic():
        if isinstance(target, dict) and _city_exists(target.get("city")):
            account = account_of(Level.MUNICIPALITY, target["city"])
            list(Account.objects.select_for_update().filter(pk=account.pk))
        refusal = confirm_refusal(actor_id, target)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        today = competence_day_of(now)
        period = target.get("period", periods.period_of(today))
        plan = BudgetPlan.objects.select_for_update().get(city_id=target["city"], period=period)
        lines = {Area(l.area): l.amount_cents for l in plan.lines.all()}
        account = account_of(Level.MUNICIPALITY, target["city"])
        base = fiscal.flows(account.pk, today - params.PERIOD_DAYS + 1, today).revenue
        check = floors_check(lines, base, ledger.available_of(account.pk))
        plan.status, plan.confirmed_at, plan.confirmed_by_id = PlanStatus.CONFIRMED.value, now, actor_id
        plan.confirmed_total, plan.confirmation = check["planned_total"], check
        plan.save(update_fields=["status", "confirmed_at", "confirmed_by_id", "confirmed_total", "confirmation"])
        decision = GovernmentDecision.objects.create(
            kind=DecisionKind.PLAN_CONFIRMED.value, level=Level.MUNICIPALITY.value, territory_id=target["city"], actor_id=actor_id, at=now,
            competence_day=today, data={"plan": plan.pk, "period": period, "lines": {a.value: v for a, v in sorted(lines.items(), key=lambda x: x[0].value)},
                                        "check": check})
        return ActionResult(True, "OK", {"plan": plan.pk, "period": period, "decision": decision.pk, "check": check})


def plan_view(city_id: int, period: Optional[int] = None, at: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Plano público do Município (09 §27, §33) com a dotação restante por área."""
    at = game_clock.now() if at is None else at
    today = competence_day_of(at)
    period = periods.period_of(today) if period is None else period
    plan = BudgetPlan.objects.filter(city_id=city_id, period=period).first()
    if plan is None:
        return None
    lines = {l.area: l.amount_cents for l in plan.lines.all()}
    first, last = periods.bounds_of(period)
    account = account_of(Level.MUNICIPALITY, city_id)
    spent = fiscal.flows(account.pk, first, min(last, today)).expense_by_category if today >= first else {}
    return {"plan": plan.pk, "city": city_id, "period": period, "first_day": first, "last_day": last, "status": plan.status,
            "lines": dict(sorted(lines.items())), "total": sum(lines.values()), "spent_by_area": {a: spent.get(a, 0) for a in sorted(lines)},
            "headroom_by_area": {a: lines[a] - spent.get(a, 0) for a in sorted(lines)}, "confirmation": plan.confirmation,
            "confirmed_at": plan.confirmed_at, "confirmed_by": plan.confirmed_by_id}


def area_headroom(city_id: int, area: Area, at: Optional[int] = None) -> Optional[int]:
    """Dotação restante da área no período atual (linha do plano CONFIRMADO − gasto categorizado). None = sem plano confirmado (≠ 0)."""
    view = plan_view(city_id, None, at)
    if view is None or view["status"] != PlanStatus.CONFIRMED.value:
        return None
    return view["headroom_by_area"].get(area.value, 0)
