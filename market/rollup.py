"""
Agregação diária (design/17 §17.10, §17.19): histórico bruto → agregado do dia FECHADO → páginas consultam os agregados.

  - `compute_day(day)` recalcula, só LENDO as tabelas brutas imutáveis, o agregado de um dia por produto (vendas, produção e consumo
    reais) e os custos da empresa; é determinístico e a auditoria o compara com o que está gravado.
  - `ensure_closed(through_day)` grava os dias fechados que faltam (idempotente, um `RollupMark` por dia, seguro com concorrência).
    O tick diário do mundo fecha o dia que acabou; consultas fecham o que faltar sob demanda, então a correção NÃO depende do tick.
  - O dia corrente nunca é gravado: as páginas o calculam ao vivo (bounded por índices de tempo).

Produção = movimentos `production` do estoque empresarial; consumo = insumos consumidos pelas receitas (`input_consumption`) +
consumo do jogador (`consumption` do inventário). Comprar/vender NÃO é consumir (17.7). Compra e venda não entram nesses números.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Min, Sum

from core import clock as game_clock
from core import ticks
from core.timeline import TickKind, game_ts
from ledger.constants import AccountKind, Nature
from ledger.models import Entry
from ledger.money import competence_day_of

from .constants import CostCategory
from .models import CompanyCostDay, DailyProductStat, MarketTransaction, RollupMark

TICK_NAME = "market_daily_rollup"
_COST_NATURES = {Nature.WAGE.value: CostCategory.SALARIES, Nature.OWNER_SALARY.value: CostCategory.SALARIES}
_TAX_NATURES = tuple(n.value for n in Nature if n.value.startswith("tax_"))

SupplyProvider = Callable[[], Dict[int, int]]
_supply_providers: Dict[str, SupplyProvider] = {}


def register_supply_provider(name: str, fn: SupplyProvider) -> None:
    """Quem implementa a OFERTA do Mercado informa {product_id: quantidade disponível para venda agora} (17.5)."""
    if name in _supply_providers:
        raise ValueError(f"Provedor de oferta duplicado: {name}")
    _supply_providers[name] = fn


def unregister_supply_provider(name: str) -> None:        # para testes
    _supply_providers.pop(name, None)


def supply_now() -> Optional[Dict[int, int]]:
    """Oferta disponível por produto agora; None se nenhum sistema de oferta existe (≠ 0: não há dado)."""
    if not _supply_providers:
        return None
    total: Dict[int, int] = {}
    for name in sorted(_supply_providers):
        for product_id, qty in _supply_providers[name]().items():
            total[product_id] = total.get(product_id, 0) + qty
    return total


def day_bounds(day: int) -> Tuple[int, int]:
    """[início, fim) do dia de competência (calendário local do jogo)."""
    d, n = date.fromordinal(day), date.fromordinal(day + 1)
    return game_ts(d.year, d.month, d.day), game_ts(n.year, n.month, n.day)


def sales_by_product(day: int, product_id: Optional[int] = None) -> Dict[int, Dict[str, Any]]:
    qs = MarketTransaction.objects.filter(competence_day=day)
    if product_id is not None:
        qs = qs.filter(product_id=product_id)
    rows = qs.values("product_id").annotate(n=Count("id"), volume=Sum("quantity"), value=Sum("total_cents"),
                                            low=Min("unit_price_cents"), high=Max("unit_price_cents"))
    return {r["product_id"]: {"transactions": r["n"], "volume": r["volume"], "value_cents": r["value"],
                              "min_price_cents": r["low"], "max_price_cents": r["high"]} for r in rows}


def usage_by_product(day: int, product_id: Optional[int] = None) -> Dict[int, Dict[str, int]]:
    """Produção e consumo reais do dia por produto, das trilhas imutáveis do estoque empresarial e do inventário."""
    from companies.models import StockMovement
    from inventory.models import InventoryMovement
    start, end = day_bounds(day)
    out: Dict[int, Dict[str, int]] = {}

    def add(pid: int, field: str, qty: int) -> None:
        out.setdefault(pid, {"production": 0, "consumption": 0})[field] += qty

    stock = StockMovement.objects.filter(at__gte=start, at__lt=end, operation__in=("production", "input_consumption"))
    inv = InventoryMovement.objects.filter(at__gte=start, at__lt=end, operation="consumption")
    if product_id is not None:
        stock, inv = stock.filter(product_id=product_id), inv.filter(product_id=product_id)
    for r in stock.values("product_id", "operation").annotate(q=Sum("delta")):
        if r["operation"] == "production":
            add(r["product_id"], "production", r["q"])
        else:
            add(r["product_id"], "consumption", -r["q"])
    for r in inv.values("product_id").annotate(q=Sum("delta")):
        add(r["product_id"], "consumption", -r["q"])
    return out


def costs_by_company(day: int, company_id: Optional[int] = None) -> Dict[Tuple[int, str], int]:
    """Custos do dia por (empresa, categoria): insumos comprados (vendas do histórico), salários e impostos pagos pela conta da empresa."""
    from catalog.models import Product
    out: Dict[Tuple[int, str], int] = {}
    buys = MarketTransaction.objects.filter(competence_day=day, buyer_kind="company")
    if company_id is not None:
        buys = buys.filter(buyer_id=company_id)
    keys = dict(Product.objects.filter(pk__in=set(buys.values_list("product_id", flat=True))).values_list("pk", "key"))
    for r in buys.values("buyer_id", "product_id").annotate(v=Sum("total_cents")):
        out[(r["buyer_id"], CostCategory.INPUT_PREFIX + keys[r["product_id"]])] = r["v"]
    entries = Entry.objects.filter(competence_day=day, from_account__kind=AccountKind.COMPANY.value,
                                   nature__in=list(_COST_NATURES) + list(_TAX_NATURES), reverses__isnull=True, reversed_by__isnull=True)
    if company_id is not None:
        entries = entries.filter(from_account__owner_id=company_id)
    for r in entries.values("from_account__owner_id", "nature").annotate(v=Sum("amount")):
        category = _COST_NATURES.get(r["nature"], CostCategory.TAXES)
        key = (r["from_account__owner_id"], category)
        out[key] = out.get(key, 0) + r["v"]
    return out


def compute_day_for_product(day: int, product_id: int) -> Dict[str, Any]:
    """Linha do dia para UM produto, ao vivo (usada para o dia corrente, que nunca é gravado)."""
    row = {"transactions": 0, "volume": 0, "value_cents": 0, "min_price_cents": None, "max_price_cents": None,
           "production": 0, "consumption": 0}
    row.update(sales_by_product(day, product_id).get(product_id, {}))
    row.update(usage_by_product(day, product_id).get(product_id, {}))
    return row


def compute_day(day: int) -> Dict[str, Any]:
    """Agregado completo do dia, só lendo o histórico bruto: {product_id: {...}} e {(company, categoria): centavos}."""
    sales, usage = sales_by_product(day), usage_by_product(day)
    products: Dict[int, Dict[str, Any]] = {}
    for pid in set(sales) | set(usage):
        row = {"transactions": 0, "volume": 0, "value_cents": 0, "min_price_cents": None, "max_price_cents": None,
               "production": 0, "consumption": 0}
        row.update(sales.get(pid, {}))
        row.update(usage.get(pid, {}))
        products[pid] = row
    return {"products": products, "costs": costs_by_company(day)}


def first_active_day() -> Optional[int]:
    """Primeiro dia com atividade bruta relevante (vendas, produção/consumo, salários/impostos), ou None."""
    from companies.models import StockMovement
    from inventory.models import InventoryMovement
    ats = []
    for qs in (MarketTransaction.objects.order_by("at"),
               StockMovement.objects.filter(operation__in=("production", "input_consumption")).order_by("at"),
               InventoryMovement.objects.filter(operation="consumption").order_by("at"),
               Entry.objects.filter(from_account__kind=AccountKind.COMPANY.value,
                                    nature__in=list(_COST_NATURES) + list(_TAX_NATURES)).order_by("at")):
        first = qs.values_list("at", flat=True).first()
        if first is not None:
            ats.append(first)
    return competence_day_of(min(ats)) if ats else None


def close_day(day: int, *, at: Optional[int] = None, snapshot_supply: bool = False) -> bool:
    """Grava o agregado de UM dia fechado. Idempotente: False se o dia já estava fechado (nada é recalculado nem duplicado)."""
    at = game_clock.now() if at is None else at
    try:
        with transaction.atomic():
            RollupMark.objects.create(day=day, computed_at=at)
            data = compute_day(day)
            supply = supply_now() if snapshot_supply else None
            DailyProductStat.objects.bulk_create([
                DailyProductStat(product_id=pid, day=day, available_stock=None if supply is None else supply.get(pid, 0), **row)
                for pid, row in sorted(data["products"].items())])
            CompanyCostDay.objects.bulk_create([
                CompanyCostDay(company_id=company, day=day, category=category, amount_cents=amount)
                for (company, category), amount in sorted(data["costs"].items()) if amount > 0])
    except IntegrityError:
        return False
    return True


def ensure_closed(through_day: int, *, at: Optional[int] = None) -> List[int]:
    """Fecha todos os dias que faltam até `through_day` inclusive (só a partir do primeiro dia com atividade). Devolve os fechados."""
    span = RollupMark.objects.aggregate(lo=Min("day"), hi=Max("day"), n=Count("id"))
    if span["n"] and span["hi"] >= through_day and span["hi"] - span["lo"] + 1 == span["n"]:
        return []                                      # caminho rápido: dias fechados contíguos até `through_day` (1 consulta)
    first = first_active_day()
    if first is None or first > through_day:
        return []
    done = set(RollupMark.objects.filter(day__gte=first, day__lte=through_day).values_list("day", flat=True))
    closed = []
    for day in range(first, through_day + 1):
        if day not in done and close_day(day, at=at):
            closed.append(day)
    return closed


def _daily_tick(tick, ctx) -> None:
    """Tick diário do mundo: o dia que acabou de fechar (e qualquer atraso) é agregado, com o retrato da oferta quando existe."""
    through = competence_day_of(tick.at) - 1
    ensure_closed(through - 1, at=tick.at)
    first = first_active_day()
    if first is not None and first <= through:
        # o retrato da oferta só vale se o tick está sendo processado no próprio dia dele; num tick atrasado, a oferta "de agora"
        # seria atribuída a um dia antigo (dado errado): nesse caso fica NULL (sem dado)
        close_day(through, at=tick.at, snapshot_supply=competence_day_of(game_clock.now()) == competence_day_of(tick.at))


def register() -> None:
    ticks.register(ticks.WORLD, TickKind.DAILY, TICK_NAME, priority=90)(_daily_tick)
