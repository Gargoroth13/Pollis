"""
Auditoria do Inventário (design/05 §19): reconstrói a posse a partir da trilha de movimentos e confere os envios com o registro
monetário. Só LÊ. Invariantes (numeração própria deste app):
  1  posse positiva e igual à soma dos movimentos de (jogador, produto); `quantity_after` acompanha a soma corrente
  2  sinal do movimento coerente com o tipo da operação (entra +, sai −) e operação conhecida
  4  consumo automático (04 §16): operação de consumo, de alimento, e só com Nutrição abaixo do limiar do design
  3  envio: um movimento de saída e um de entrada, de mesma quantidade, com a mesma referência; a taxa do envio tem o
     lançamento `MAIL_FEE` correspondente (jogador → União, valor = taxa)
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Dict, Tuple

from ledger.audit import AuditReport
from ledger.constants import Nature
from ledger.models import Entry
from ledger import services as ledger

from .constants import (AUTO_CONSUME_BELOW, AUTO_CONSUMPTION_REFERENCE, CREDIT_OPERATIONS, DEBIT_OPERATIONS, Operation)
from .models import InventoryItem, InventoryMovement, Shipment


def _audit_automatic(report: AuditReport, m: InventoryMovement) -> None:
    ex = m.explained or {}
    try:
        before = Decimal(str(ex.get("nutrition_before")))
    except InvalidOperation:
        before = None
    if m.operation != Operation.CONSUMPTION.value or ex.get("automatic") is not True:
        report.add(4, "AUTO_CONSUMPTION_NOT_A_CONSUMPTION", movement=m.pk, operation=m.operation)
    if before is None or before >= AUTO_CONSUME_BELOW:
        report.add(4, "AUTO_CONSUMPTION_ABOVE_THRESHOLD", movement=m.pk, nutrition_before=ex.get("nutrition_before"))
    if not hasattr(m.product, "food"):
        report.add(4, "AUTO_CONSUMPTION_NOT_FOOD", movement=m.pk, product=m.product_id)


def audit_inventory() -> AuditReport:
    report = AuditReport()
    credit_ops = {o.value for o in CREDIT_OPERATIONS}
    debit_ops = {o.value for o in DEBIT_OPERATIONS}
    running: Dict[Tuple[int, int], int] = defaultdict(int)
    movements = 0
    for m in InventoryMovement.objects.select_related("product").order_by("id").iterator():
        movements += 1
        if m.operation not in credit_ops | debit_ops:
            report.add(2, "UNKNOWN_OPERATION", movement=m.pk, operation=m.operation)
        elif (m.operation in credit_ops and m.delta <= 0) or (m.operation in debit_ops and m.delta >= 0):
            report.add(2, "OPERATION_SIGN_MISMATCH", movement=m.pk, operation=m.operation, delta=m.delta)
        if m.reference_kind == AUTO_CONSUMPTION_REFERENCE:
            _audit_automatic(report, m)
        pair = (m.player_id, m.product_id)
        running[pair] += m.delta
        if running[pair] != m.quantity_after:
            report.add(1, "QUANTITY_AFTER_MISMATCH", movement=m.pk, expected=running[pair], recorded=m.quantity_after)
    items = {(i.player_id, i.product_id): i.quantity for i in InventoryItem.objects.all()}
    for pair, total in running.items():
        if items.get(pair, 0) != total:
            report.add(1, "HOLDING_MISMATCH", player=pair[0], product=pair[1], holding=items.get(pair, 0), movements=total)
    for pair, quantity in items.items():
        if pair not in running:
            report.add(1, "HOLDING_WITHOUT_MOVEMENTS", player=pair[0], product=pair[1], holding=quantity)
        if quantity <= 0:
            report.add(1, "HOLDING_NOT_POSITIVE", player=pair[0], product=pair[1], holding=quantity)

    shipments = 0
    for s in Shipment.objects.order_by("id").iterator():
        shipments += 1
        by_op = {m.operation: m for m in InventoryMovement.objects.filter(reference_kind="shipment", reference_id=str(s.pk))}
        out, inn = by_op.get(Operation.TRANSFER_OUT.value), by_op.get(Operation.TRANSFER_IN.value)
        if out is None or inn is None or len(by_op) != 2:
            report.add(3, "SHIPMENT_MOVEMENTS_MISSING", shipment=s.pk)
        else:
            if not (out.delta == -s.quantity and inn.delta == s.quantity and out.player_id == s.sender_id
                    and inn.player_id == s.recipient_id and out.product_id == inn.product_id == s.product_id):
                report.add(3, "SHIPMENT_MOVEMENT_MISMATCH", shipment=s.pk)
        if s.fee > 0:
            entry = Entry.objects.filter(transaction__key=s.ledger_key, nature=Nature.MAIL_FEE.value).first() \
                if s.ledger_key else None
            if entry is None:
                report.add(3, "SHIPMENT_FEE_ENTRY_MISSING", shipment=s.pk, fee=s.fee)
            elif (entry.amount != s.fee or entry.from_account.owner_id != s.sender_id
                  or entry.to_account_id != ledger.union_account().pk):
                report.add(3, "SHIPMENT_FEE_ENTRY_MISMATCH", shipment=s.pk, fee=s.fee, entry=entry.seq)
    report.stats.update({"movements": movements, "holdings": len(items), "shipments": shipments,
                         "units": sum(items.values())})
    return report
