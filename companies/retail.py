"""
Varejo (design/02 §11): estoque ≠ capacidade de venda.

  - **Estoque** (`stock.py`): máximo pela estrela.
  - **Capacidade de venda**: o Trabalhar do Vendedor (`support.record_support_work`) soma capacidade ao DIA da empresa
    (`base × skill (Carisma) × especialização`, `[PROV]`). A capacidade do dia é `floor(soma das contribuições)`; cada venda consome
    1 unidade de estoque E 1 de capacidade; o que sobrar não passa para o dia seguinte ("naquele ciclo", §11.2).
  - `fulfill_sale` é o serviço que o mercado (P1.05) chama quando um jogador compra do Varejo: vende o que o catálogo declara com o
    canal `retail_sale` (02 §4; Varejo vende o bem final aos jogadores). NÃO move dinheiro: quem vende liga o pagamento (registro
    monetário) a esta chamada na MESMA transação, depois de ela devolver OK.

PROTOCOLO: jogador(es) → empresa (serializa estoque, capacidade e vendas) → registro monetário.
"""
from __future__ import annotations

from decimal import ROUND_FLOOR, Decimal
from typing import Any, Dict, Optional

from django.db import transaction
from django.db.models import Sum

from catalog import services as catalog
from catalog.constants import Channel
from core import clock as game_clock
from core.breakdown import Calc, Explained
from ledger.money import competence_day_of
from players.services import ActionResult

from . import stock, support
from .constants import CompanyType, PositionKind, StockOperation
from .models import Company, SalesCapacityUse


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def capacity_status(company_id: int, now: Optional[int] = None) -> Dict[str, Any]:
    """Capacidade de venda do dia com o detalhamento (20): produzida (soma), inteira, usada, disponível."""
    now = game_clock.now() if now is None else now
    day = competence_day_of(now)
    produced = support.daily_total(company_id, PositionKind.SALESPERSON.value, day)
    whole = int(produced["total"].to_integral_value(rounding=ROUND_FLOOR))
    used = SalesCapacityUse.objects.filter(company_id=company_id, competence_day=day).aggregate(n=Sum("quantity"))["n"] or 0
    available: Explained = (Calc("sales_capacity_produced_today", whole).add("sales_capacity_used_today", -used).result(now))
    return {"day": day, "works": produced["works"], "produced": produced["total"], "whole": whole, "used": used,
            "available": max(0, int(available.value)), "explained": available}


def sale_refusal(company_id: Any, product_key: Any, quantity: Any) -> Optional[ActionResult]:
    """Recusas que só LEEM (o serviço usa as mesmas): tipo, produto, canal e quantidade."""
    if isinstance(company_id, bool) or not isinstance(company_id, int):
        return _refuse("COMPANY_NOT_FOUND", company=repr(company_id)[:40])
    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return _refuse("COMPANY_NOT_FOUND", company=company_id)
    if CompanyType(company.type) is not CompanyType.RETAIL:
        return _refuse("COMPANY_TYPE_CANNOT_SELL_TO_PLAYERS", company_type=company.type)
    if not isinstance(product_key, str) or catalog.get_product(product_key) is None:
        return _refuse("UNKNOWN_PRODUCT", key=repr(product_key)[:40])
    if not catalog.has_channel(product_key, Channel.RETAIL_SALE):
        return _refuse("PRODUCT_NOT_SOLD_AT_RETAIL", product=product_key)
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        return _refuse("INVALID_QUANTITY", quantity=repr(quantity)[:40])
    return None


def fulfill_sale(company_id: int, product_key: str, quantity: int, *, destination: str, key: str, reference_kind: str,
                 reference_id, actor: Optional[int] = None, at: Optional[int] = None) -> ActionResult:
    """
    Uma venda do Varejo: consome `quantity` de estoque (`SALE`) e de capacidade de venda do dia. Idempotente por `key`.
    Recusas: COMPANY_NOT_FOUND, COMPANY_TYPE_CANNOT_SELL_TO_PLAYERS, UNKNOWN_PRODUCT, PRODUCT_NOT_SOLD_AT_RETAIL, INVALID_QUANTITY,
    INVALID_PARAMS, SALES_CAPACITY_EXCEEDED (o detalhe traz o que há), INSUFFICIENT_STOCK, IDEMPOTENCY_CONFLICT.
    """
    refusal = sale_refusal(company_id, product_key, quantity)
    if refusal is not None:
        return refusal
    if not (isinstance(destination, str) and destination and isinstance(key, str) and key and isinstance(reference_kind, str)
            and reference_kind and str(reference_id)):
        return _refuse("INVALID_PARAMS", why="destino, chave e referência são obrigatórios")
    now = game_clock.now() if at is None else at
    with transaction.atomic():
        company = Company.objects.select_for_update().get(pk=company_id)                    # protocolo: a empresa primeiro
        existing = SalesCapacityUse.objects.filter(key=key).first()
        if existing is not None:
            same = (existing.company_id, existing.product.key, existing.quantity) == (company_id, product_key, quantity)
            return (ActionResult(True, "OK", {"already_applied": True, "quantity": existing.quantity}) if same
                    else _refuse("IDEMPOTENCY_CONFLICT", key=key))
        status = capacity_status(company_id, now)
        if quantity > status["available"]:
            return _refuse("SALES_CAPACITY_EXCEEDED", requested=quantity, available=status["available"],
                           explained=status["explained"].to_dict())
        moved = stock.apply_locked(company, catalog.get_product(product_key), -quantity, StockOperation.SALE,
                                   origin=f"company:{company_id}", destination=destination, key=key,
                                   reference_kind=reference_kind, reference_id=reference_id, at=now, actor=actor,
                                   explained={"sales_capacity_before": status["available"]})
        if not moved.ok:
            return moved
        SalesCapacityUse.objects.create(company=company, product=catalog.get_product(product_key), quantity=quantity,
                                        competence_day=status["day"], at=now, key=key, destination=destination, actor=actor)
        return ActionResult(True, "OK", {"product": product_key, "quantity": quantity, "stock_after": moved.detail["quantity"],
                                         "capacity_after": status["available"] - quantity, "day": status["day"]})
