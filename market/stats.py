"""
Estatísticas de Mercado por Produto (design/17 §17.3-17.13): preço médio ponderado, menor/maior preço, oferta, produção, consumo,
tendência, gráficos de 30 dias e visão geral do Mercado. Só LÊ.

Regras que valem em tudo:
  - **Só vendas concluídas** (17.4): anúncios e preços de listagem nunca entram.
  - **Sem dados é "Sem dados"** (17.9, 17.20): sem transações no período o indicador é `NO_DATA` (`value=None`), nunca zero e nunca o
    `base_price` do catálogo. Produção/consumo são somas de eventos reais: sem eventos é 0 real, não "sem dados".
  - **Janelas**: as de 24 h são móveis (`now − 24 h, now]`), lidas das trilhas brutas por índice de tempo. Tendência e gráficos usam
    DIAS de competência: dias fechados dos agregados (`DailyProductStat`, fechados sob demanda) + o dia corrente calculado ao vivo.
    Últimos 7 dias = hoje e os 6 anteriores; 7 dias anteriores = os 7 antes deles.
  - Cada indicador devolve valor final + detalhamento estruturado (20).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Count, Max, Min, Sum

from catalog import services as catalog
from core import clock as game_clock
from ledger.money import competence_day_of

from . import rollup
from .constants import CHART_DAYS, NO_DATA, OK, TREND_DAYS, WINDOW_24H
from .models import DailyProductStat, MarketTransaction


@dataclass(frozen=True)
class Indicator:
    value: Optional[Any]                  # None = "Sem dados" (17.9)
    status: str                           # OK | NO_DATA
    detail: Dict[str, Any] = field(default_factory=dict)
    period: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"value": self.value, "status": self.status, "detail": self.detail, "period": self.period}


def _no_data(period: str, **detail) -> Indicator:
    return Indicator(None, NO_DATA, detail, period)


def _window_sales(product_id: int, now: int):
    return MarketTransaction.objects.filter(product_id=product_id, at__gt=now - WINDOW_24H, at__lte=now)


def avg_price_24h(product_id: int, now: int) -> Indicator:
    agg = _window_sales(product_id, now).aggregate(n=Count("id"), q=Sum("quantity"), v=Sum("total_cents"))
    if not agg["n"]:
        return _no_data("24h")
    return Indicator(Decimal(agg["v"]) / Decimal(agg["q"]), OK,
                     {"value_cents": agg["v"], "quantity": agg["q"], "transactions": agg["n"], "formula": "soma(preço×quantidade) / soma(quantidade)"}, "24h")


def price_range_24h(product_id: int, now: int) -> Dict[str, Indicator]:
    agg = _window_sales(product_id, now).aggregate(n=Count("id"), low=Min("unit_price_cents"), high=Max("unit_price_cents"))
    if not agg["n"]:
        return {"min": _no_data("24h"), "max": _no_data("24h")}
    return {"min": Indicator(agg["low"], OK, {"transactions": agg["n"]}, "24h"),
            "max": Indicator(agg["high"], OK, {"transactions": agg["n"]}, "24h")}


def usage_24h(product_id: int, now: int) -> Dict[str, Indicator]:
    """Produção e consumo reais das últimas 24 h, das trilhas imutáveis."""
    from companies.models import StockMovement
    from inventory.models import InventoryMovement
    start = now - WINDOW_24H
    stock = StockMovement.objects.filter(product_id=product_id, at__gt=start, at__lte=now, operation__in=("production", "input_consumption"))
    produced = stock.filter(operation="production").aggregate(q=Sum("delta"))["q"] or 0
    inputs = -(stock.filter(operation="input_consumption").aggregate(q=Sum("delta"))["q"] or 0)
    players = -(InventoryMovement.objects.filter(product_id=product_id, at__gt=start, at__lte=now, operation="consumption")
                .aggregate(q=Sum("delta"))["q"] or 0)
    return {"production": Indicator(produced, OK, {"source": "movimentos de produção do estoque empresarial"}, "24h"),
            "consumption": Indicator(inputs + players, OK, {"recipe_inputs": inputs, "player_consumption": players,
                                                           "note": "comprar ou vender não é consumir (17.7)"}, "24h")}


def available_stock(product_id: int) -> Indicator:
    """Oferta do Mercado agora (17.5). Sem sistema de oferta registrado, é "Sem dados" (não 0)."""
    supply = rollup.supply_now()
    if supply is None:
        return _no_data("agora", why="o Mercado ainda não tem oferta registrada")
    return Indicator(supply.get(product_id, 0), OK, {}, "agora")


# --- dias (agregados + dia corrente ao vivo) ------------------------------------------------------------------------------------

def _row(day: int, stat: Optional[DailyProductStat]) -> Dict[str, Any]:
    if stat is None:
        return {"day": day, "transactions": 0, "volume": 0, "value_cents": 0, "min_price_cents": None, "max_price_cents": None,
                "production": 0, "consumption": 0, "available_stock": None}
    return {"day": day, "transactions": stat.transactions, "volume": stat.volume, "value_cents": stat.value_cents,
            "min_price_cents": stat.min_price_cents, "max_price_cents": stat.max_price_cents, "production": stat.production,
            "consumption": stat.consumption, "available_stock": stat.available_stock}


def day_rows(product_id: int, first_day: int, last_day: int, now: int) -> List[Dict[str, Any]]:
    """Uma linha por dia de `first_day` a `last_day`: fechados dos agregados, o corrente ao vivo (nunca gravado)."""
    today = competence_day_of(now)
    rollup.ensure_closed(min(last_day, today - 1), at=now)
    stats = {s.day: s for s in DailyProductStat.objects.filter(product_id=product_id, day__gte=first_day, day__lte=min(last_day, today - 1))}
    rows = []
    for day in range(first_day, last_day + 1):
        if day == today:
            live = rollup.compute_day_for_product(day, product_id)
            rows.append({"day": day, **live, "available_stock": None})
        elif day < today:
            rows.append(_row(day, stats.get(day)))
        else:
            rows.append(_row(day, None))
    return rows


def _avg(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    volume = sum(r["volume"] for r in rows)
    if not volume:
        return None
    value = sum(r["value_cents"] for r in rows)
    return {"avg_cents": Decimal(value) / Decimal(volume), "value_cents": value, "volume": volume}


def trend(product_id: int, now: int) -> Indicator:
    """((média dos últimos 7 dias / média dos 7 dias anteriores) − 1) × 100, médias ponderadas pela quantidade (17.8)."""
    today = competence_day_of(now)
    rows = day_rows(product_id, today - 2 * TREND_DAYS + 1, today, now)
    prev, last = _avg(rows[:TREND_DAYS]), _avg(rows[TREND_DAYS:])
    if prev is None or last is None:
        return _no_data("7d vs 7d", last_7d=last, previous_7d=prev,
                        why="é preciso ter vendas nos dois períodos de 7 dias")
    pct = (last["avg_cents"] / prev["avg_cents"] - 1) * 100
    return Indicator(pct, OK, {"last_7d": last, "previous_7d": prev, "formula": "(média 7d / média 7d anteriores − 1) × 100"}, "7d vs 7d")


def product_stats(product_key: str, now: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Visão principal da página do Produto (17.12). None se o produto não existe."""
    product = catalog.get_product(product_key)
    if product is None:
        return None
    now = game_clock.now() if now is None else now
    rng = price_range_24h(product.pk, now)
    use = usage_24h(product.pk, now)
    return {"product": product.key, "name": product.name, "now": now,
            "avg_price": avg_price_24h(product.pk, now), "min_price": rng["min"], "max_price": rng["max"],
            "available_stock": available_stock(product.pk), "production": use["production"], "consumption": use["consumption"],
            "trend": trend(product.pk, now)}


def charts(product_key: str, now: Optional[int] = None, days: int = CHART_DAYS) -> Optional[Dict[str, Any]]:
    """Séries de 30 dias (17.13): preço médio, e estoque/produção/consumo; os mesmos dados dos agregados. Dia sem venda: preço None."""
    product = catalog.get_product(product_key)
    if product is None:
        return None
    now = game_clock.now() if now is None else now
    today = competence_day_of(now)
    rows = day_rows(product.pk, today - days + 1, today, now)
    price, supply = [], []
    for r in rows:
        avg = _avg([r])
        price.append({"day": r["day"], "avg_price_cents": None if avg is None else avg["avg_cents"], "volume": r["volume"]})
        supply.append({"day": r["day"], "available_stock": r["available_stock"], "production": r["production"],
                       "consumption": r["consumption"]})
    return {"product": product.key, "days": days, "price": price, "supply_demand": supply}


def market_overview(now: Optional[int] = None, limit: int = 5) -> Dict[str, Any]:
    """Página geral (17.11): maiores altas, maiores quedas e maiores volumes (24 h) entre produtos com dados suficientes."""
    now = game_clock.now() if now is None else now
    ids = list(MarketTransaction.objects.filter(at__gt=now - (2 * TREND_DAYS + 1) * 86_400, at__lte=now)
               .order_by().values_list("product_id", flat=True).distinct())
    trends, volumes = [], []
    from catalog.models import Product
    keys = dict(Product.objects.filter(pk__in=ids).values_list("pk", "key"))
    for pid in ids:
        t = trend(pid, now)
        if t.status == OK:
            trends.append({"product": keys[pid], "trend_pct": t.value})
        agg = _window_sales(pid, now).aggregate(q=Sum("quantity"), v=Sum("total_cents"))
        if agg["q"]:
            volumes.append({"product": keys[pid], "volume": agg["q"], "value_cents": agg["v"]})
    return {"risers": sorted([t for t in trends if t["trend_pct"] > 0], key=lambda t: (-t["trend_pct"], t["product"]))[:limit],
            "fallers": sorted([t for t in trends if t["trend_pct"] < 0], key=lambda t: (t["trend_pct"], t["product"]))[:limit],
            "top_volume": sorted(volumes, key=lambda v: (-v["value_cents"], v["product"]))[:limit]}
