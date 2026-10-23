"""
Auditoria dos Contratos (design/18). Só LÊ. Invariantes (numeração própria deste app):
  1  contrato: enumerações válidas; partes distintas; termos intactos (`terms_hash` = termos atuais, 18.4); aceites coerentes com o estado
     (em vigor/encerrado depois de vigor ⇒ as duas partes aceitaram); contadores = execuções registradas (próxima sequência,
     falhas); agenda coerente com a regra do tipo (próximo vencimento, última ocorrência); estado terminal com motivo e instante
  2  histórico: eventos contínuos 1..n por contrato, começando por CREATED; cada aceite, ativação, execução, falha, multa e
     encerramento do estado tem seu evento; nenhum evento sem a coisa a que se refere
  3  dinheiro e estoque: cada ocorrência cumprida tem os lançamentos que o tipo exige, pelos valores dos termos (fornecimento: SALE
     líquida + TAX_SALES = bruto, vendas registradas no mercado com canal `contract`, estoque saindo do vendedor e entrando no
     comprador; empréstimo: desembolso do principal, parcela = principal + juros); cada ocorrência falha tem a pendência registrada
     (dívida no registro monetário quando o tipo a usa); a multa é UMA transferência (ou dívida) pelo valor dos termos, do responsável
  4  nenhuma chave de execução órfã: todo lançamento/estoque `contract:{id}:exec:{n}` tem a ocorrência registrada
"""
from __future__ import annotations

from typing import Dict, List

from companies.models import StockMovement
from ledger.audit import AuditReport
from ledger.constants import Nature
from ledger.models import Entry, Obligation, Transaction
from market.models import MarketTransaction
from market.recording import find_payment

from . import handlers
from .constants import (ENDED_STATUSES, KEY_PREFIX, REFERENCE_KIND, RUNNING_STATUSES, ContractType, EventKind, ExecutionStatus,
                        Frequency, PartyKind, Responsible, Side, Status)
from .models import Contract, ContractEvent, ContractExecution


def audit_contracts() -> AuditReport:
    report = AuditReport()
    n = 0
    seen_keys: Dict[int, set] = {}
    for c in Contract.objects.order_by("id"):
        n += 1
        _audit_contract(report, c)
        seen_keys[c.pk] = {e.sequence for e in c.executions.all()}
    report.stats["contracts"] = n
    _audit_orphans(report, seen_keys)
    return report


def _audit_contract(report: AuditReport, c: Contract) -> None:
    ctype = report.enum(ContractType, c.type, "Contract", "type", c.pk)
    status = report.enum(Status, c.status, "Contract", "status", c.pk)
    freq = report.enum(Frequency, c.frequency, "Contract", "frequency", c.pk)
    ak, bk = report.enum(PartyKind, c.party_a_kind, "Contract", "party_a_kind", c.pk), report.enum(
        PartyKind, c.party_b_kind, "Contract", "party_b_kind", c.pk)
    if None in (ctype, status, freq, ak, bk):
        return
    if (c.party_a_kind, c.party_a_id) == (c.party_b_kind, c.party_b_id):
        report.add(1, "SAME_PARTY", contract=c.pk)
    if c.terms_hash != c.frozen_digest():
        report.add(1, "TERMS_CHANGED", contract=c.pk)
    handler = handlers.get_handler(c.type)
    executions = list(c.executions.order_by("sequence"))
    events = list(c.events.order_by("seq"))
    started = c.activated_at is not None
    if status in RUNNING_STATUSES and not (c.accepted_a_at and c.accepted_b_at and started):
        report.add(1, "RUNNING_WITHOUT_ACCEPTANCES", contract=c.pk, status=c.status)
    if status is Status.PROPOSED and (started or (c.accepted_a_at and c.accepted_b_at)):
        report.add(1, "PROPOSED_BUT_STARTED", contract=c.pk)
    if status is Status.CANCELLED and started:
        report.add(1, "CANCELLED_AFTER_START", contract=c.pk)
    if status in ENDED_STATUSES and (c.ended_at is None or not c.end_reason):
        report.add(1, "ENDED_WITHOUT_REASON", contract=c.pk)
    if status not in ENDED_STATUSES and (c.ended_at is not None or c.end_reason):
        report.add(1, "NOT_ENDED_BUT_HAS_END", contract=c.pk)
    if status in (Status.CLOSED, Status.BROKEN) and not started:
        report.add(1, "ENDED_WITHOUT_START", contract=c.pk)
    if [e.sequence for e in executions] != list(range(len(executions))):
        report.add(1, "EXECUTION_SEQUENCE_GAP", contract=c.pk)
    if c.next_sequence != len(executions):
        report.add(1, "NEXT_SEQUENCE_MISMATCH", contract=c.pk, next=c.next_sequence, executions=len(executions))
    if c.failures != sum(1 for e in executions if e.status == ExecutionStatus.FAILED.value):
        report.add(1, "FAILURES_MISMATCH", contract=c.pk)
    if handler is not None and started:
        if status in RUNNING_STATUSES:
            expected_due = handler.due_day(c, c.next_sequence) if c.next_sequence < c.occurrences else None
            if c.next_due_day != expected_due:
                report.add(1, "NEXT_DUE_MISMATCH", contract=c.pk, next_due_day=c.next_due_day, expected=expected_due)
        elif c.next_due_day is not None:
            report.add(1, "ENDED_WITH_DUE_DAY", contract=c.pk)
        if c.last_due_day != handler.due_day(c, c.occurrences - 1):
            report.add(1, "LAST_DUE_MISMATCH", contract=c.pk)
        for e in executions:
            if e.due_day != handler.due_day(c, e.sequence):
                report.add(1, "EXECUTION_DUE_MISMATCH", contract=c.pk, sequence=e.sequence)
    if status is Status.CLOSED and (c.next_sequence != c.occurrences):
        report.add(1, "CLOSED_BEFORE_ALL_OCCURRENCES", contract=c.pk)
    _audit_events(report, c, events, executions, status)
    if handler is not None and started:
        _audit_money(report, c, handler, executions, events)


def _kinds(events: List[ContractEvent]) -> Dict[str, List[ContractEvent]]:
    out: Dict[str, List[ContractEvent]] = {}
    for e in events:
        out.setdefault(e.kind, []).append(e)
    return out


def _audit_events(report: AuditReport, c: Contract, events, executions, status: Status) -> None:
    if [e.seq for e in events] != list(range(1, len(events) + 1)):
        report.add(2, "EVENT_SEQUENCE_GAP", contract=c.pk)
    if not events or events[0].kind != EventKind.CREATED.value:
        report.add(2, "FIRST_EVENT_NOT_CREATED", contract=c.pk)
        return
    by = _kinds(events)
    accepted = {e.ref for e in by.get(EventKind.ACCEPTED.value, [])}
    for side, at in ((Side.A, c.accepted_a_at), (Side.B, c.accepted_b_at)):
        if (at is not None) != (side.value in accepted):
            report.add(2, "ACCEPTANCE_EVENT_MISMATCH", contract=c.pk, side=side.value)
    if (c.activated_at is not None) != bool(by.get(EventKind.ACTIVATED.value)):
        report.add(2, "ACTIVATION_EVENT_MISMATCH", contract=c.pk)
    for e in executions:
        kind = EventKind.EXECUTED if e.status == ExecutionStatus.SUCCESS.value else EventKind.FAILED
        if not any(ev.ref == str(e.sequence) for ev in by.get(kind.value, [])):
            report.add(2, "EXECUTION_EVENT_MISSING", contract=c.pk, sequence=e.sequence)
    n_events = len(by.get(EventKind.EXECUTED.value, [])) + len(by.get(EventKind.FAILED.value, []))
    if n_events != len(executions):
        report.add(2, "EXECUTION_EVENT_COUNT", contract=c.pk, events=n_events, executions=len(executions))
    terminal = {Status.CLOSED: EventKind.CLOSED, Status.BROKEN: EventKind.BROKEN}.get(status)
    if terminal is not None and len(by.get(terminal.value, [])) != 1:
        report.add(2, "TERMINAL_EVENT_MISMATCH", contract=c.pk, status=c.status)
    if status is Status.CANCELLED and len(by.get(EventKind.DECLINED.value, [])) + len(by.get(EventKind.WITHDRAWN.value, [])) != 1:
        report.add(2, "CANCEL_EVENT_MISMATCH", contract=c.pk)
    if status in (Status.PROPOSED, Status.ACTIVE, Status.DEFAULTED) and (by.get(EventKind.CLOSED.value) or by.get(EventKind.BROKEN.value)):
        report.add(2, "TERMINAL_EVENT_WITHOUT_STATE", contract=c.pk)
    if status is Status.DEFAULTED and not by.get(EventKind.DEFAULT_ENTERED.value):
        report.add(2, "DEFAULT_EVENT_MISSING", contract=c.pk)
    if len(by.get(EventKind.PENALTY_APPLIED.value, [])) > 1:
        report.add(2, "PENALTY_APPLIED_TWICE", contract=c.pk)


def _audit_money(report: AuditReport, c: Contract, handler, executions, events) -> None:
    by = _kinds(events)
    penalties = by.get(EventKind.PENALTY_APPLIED.value, [])
    for e in executions:
        key = f"{KEY_PREFIX}{c.pk}:exec:{e.sequence}"
        if e.status == ExecutionStatus.SUCCESS.value:
            if e.ledger_key != key:
                report.add(3, "EXECUTION_KEY_MISMATCH", contract=c.pk, sequence=e.sequence)
                continue
            if c.type == ContractType.SUPPLY.value:
                _audit_supply_success(report, c, e, key)
            elif c.type == ContractType.LOAN.value:
                _audit_loan_success(report, c, handler, e, key)
        else:
            if e.responsible not in {r.value for r in Responsible}:
                report.add(3, "FAILURE_WITHOUT_RESPONSIBLE", contract=c.pk, sequence=e.sequence)
            if e.pending_cents is None and e.pending_quantity is None:
                report.add(3, "FAILURE_WITHOUT_PENDING", contract=c.pk, sequence=e.sequence)
            if Transaction.objects.filter(key=key).exists() or StockMovement.objects.filter(key__startswith=f"{key}:").exists():
                report.add(3, "FAILED_EXECUTION_MOVED_RESOURCES", contract=c.pk, sequence=e.sequence)
            if handler.obligation_backed:
                parts = Obligation.objects.filter(reference_kind=REFERENCE_KIND, reference_id__startswith=f"{c.pk}:{e.sequence}:")
                if sum(o.amount_due for o in parts) != e.pending_cents:
                    report.add(3, "FAILURE_OBLIGATIONS_MISMATCH", contract=c.pk, sequence=e.sequence)
    if c.type == ContractType.LOAN.value:
        disb = Entry.objects.filter(transaction__key=f"{KEY_PREFIX}{c.pk}:disburse", nature=Nature.LOAN_PRINCIPAL.value)
        want = c.terms.get("principal_cents")
        if disb.count() != 1 or disb[0].amount != want:
            report.add(3, "DISBURSEMENT_MISMATCH", contract=c.pk)
    if penalties:
        p = penalties[0].data
        key = f"{KEY_PREFIX}{c.pk}:penalty"
        if c.penalty_cents <= 0 or p.get("amount_cents") != c.penalty_cents:
            report.add(3, "PENALTY_AMOUNT_MISMATCH", contract=c.pk)
        if p.get("paid"):
            rows = list(Entry.objects.filter(transaction__key=key, nature=Nature.PENALTY.value))
            if len(rows) != 1 or rows[0].amount != c.penalty_cents:
                report.add(3, "PENALTY_ENTRY_MISMATCH", contract=c.pk)
        elif Obligation.objects.filter(key=key, nature=Nature.PENALTY.value, amount_due=c.penalty_cents).count() != 1:
            report.add(3, "PENALTY_OBLIGATION_MISMATCH", contract=c.pk)
    elif Entry.objects.filter(transaction__key=f"{KEY_PREFIX}{c.pk}:penalty").exists() or Obligation.objects.filter(
            key=f"{KEY_PREFIX}{c.pk}:penalty").exists():
        report.add(3, "PENALTY_WITHOUT_EVENT", contract=c.pk)


def _audit_supply_success(report, c, e, key) -> None:
    from .handlers import account_of
    t = c.terms
    gross = t["quantity"] * t["unit_price_cents"]
    seller, buyer = account_of(c.party_a_kind, c.party_a_id), account_of(c.party_b_kind, c.party_b_id)
    if find_payment(key, buyer, seller, gross, include_reversed=True) is None:
        report.add(3, "SUPPLY_PAYMENT_MISMATCH", contract=c.pk, sequence=e.sequence)
    sale = MarketTransaction.objects.filter(ledger_key=key).first()
    if sale is None or (sale.channel, sale.quantity, sale.unit_price_cents, sale.product.key, sale.seller_id, sale.buyer_id) != (
            "contract", t["quantity"], t["unit_price_cents"], t["product"], c.party_a_id, c.party_b_id):
        report.add(3, "SUPPLY_SALE_NOT_RECORDED", contract=c.pk, sequence=e.sequence)
    out = StockMovement.objects.filter(key=f"{key}:out").first()
    inc = StockMovement.objects.filter(key=f"{key}:in").first()
    if (out is None or (out.company_id, out.delta, out.product.key) != (c.party_a_id, -t["quantity"], t["product"])
            or inc is None or (inc.company_id, inc.delta, inc.product.key) != (c.party_b_id, t["quantity"], t["product"])):
        report.add(3, "SUPPLY_STOCK_MISMATCH", contract=c.pk, sequence=e.sequence)


def _audit_loan_success(report, c, handler, e, key) -> None:
    p, i = handler.parts(c, e.sequence)
    got = {x.nature: x.amount for x in Entry.objects.filter(transaction__key=key)}
    want = {Nature.LOAN_REPAYMENT.value: p, Nature.LOAN_INTEREST.value: i}
    want = {k: v for k, v in want.items() if v}
    if got != want:
        report.add(3, "LOAN_INSTALLMENT_MISMATCH", contract=c.pk, sequence=e.sequence, got=got, want=want)


def _audit_orphans(report: AuditReport, seen: Dict[int, set]) -> None:
    for key in Transaction.objects.filter(key__startswith=KEY_PREFIX).values_list("key", flat=True):
        parts = key.split(":")
        if len(parts) >= 4 and parts[2] == "exec":
            cid, seq = int(parts[1]), int(parts[3])
            if seq not in seen.get(cid, set()):
                report.add(4, "ORPHAN_LEDGER_KEY", key=key)
    for key in StockMovement.objects.filter(key__startswith=KEY_PREFIX).values_list("key", flat=True):
        parts = key.split(":")
        if len(parts) >= 4 and parts[2] == "exec":
            cid, seq = int(parts[1]), int(parts[3])
            if seq not in seen.get(cid, set()):
                report.add(4, "ORPHAN_STOCK_KEY", key=key)
