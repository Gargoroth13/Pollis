"""
Auditoria e métricas do registro monetário (design/24 §24.17). O saldo guardado é CACHE: a verdade é o log de lançamentos (R9).

`audit_ledger()` reconstrói tudo a partir dos lançamentos e compara com o que está guardado; adulteração direta no banco
(saldo, lançamento, contador, obrigação) aparece como achado. Não escreve nada.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List

from django.db.models import Count, Sum

from .constants import (OPERATIONAL_KINDS, REMUNERATION_NATURES, SINK_NATURES, AccountKind, HoldStatus, Nature,
                        ObligationStatus, RequestStatus)
from .models import (Account, Entry, Hold, Obligation, RemunerationCounter, RemunerationRequest, Transaction)


@dataclass
class AuditReport:
    findings: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.findings

    def add(self, invariant: int, code: str, **detail) -> None:
        self.findings.append({"invariant": invariant, "code": code, **detail})

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "findings": self.findings, "stats": self.stats}


def audit_ledger() -> AuditReport:
    rep = AuditReport()
    accounts = {a.pk: a for a in Account.objects.all()}
    kind_of = {pk: AccountKind(a.kind) for pk, a in accounts.items()}

    # 1. soma de todos os saldos guardados = 0
    total = sum(a.balance for a in accounts.values())
    if total != 0:
        rep.add(1, "BALANCES_DO_NOT_SUM_TO_ZERO", total=total)

    # 2. sinais por tipo
    for pk, a in accounts.items():
        if kind_of[pk] == AccountKind.ISSUANCE:
            if a.balance > 0:
                rep.add(2, "ISSUANCE_POSITIVE", account=pk, balance=a.balance)
        elif a.balance < 0:
            rep.add(2, "NEGATIVE_BALANCE", account=pk, kind=a.kind, balance=a.balance)

    # 3, 5, 12, 13: reconstrução do log, cadeia antes/depois, rotas e referências
    running: Dict[int, int] = defaultdict(int)
    grants = 0
    entries_count = 0
    by_seq: Dict[int, Entry] = {}
    for e in Entry.objects.order_by("seq").iterator(chunk_size=2000):
        entries_count += 1
        nature = Nature(e.nature)
        fk, tk = kind_of.get(e.from_account_id), kind_of.get(e.to_account_id)
        if fk is None or tk is None:
            rep.add(3, "ENTRY_WITH_UNKNOWN_ACCOUNT", seq=e.seq)
            continue
        if e.amount <= 0:
            rep.add(12, "ENTRY_AMOUNT_NOT_POSITIVE", seq=e.seq, amount=e.amount)
        if e.from_balance_before != running[e.from_account_id] or e.from_balance_after != e.from_balance_before - e.amount:
            rep.add(3, "ENTRY_FROM_CHAIN_BROKEN", seq=e.seq, account=e.from_account_id,
                    expected_before=running[e.from_account_id], recorded_before=e.from_balance_before)
        running[e.from_account_id] -= e.amount
        if e.to_balance_before != running[e.to_account_id] or e.to_balance_after != e.to_balance_before + e.amount:
            rep.add(3, "ENTRY_TO_CHAIN_BROKEN", seq=e.seq, account=e.to_account_id,
                    expected_before=running[e.to_account_id], recorded_before=e.to_balance_before)
        running[e.to_account_id] += e.amount
        if fk == AccountKind.SINK:
            rep.add(5, "SINK_AS_ORIGIN", seq=e.seq)
        if fk == AccountKind.ISSUANCE:
            grants += 1
            if nature != Nature.SCENARIO_GRANT:
                rep.add(13, "ISSUANCE_WITH_WRONG_NATURE", seq=e.seq, nature=e.nature)
        if tk == AccountKind.ISSUANCE:
            rep.add(2, "ISSUANCE_AS_DESTINATION", seq=e.seq)
        if nature == Nature.SCENARIO_GRANT and fk != AccountKind.ISSUANCE:
            rep.add(13, "GRANT_WITHOUT_ISSUANCE_ORIGIN", seq=e.seq)
        if tk == AccountKind.SINK and nature not in SINK_NATURES:
            rep.add(13, "SINK_RECEIVES_WRONG_NATURE", seq=e.seq, nature=e.nature)
        if not e.reference_kind or not e.reference_id:
            rep.add(12, "ENTRY_WITHOUT_REFERENCE", seq=e.seq)
        if nature in REMUNERATION_NATURES and not e.transaction.key.startswith(("remuneration:", "settle:")):
            rep.add(11, "REMUNERATION_OUTSIDE_PAYROLL", seq=e.seq, key=e.transaction.key)
        if e.reverses_id is not None:
            original = by_seq.get(e.reverses_id) or Entry.objects.filter(pk=e.reverses_id).first()
            if original is None or (original.from_account_id, original.to_account_id, original.amount) != (
                    e.to_account_id, e.from_account_id, e.amount):
                rep.add(12, "REVERSAL_DOES_NOT_MIRROR_ORIGINAL", seq=e.seq, reverses=e.reverses_id)
        by_seq[e.seq] = e if len(by_seq) < 5000 else by_seq.get(e.seq)  # só a vizinhança recente basta; o resto vai ao banco
        if len(by_seq) > 5000:
            by_seq.clear()
    for pk, a in accounts.items():
        if a.balance != running[pk]:
            rep.add(3, "STORED_BALANCE_DIFFERS_FROM_LOG", account=pk, kind=a.kind, stored=a.balance, rebuilt=running[pk])

    # 4. emitido = brutos operacionais + retenções + sumidouro (reservas NÃO entram)
    issuance_balance = sum(a.balance for pk, a in accounts.items() if kind_of[pk] == AccountKind.ISSUANCE)
    emitted = -issuance_balance
    operational = sum(a.balance for pk, a in accounts.items() if kind_of[pk] in OPERATIONAL_KINDS)
    retained = sum(a.balance for pk, a in accounts.items() if kind_of[pk] == AccountKind.RETENTION)
    sunk = sum(a.balance for pk, a in accounts.items() if kind_of[pk] == AccountKind.SINK)
    if emitted != operational + retained + sunk:
        rep.add(4, "EMITTED_NOT_EQUAL_TO_BALANCES", emitted=emitted, operational=operational, retained=retained, sink=sunk)
    granted = Entry.objects.filter(nature=Nature.SCENARIO_GRANT.value).aggregate(s=Sum("amount"))["s"] or 0
    if granted != emitted:
        rep.add(4, "EMITTED_NOT_EQUAL_TO_GRANTS", emitted=emitted, granted=granted)

    # 7, 8. transações sem lançamentos; chaves repetidas
    empty = Transaction.objects.annotate(n=Count("entries")).filter(n=0).count()
    if empty:
        rep.add(7, "TRANSACTION_WITHOUT_ENTRIES", count=empty)
    dup = (Transaction.objects.values("key").annotate(n=Count("pk")).filter(n__gt=1).count())
    if dup:
        rep.add(8, "DUPLICATE_IDEMPOTENCY_KEYS", count=dup)

    # 9. reservas e obrigações
    held: Dict[int, int] = defaultdict(int)
    for h in Hold.objects.filter(status=HoldStatus.ACTIVE.value):
        held[h.account_id] += h.amount
    for pk, amount in held.items():
        if amount > accounts[pk].balance:
            rep.add(9, "HOLDS_EXCEED_BALANCE", account=pk, held=amount, balance=accounts[pk].balance)
    for ob in Obligation.objects.all():
        if ob.amount_paid > ob.amount_due:
            rep.add(9, "OBLIGATION_OVERPAID", obligation=ob.pk)
        if ob.status == ObligationStatus.PAID.value and ob.amount_paid != ob.amount_due:
            rep.add(9, "OBLIGATION_PAID_STATUS_INCONSISTENT", obligation=ob.pk)
        if ob.status == ObligationStatus.OPEN.value and ob.amount_paid == ob.amount_due:
            rep.add(9, "OBLIGATION_OPEN_BUT_SETTLED", obligation=ob.pk)

    # 10. contadores = soma do reconhecido por (jogador, competência)
    expected: Dict[tuple, Dict[str, int]] = defaultdict(lambda: {"c_s": 0, "c_t": 0, "c_p": 0, "p_released": 0})
    for r in RemunerationRequest.objects.filter(status=RequestStatus.RECOGNIZED.value):
        row = expected[(r.player_id, r.competence_day)]
        row["c_t"] += r.recognized
        if r.nature == Nature.POLITICAL_SALARY.value:
            row["c_p"] += r.recognized
            row["p_released"] += int(r.explained.get("released", 0))
        else:
            row["c_s"] += r.recognized
        if r.recognized != r.paid + r.pending:
            rep.add(10, "REQUEST_RECOGNIZED_NOT_PAID_PLUS_PENDING", request=r.key)
        if r.paid and not Transaction.objects.filter(key=f"remuneration:{r.key}").exists() and r.tax != r.recognized:
            rep.add(10, "REQUEST_PAID_WITHOUT_TRANSACTION", request=r.key)
    stored = {(c.player_id, c.competence_day): c for c in RemunerationCounter.objects.all()}
    for key_, want in expected.items():
        c = stored.get(key_)
        have = {"c_s": c.c_s, "c_t": c.c_t, "c_p": c.c_p, "p_released": c.p_released} if c else dict.fromkeys(want, 0)
        if have != want:
            rep.add(10, "COUNTER_DIFFERS_FROM_REQUESTS", player=key_[0], day=key_[1], stored=have, expected=want)
    for key_, c in stored.items():
        if key_ not in expected and (c.c_s or c.c_t or c.c_p or c.p_released):
            rep.add(10, "COUNTER_WITHOUT_RECOGNIZED_REQUESTS", player=key_[0], day=key_[1])

    # contas encerradas vazias
    for pk, a in accounts.items():
        if a.closed and (a.balance != 0 or held.get(pk)):
            rep.add(3, "CLOSED_ACCOUNT_NOT_EMPTY", account=pk)

    rep.stats = {"accounts": len(accounts), "entries": entries_count, "grants": grants, "emitted": emitted,
                 "operational": operational, "retained": retained, "sink": sunk}
    return rep


def ledger_metrics() -> Dict[str, Any]:
    """Números para o Dashboard (design/24 §24.17; CLAUDE.md §8–9). Só leitura."""
    accounts = list(Account.objects.all())
    by_kind: Dict[str, Dict[str, int]] = defaultdict(lambda: {"accounts": 0, "balance": 0})
    for a in accounts:
        by_kind[a.kind]["accounts"] += 1
        by_kind[a.kind]["balance"] += a.balance
    emitted = -sum(a.balance for a in accounts if a.kind == AccountKind.ISSUANCE.value)
    circulation = sum(a.balance for a in accounts if AccountKind(a.kind) in OPERATIONAL_KINDS)
    retained = sum(a.balance for a in accounts if a.kind == AccountKind.RETENTION.value)
    sink = sum(a.balance for a in accounts if a.kind == AccountKind.SINK.value)
    grants = Entry.objects.filter(nature=Nature.SCENARIO_GRANT.value)
    grant_by_scenario = {row["reference_id"]: row["s"] for row in
                         grants.values("reference_id").annotate(s=Sum("amount"))}
    by_nature = {row["nature"]: {"count": row["n"], "amount": row["s"]} for row in
                 Entry.objects.values("nature").annotate(n=Count("pk"), s=Sum("amount"))}
    reserved = Hold.objects.filter(status=HoldStatus.ACTIVE.value).aggregate(s=Sum("amount"))["s"] or 0
    pending_rows = Obligation.objects.filter(status=ObligationStatus.OPEN.value).values_list("amount_due", "amount_paid")
    counters = RemunerationCounter.objects.aggregate(rows=Count("pk"), c_s=Sum("c_s"), c_t=Sum("c_t"), c_p=Sum("c_p"))
    return {
        "emitted_total": emitted, "emitted_by_scenario": grant_by_scenario, "accounts_granted": grants.values("to_account").distinct().count(),
        "in_circulation": circulation, "retained": retained, "sink_destroyed": sink, "reserved": reserved,
        "pending_obligations": sum(d - p for d, p in pending_rows), "pending_obligations_count": len(pending_rows),
        "by_account_kind": dict(by_kind), "by_nature": by_nature, "entries": Entry.objects.count(),
        "counters": {k: (v or 0) for k, v in counters.items()},
        "remuneration_requests": {row["status"]: row["n"] for row in
                                  RemunerationRequest.objects.values("status").annotate(n=Count("pk"))},
    }
