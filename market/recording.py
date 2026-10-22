"""
Histórico de transações (design/17 §17.2): `record_sale` é chamado por quem CONCLUI uma venda (Varejo, entre empresas, Mercado de
Jogadores, contratos), na MESMA transação do pagamento, DEPOIS de o dinheiro ter se movido. O registro só nasce se o registro monetário
tiver o lançamento `SALE` do comprador ao vendedor pelo valor total: não existe venda no histórico sem dinheiro real movido
(conservação, `24`) e não existe estatística de mercado inventada (17.9, 17.20).

Esta camada NÃO decide preço, anúncio, taxa nem quem pode vender: o mecanismo do Mercado é de outro documento (ver CHANGELOG_DEV,
P1.05). Ela só registra o que aconteceu e deixa o histórico completo, imutável e auditável.
"""
from __future__ import annotations

from typing import Any, Optional

from django.db import IntegrityError, transaction

from catalog import services as catalog
from ledger import services as ledger
from ledger.constants import AccountKind, Nature
from ledger.models import Entry
from ledger.money import competence_day_of
from players.models import Player
from players.services import ActionResult

from .constants import MAX_QUANTITY, MAX_UNIT_PRICE_CENTS, Channel, PartyKind
from .models import MarketTransaction


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def party_account_id(kind: PartyKind, entity_id: int) -> Optional[int]:
    """Conta do registro monetário do jogador/empresa, ou None se a entidade não existe."""
    if kind is PartyKind.PLAYER:
        return ledger.player_account(entity_id).pk if Player.objects.filter(pk=entity_id).exists() else None
    from companies.models import Company
    return ledger.get_or_create_account(AccountKind.COMPANY, entity_id).pk if Company.objects.filter(pk=entity_id).exists() else None


def record_sale(*, product_key: Any, quantity: Any, unit_price_cents: Any, buyer_kind: Any, buyer_id: Any, seller_kind: Any,
                seller_id: Any, channel: Any, ledger_key: Any) -> ActionResult:
    """
    Registra uma venda CONCLUÍDA. Idempotente por `ledger_key` (a chave da transação do pagamento). Recusas: UNKNOWN_PRODUCT,
    INVALID_QUANTITY, INVALID_PRICE, INVALID_PARTY, INVALID_CHANNEL, INVALID_PARTIES (comprador = vendedor), PARTY_NOT_FOUND,
    PAYMENT_NOT_FOUND (sem o lançamento SALE do comprador ao vendedor pelo valor total), IDEMPOTENCY_CONFLICT.
    """
    product = catalog.get_product(product_key) if isinstance(product_key, str) else None
    if product is None:
        return _refuse("UNKNOWN_PRODUCT", key=repr(product_key)[:40])
    if not _is_int(quantity) or not 0 < quantity <= MAX_QUANTITY:
        return _refuse("INVALID_QUANTITY", quantity=repr(quantity)[:40], max=MAX_QUANTITY)
    if not _is_int(unit_price_cents) or not 0 < unit_price_cents <= MAX_UNIT_PRICE_CENTS:
        return _refuse("INVALID_PRICE", unit_price_cents=repr(unit_price_cents)[:40], why="preço unitário em centavos inteiros > 0")
    try:
        b_kind, s_kind, chan = PartyKind(buyer_kind), PartyKind(seller_kind), Channel(channel)
    except ValueError:
        bad = [("buyer_kind", buyer_kind), ("seller_kind", seller_kind), ("channel", channel)]
        code = "INVALID_CHANNEL" if channel not in {c.value for c in Channel} else "INVALID_PARTY"
        return _refuse(code, **{k: repr(v)[:40] for k, v in bad})
    if not _is_int(buyer_id) or not _is_int(seller_id) or buyer_id <= 0 or seller_id <= 0:
        return _refuse("INVALID_PARTY", buyer_id=repr(buyer_id)[:40], seller_id=repr(seller_id)[:40])
    if (b_kind, buyer_id) == (s_kind, seller_id):
        return _refuse("INVALID_PARTIES", why="comprador e vendedor são a mesma entidade")
    if not isinstance(ledger_key, str) or not ledger_key:
        return _refuse("PAYMENT_NOT_FOUND", ledger_key=repr(ledger_key)[:40])
    total = quantity * unit_price_cents
    with transaction.atomic():
        existing = MarketTransaction.objects.filter(ledger_key=ledger_key).select_related("product").first()
        if existing is not None:
            return _same_or_conflict(existing, product.pk, quantity, unit_price_cents, b_kind, buyer_id, s_kind, seller_id, chan)
        buyer_acc, seller_acc = party_account_id(b_kind, buyer_id), party_account_id(s_kind, seller_id)
        if buyer_acc is None or seller_acc is None:
            return _refuse("PARTY_NOT_FOUND", buyer=buyer_acc is not None, seller=seller_acc is not None)
        sale = [e for e in Entry.objects.filter(transaction__key=ledger_key, nature=Nature.SALE.value, reversed_by__isnull=True)
                if e.from_account_id == buyer_acc and e.to_account_id == seller_acc and e.amount == total]
        if len(sale) != 1:
            return _refuse("PAYMENT_NOT_FOUND", ledger_key=ledger_key, total_cents=total,
                           why="não há UM lançamento SALE do comprador ao vendedor pelo valor total")
        at = sale[0].at
        try:
            with transaction.atomic():
                tx = MarketTransaction.objects.create(
                    product=product, quantity=quantity, unit_price_cents=unit_price_cents, total_cents=total, at=at,
                    competence_day=competence_day_of(at), buyer_kind=b_kind.value, buyer_id=buyer_id, seller_kind=s_kind.value,
                    seller_id=seller_id, channel=chan.value, ledger_key=ledger_key)
        except IntegrityError:                                       # corrida pela mesma chave: vale a que chegou primeiro
            existing = MarketTransaction.objects.filter(ledger_key=ledger_key).select_related("product").first()
            if existing is None:
                raise
            return _same_or_conflict(existing, product.pk, quantity, unit_price_cents, b_kind, buyer_id, s_kind, seller_id, chan)
        return ActionResult(True, "OK", {"transaction": tx.pk, "product": product.key, "quantity": quantity,
                                         "unit_price_cents": unit_price_cents, "total_cents": total, "at": at})


def _same_or_conflict(existing, product_id, quantity, unit_price, b_kind, buyer_id, s_kind, seller_id, chan) -> ActionResult:
    same = (existing.product_id, existing.quantity, existing.unit_price_cents, existing.buyer_kind, existing.buyer_id,
            existing.seller_kind, existing.seller_id, existing.channel) == (
        product_id, quantity, unit_price, b_kind.value, buyer_id, s_kind.value, seller_id, chan.value)
    return (ActionResult(True, "OK", {"already_applied": True, "transaction": existing.pk}) if same
            else _refuse("IDEMPOTENCY_CONFLICT", ledger_key=existing.ledger_key))
