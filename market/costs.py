"""
Transparência de custos da Empresa (design/17 §17.14-17.16). Só LÊ os agregados diários (`CompanyCostDay`, fechados sob demanda).

Compara os ÚLTIMOS 7 DIAS FECHADOS com os 7 anteriores (o dia corrente, incompleto, não entra: somar um dia parcial contra dias
inteiros distorceria o total). Cada categoria traz valores, variação % (None quando não há base de comparação) e a diferença em
centavos. A "principal contribuição observada" (17.15) é a categoria de maior diferença NA DIREÇÃO da variação do total; o texto não
afirma causalidade, só qual componente merece atenção.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Sum

from core import clock as game_clock
from ledger.money import competence_day_of

from . import rollup
from .constants import NO_DATA, OK, TREND_DAYS, CostCategory
from .models import CompanyCostDay


def _sums(company_id: int, first_day: int, last_day: int) -> Dict[str, int]:
    rows = (CompanyCostDay.objects.filter(company_id=company_id, day__gte=first_day, day__lte=last_day)
            .values("category").annotate(v=Sum("amount_cents")))
    return {r["category"]: r["v"] for r in rows}


def _pct(last: int, prev: int) -> Optional[Decimal]:
    return None if prev == 0 else (Decimal(last) / Decimal(prev) - 1) * 100


def company_cost_report(company_id: int, now: Optional[int] = None) -> Dict[str, Any]:
    now = game_clock.now() if now is None else now
    yesterday = competence_day_of(now) - 1
    rollup.ensure_closed(yesterday, at=now)
    last_first, prev_first = yesterday - TREND_DAYS + 1, yesterday - 2 * TREND_DAYS + 1
    last = _sums(company_id, last_first, yesterday)
    prev = _sums(company_id, prev_first, last_first - 1)
    periods = {"last_7d": {"first_day": last_first, "last_day": yesterday}, "previous_7d": {"first_day": prev_first, "last_day": last_first - 1}}
    total_last, total_prev = sum(last.values()), sum(prev.values())
    if not total_last and not total_prev:
        return {"status": NO_DATA, "periods": periods, "total": None, "components": [], "main_contribution": None,
                "why": "a empresa não registrou custos nos dois períodos"}
    components: List[Dict[str, Any]] = []
    for category in sorted(set(last) | set(prev)):
        l, p = last.get(category, 0), prev.get(category, 0)
        components.append({"category": category, "product": category[len(CostCategory.INPUT_PREFIX):] if category.startswith(CostCategory.INPUT_PREFIX) else None,
                           "last_7d_cents": l, "previous_7d_cents": p, "delta_cents": l - p, "variation_pct": _pct(l, p)})
    components.sort(key=lambda c: (-abs(c["delta_cents"]), c["category"]))
    delta = total_last - total_prev
    main = None
    if delta:
        same_direction = [c for c in components if c["delta_cents"] * delta > 0]
        if same_direction:
            top = max(same_direction, key=lambda c: (abs(c["delta_cents"]), c["category"]))
            main = {"category": top["category"], "product": top["product"], "delta_cents": top["delta_cents"],
                    "text": ("Principal contribuição para o aumento dos custos" if delta > 0 else "Principal contribuição para a queda dos custos")}
    return {"status": OK, "periods": periods,
            "total": {"last_7d_cents": total_last, "previous_7d_cents": total_prev, "delta_cents": delta, "variation_pct": _pct(total_last, total_prev)},
            "components": components, "main_contribution": main}
