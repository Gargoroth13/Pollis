"""
Estoque empresarial (design/02 §11.1, §19; 05 §17): posse de Produtos do catálogo por EMPRESA, distinta do inventário do jogador
(mesmos Produtos, outra estrutura). Quantidades inteiras; trilha imutável; capacidade por estrela.

PROTOCOLO: quem altera o estoque trava ANTES a linha da empresa (`Company`, depois do jogador, quando há) — ela serializa
produção, compras e vendas da empresa; só então toca `StockItem`/`StockMovement`. Esta camada NÃO move dinheiro: quem compra ou
vende liga o pagamento (registro monetário) ao movimento, na MESMA transação e na ordem do protocolo.

Nada nasce sem origem: produção (Trabalho de funcionário) e `PURCHASE`; nada some sem destino: insumo consumido e `SALE`.
Entrada externa (`credit_stock`) só aceita `PURCHASE`; saída externa (`debit_stock`) só `SALE` — a produção e o consumo de insumo
só existem dentro de `production`.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction

from catalog import services as catalog
from catalog.models import Product
from core import clock as game_clock
from core.breakdown import Calc, Explained
from players.services import ActionResult

from . import params
from .constants import (EXTERNAL_STOCK_CREDIT, EXTERNAL_STOCK_DEBIT, MAX_STOCK_QUANTITY, StockOperation)
from .models import Company, StockItem, StockMovement

_QUANTUM = Decimal("0.000001")


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def capacity_of(stars: int) -> Explained:
    """Estoque máximo (unidades) da estrela (02 §11.1; `[PROV]` em `params`), com o detalhamento (20)."""
    return Calc("stock_capacity", params.STOCK_CAPACITY_PER_STAR[stars]).result(game_clock.now())


def used_of(company_id: int) -> int:
    return sum(StockItem.objects.filter(company_id=company_id).values_list("quantity", flat=True))


def quantity_of(company_id: int, product_key: str) -> int:
    return StockItem.objects.filter(company_id=company_id, product__key=product_key).values_list("quantity", flat=True).first() or 0


def stock_of(company_id: int) -> List[Dict[str, Any]]:
    """Leitura do estoque: produto, quantidade e qualidade média (None = desconhecida)."""
    return [{"product": i.product.key, "name": i.product.name, "quantity": i.quantity, "quality": i.quality}
            for i in StockItem.objects.filter(company_id=company_id).select_related("product").order_by("product__key")]


def _quantity_problem(quantity: Any) -> Optional[ActionResult]:
    if not isinstance(quantity, int) or isinstance(quantity, bool) or not 0 < quantity <= MAX_STOCK_QUANTITY:
        return _refuse("INVALID_QUANTITY", quantity=repr(quantity)[:40], max=MAX_STOCK_QUANTITY)
    return None


def _blend(have: int, old: Optional[Decimal], add: int, new: Optional[Decimal]) -> Optional[Decimal]:
    """Qualidade média por unidade depois de somar `add` unidades de qualidade `new`. Desconhecida em qualquer lado → desconhecida."""
    if have == 0:
        return None if new is None else new.quantize(_QUANTUM)
    if old is None or new is None:
        return None
    return ((old * have + new * add) / (have + add)).quantize(_QUANTUM)


def apply_locked(company: Company, product: Product, delta: int, operation: StockOperation, *, origin: str, destination: str,
                 key: str, reference_kind: str, reference_id, at: int, actor: Optional[int] = None,
                 quality: Optional[Decimal] = None, explained: Optional[Dict[str, Any]] = None) -> ActionResult:
    """
    UM movimento sobre uma empresa JÁ travada, dentro de uma transação. Entrada respeita a capacidade da estrela (STOCK_FULL);
    saída exige quantidade (INSUFFICIENT_STOCK). Idempotente por `key`: mesmo conteúdo = repetição; outro = IDEMPOTENCY_CONFLICT.
    """
    existing = StockMovement.objects.filter(key=key).first()
    if existing is not None:
        same = (existing.company_id, existing.product_id, existing.delta, existing.operation) == (
            company.pk, product.pk, delta, operation.value)
        return (ActionResult(True, "OK", {"already_applied": True, "movement": existing.pk, "quantity": existing.quantity_after})
                if same else _refuse("IDEMPOTENCY_CONFLICT", key=key))
    item = StockItem.objects.select_for_update().filter(company=company, product=product).first()
    have = item.quantity if item is not None else 0
    after = have + delta
    if after < 0:
        return _refuse("INSUFFICIENT_STOCK", have=have, required=-delta, product=product.key)
    if delta > 0:
        capacity = capacity_of(company.stars)
        used = used_of(company.pk)
        if used + delta > int(capacity.value):
            return _refuse("STOCK_FULL", used=used, adding=delta, capacity=int(capacity.value), explained=capacity.to_dict())
    new_quality = (_blend(have, item.quality if item else None, delta, quality) if delta > 0 else
                   (item.quality if item is not None else None))
    if item is None:
        item = StockItem.objects.create(company=company, product=product, quantity=after, quality=new_quality)
    elif after == 0:
        item.delete()
    else:
        item.quantity, item.quality = after, new_quality
        item.save(update_fields=["quantity", "quality"])
    movement = StockMovement.objects.create(
        company=company, product=product, delta=delta, quantity_after=after, quality_after=None if after == 0 else new_quality,
        operation=operation.value, key=key, reference_kind=reference_kind, reference_id=str(reference_id), origin=origin,
        destination=destination, actor=actor, at=at, explained=explained or {})
    return ActionResult(True, "OK", {"movement": movement.pk, "quantity": after, "delta": delta, "product": product.key,
                                     "quality": None if after == 0 else new_quality})


def _external(company_id: Any, product_key: Any, quantity: Any, operation: StockOperation, allowed, *, origin, destination,
              key, reference_kind, reference_id, at, quality, explained, sign: int) -> ActionResult:
    if operation not in allowed:
        return _refuse("OPERATION_NOT_ALLOWED", operation=getattr(operation, "value", str(operation)),
                       allowed=sorted(o.value for o in allowed))
    problem = _quantity_problem(quantity)
    if problem is not None:
        return problem
    if not (isinstance(origin, str) and origin and isinstance(destination, str) and destination and isinstance(key, str) and key
            and isinstance(reference_kind, str) and reference_kind and str(reference_id)):
        return _refuse("INVALID_PARAMS", why="origem, destino, chave e referência são obrigatórios")
    if quality is not None and (isinstance(quality, float) or Decimal(quality) < 0):
        return _refuse("INVALID_QUALITY", quality=repr(quality)[:40])
    product = catalog.get_product(product_key) if isinstance(product_key, str) else None
    if product is None:
        return _refuse("UNKNOWN_PRODUCT", key=repr(product_key)[:40])
    if isinstance(company_id, bool) or not isinstance(company_id, int) or not Company.objects.filter(pk=company_id).exists():
        return _refuse("COMPANY_NOT_FOUND", company=repr(company_id)[:40])
    if sign > 0 and operation is StockOperation.PURCHASE:
        from . import trade                                                                   # 02 §4: só compra o que tem uso válido
        refusal = trade.purchase_refusal(company_id, product_key)
        if refusal is not None:
            return refusal
    with transaction.atomic():
        company = Company.objects.select_for_update().get(pk=company_id)                     # protocolo: a empresa primeiro
        return apply_locked(company, product, sign * quantity, operation, origin=origin, destination=destination, key=key,
                            reference_kind=reference_kind, reference_id=reference_id,
                            at=game_clock.now() if at is None else at, quality=None if quality is None else Decimal(quality),
                            explained=explained)


def credit_stock(company_id: int, product_key: str, quantity: int, *, operation: StockOperation = StockOperation.PURCHASE,
                 origin: str, key: str, reference_kind: str, reference_id, quality=None, at: Optional[int] = None,
                 explained: Optional[Dict[str, Any]] = None) -> ActionResult:
    """
    Entrada por um sistema com origem documentada: hoje só `PURCHASE` (compra; P1.05/P1.08). Idempotente por `key`. NÃO move
    dinheiro: quem compra liga o pagamento à entrada, na mesma transação. Recusas: OPERATION_NOT_ALLOWED, INVALID_QUANTITY,
    INVALID_PARAMS, INVALID_QUALITY, UNKNOWN_PRODUCT, COMPANY_NOT_FOUND, STOCK_FULL, IDEMPOTENCY_CONFLICT e as da permissão de compra
    (02 §4, `trade.purchase_refusal`): PRODUCT_NOT_TRADABLE_BETWEEN_COMPANIES, NO_VALID_USE.
    """
    return _external(company_id, product_key, quantity, operation, EXTERNAL_STOCK_CREDIT, origin=origin,
                     destination=f"company:{company_id}", key=key, reference_kind=reference_kind, reference_id=reference_id,
                     at=at, quality=quality, explained=explained, sign=1)


def debit_stock(company_id: int, product_key: str, quantity: int, *, operation: StockOperation = StockOperation.SALE,
                destination: str, key: str, reference_kind: str, reference_id, at: Optional[int] = None,
                explained: Optional[Dict[str, Any]] = None) -> ActionResult:
    """Saída por um sistema com destino documentado: hoje só `SALE`. O insumo da produção só sai dentro do Trabalho."""
    return _external(company_id, product_key, quantity, operation, EXTERNAL_STOCK_DEBIT, origin=f"company:{company_id}",
                     destination=destination, key=key, reference_kind=reference_kind, reference_id=reference_id, at=at,
                     quality=None, explained=explained, sign=-1)
