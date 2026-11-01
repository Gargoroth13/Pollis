"""
Notícias econômicas (design/12 §12.4): tendência de preço médio de um Produto nos últimos 7 dias, com o MESMO cálculo do 17
(`market.stats.trend`), lendo só os AGREGADOS diários (nunca percorre transações brutas para montar o feed, 12.15).

Só gera notícia se |tendência| ≥ limiar (12.4) e se o indicador do produto não saiu em notícia dentro do intervalo mínimo (12.12).
"Sem dados" (17.9) nunca vira notícia. As outras métricas que o 12 "pode" noticiar (estoque, produção, consumo, volume) não são padrão
do design e não têm limiar definido: ver design/12a (H5).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from catalog.models import Product
from core import clock as game_clock
from core import ticks
from core.timeline import Tick, TickKind
from ledger.money import competence_day_of
from market import rollup, stats
from market.constants import OK, TREND_DAYS
from market.models import DailyProductStat

from . import params, texts
from .constants import Category, Priority, RefKind, Status
from .publish import Published, publish

TICK_NAME = "history_economy_news"


@dataclass(frozen=True)
class TrendCheck:
    """Avaliação explicável (20) de um produto: o que foi medido e por que gerou, ou não, notícia."""
    product: str
    pct: Optional[Decimal]
    outcome: str                      # published | duplicate | suppressed | below_threshold | no_data
    threshold: Decimal
    detail: dict


def candidate_product_ids(today: int) -> List[int]:
    """Produtos com venda nos últimos 14 dias de competência (2 períodos de 7), dos AGREGADOS diários já fechados."""
    return list(DailyProductStat.objects.filter(day__gte=today - 2 * TREND_DAYS, day__lt=today, volume__gt=0)
                .order_by().values_list("product_id", flat=True).distinct())


def check_price_trends(now: Optional[int] = None) -> List[TrendCheck]:
    now = game_clock.now() if now is None else now
    today = competence_day_of(now)
    rollup.ensure_closed(today - 1, at=now)                       # os dias fechados vêm dos agregados; fecha o que faltar (idempotente)
    ids = candidate_product_ids(today)
    products = {p.pk: p for p in Product.objects.filter(pk__in=ids)}
    threshold = params.PRICE_TREND_THRESHOLD_PCT
    out: List[TrendCheck] = []
    for pid in sorted(ids, key=lambda i: products[i].key):
        product = products[pid]
        trend = stats.trend(pid, now)
        if trend.status != OK:
            out.append(TrendCheck(product.key, None, "no_data", threshold, trend.detail))
            continue
        pct = trend.value
        if abs(pct) < threshold:
            out.append(TrendCheck(product.key, pct, "below_threshold", threshold, trend.detail))
            continue
        up = pct > 0
        major = abs(pct) >= params.MAJOR_TREND_PCT
        result = publish("economy.price_up" if up else "economy.price_down",
                         {"product": product.name, "pct": texts.fmt_pct(abs(pct))}, category=Category.ECONOMY,
                         priority=Priority.MAJOR_ECONOMIC if major else Priority.MINOR_ECONOMIC, at=now, ref=(RefKind.PRODUCT, product.key),
                         dedupe_key=f"price_trend:{product.key}:{today}", indicator=f"price_trend:{product.key}",
                         min_interval=params.INDICATOR_MIN_INTERVAL_SECONDS,
                         structured={"product": product.key, "pct": pct, "threshold_pct": threshold, "major_pct": params.MAJOR_TREND_PCT,
                                     "formula": trend.detail.get("formula"), "last_7d": trend.detail["last_7d"], "previous_7d": trend.detail["previous_7d"]})
        out.append(TrendCheck(product.key, pct, result.status, threshold, trend.detail))
    return out


def _daily_tick(tick: Tick, ctx) -> None:
    check_price_trends(tick.at)


def register() -> None:
    ticks.register(ticks.WORLD, TickKind.DAILY, TICK_NAME, priority=95)(_daily_tick)      # depois do fechamento diário do mercado (prioridade 90)
