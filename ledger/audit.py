"""
Auditoria e métricas do registro monetário (design/24 §24.17). O saldo guardado é CACHE: a verdade é o log de lançamentos (R9).

`audit_ledger()` reconstrói tudo a partir dos lançamentos e compara com o que está guardado; adulteração direta no banco
(saldo, lançamento, metadados da transação, contador, obrigação, valor fora do domínio de uma enumeração) aparece como
ACHADO estruturado. A auditoria nunca encerra por causa de um dado inválido: cada seção roda isolada e, se uma exceção
inesperada escapar, vira o achado `AUDIT_SECTION_FAILED` em vez de interromper as demais. Não escreve nada.

Invariantes 1–14: ver design/24 §24.17. 15: valores de enumeração dentro do domínio. 16: metadados da transação (chave,
instante, ator, hash, conteúdo canônico) conferem com os lançamentos. 17: consumo de reservas registrado = consumo das
reservas. 18: toda emissão (`SCENARIO_GRANT`) corresponde a uma dotação explícita do cenário (papel, tipo de conta, valor, chave).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from django.db.models import Count, Sum

from .constants import (GRANT_ROLE_KINDS, OPERATIONAL_KINDS, REMUNERATION_NATURES, SINK_NATURES, AccountKind, HoldStatus, Nature,
                        ObligationStatus, Policy, RequestStatus)
from .models import (Account, Entry, Hold, LedgerScenario, Obligation, RemunerationCounter, RemunerationRequest,
                     ScenarioGrantLine, Transaction)
from .services import payload_digest

_OPERATIONAL_VALUES = frozenset(k.value for k in OPERATIONAL_KINDS)
_CHUNK = 500


@dataclass
class AuditReport:
    findings: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.findings

    def add(self, invariant: int, code: str, **detail) -> None:
        self.findings.append({"invariant": invariant, "code": code, **detail})

    def enum(self, cls, value, model: str, field_name: str, pk) -> Optional[Any]:
        """Valor da enumeração, ou None (com achado `INVALID_ENUM_VALUE`) se o banco guarda algo fora do domínio."""
        try:
            return cls(value)
        except (ValueError, TypeError):
            self.add(15, "INVALID_ENUM_VALUE", model=model, field=field_name, pk=pk, value=repr(value)[:80])
            return None

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "findings": self.findings, "stats": self.stats}


def _as_int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


# --- seções ------------------------------------------------------------------------------------------------------------

def _accounts(rep: AuditReport, ctx: Dict[str, Any]) -> None:
    accounts: Dict[int, Account] = {a.pk: a for a in Account.objects.all()}
    kind_of: Dict[int, Optional[AccountKind]] = {pk: rep.enum(AccountKind, a.kind, "Account", "kind", pk)
                                                 for pk, a in accounts.items()}
    ctx.update(accounts=accounts, kind_of=kind_of)
    total = sum(a.balance for a in accounts.values())
    if total != 0:                                                                                   # 1
        rep.add(1, "BALANCES_DO_NOT_SUM_TO_ZERO", total=total)
    for pk, a in accounts.items():                                                                   # 2
        kind = kind_of[pk]
        if kind is None:
            continue
        if kind == AccountKind.ISSUANCE:
            if a.balance > 0:
                rep.add(2, "ISSUANCE_POSITIVE", account=pk, balance=a.balance)
        elif a.balance < 0:
            rep.add(2, "NEGATIVE_BALANCE", account=pk, kind=a.kind, balance=a.balance)


def _log(rep: AuditReport, ctx: Dict[str, Any]) -> None:
    """3, 5, 11, 12, 13: reconstrução do log, cadeia antes/depois, rotas e referências."""
    accounts, kind_of = ctx["accounts"], ctx["kind_of"]
    running: Dict[int, int] = defaultdict(int)
    reversals: List[Entry] = []
    entries_count = 0
    for e in Entry.objects.select_related("transaction").order_by("seq").iterator(chunk_size=2000):
        entries_count += 1
        nature = rep.enum(Nature, e.nature, "Entry", "nature", e.seq)
        if e.from_account_id not in accounts or e.to_account_id not in accounts:
            rep.add(3, "ENTRY_WITH_UNKNOWN_ACCOUNT", seq=e.seq)
            continue
        fk, tk = kind_of[e.from_account_id], kind_of[e.to_account_id]
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
        if tk == AccountKind.ISSUANCE:
            rep.add(2, "ISSUANCE_AS_DESTINATION", seq=e.seq)
        if fk == AccountKind.ISSUANCE and nature is not None and nature != Nature.SCENARIO_GRANT:
            rep.add(13, "ISSUANCE_WITH_WRONG_NATURE", seq=e.seq, nature=e.nature)
        if nature == Nature.SCENARIO_GRANT and fk != AccountKind.ISSUANCE:
            rep.add(13, "GRANT_WITHOUT_ISSUANCE_ORIGIN", seq=e.seq)
        if tk == AccountKind.SINK and nature is not None and nature not in SINK_NATURES:
            rep.add(13, "SINK_RECEIVES_WRONG_NATURE", seq=e.seq, nature=e.nature)
        if not e.reference_kind or not e.reference_id:
            rep.add(12, "ENTRY_WITHOUT_REFERENCE", seq=e.seq)
        if nature in REMUNERATION_NATURES and not (e.transaction.key or "").startswith(("remuneration:", "settle:")):
            rep.add(11, "REMUNERATION_OUTSIDE_PAYROLL", seq=e.seq, key=e.transaction.key)
        if e.reverses_id is not None:
            reversals.append(e)
    for pk, a in accounts.items():
        if a.balance != running[pk]:
            rep.add(3, "STORED_BALANCE_DIFFERS_FROM_LOG", account=pk, kind=a.kind, stored=a.balance, rebuilt=running[pk])
    targets = {e.reverses_id for e in reversals}
    originals = {o.pk: (o.from_account_id, o.to_account_id, o.amount)
                 for o in Entry.objects.filter(pk__in=targets).only("seq", "from_account", "to_account", "amount")}
    for e in reversals:
        if originals.get(e.reverses_id) != (e.to_account_id, e.from_account_id, e.amount):
            rep.add(12, "REVERSAL_DOES_NOT_MIRROR_ORIGINAL", seq=e.seq, reverses=e.reverses_id)
    ctx["entries"] = entries_count
    ctx["running"] = running


def _emission(rep: AuditReport, ctx: Dict[str, Any]) -> None:
    """4: emitido = brutos operacionais + retenções + sumidouro (reservas NÃO entram); e emitido = soma das dotações."""
    accounts, kind_of = ctx["accounts"], ctx["kind_of"]
    sums: Dict[Optional[AccountKind], int] = defaultdict(int)
    for pk, a in accounts.items():
        sums[kind_of[pk]] += a.balance
    emitted = -sums[AccountKind.ISSUANCE]
    operational = sum(a.balance for pk, a in accounts.items() if kind_of[pk] in OPERATIONAL_KINDS)
    retained, sunk = sums[AccountKind.RETENTION], sums[AccountKind.SINK]
    if sums[None] == 0 and emitted != operational + retained + sunk:
        rep.add(4, "EMITTED_NOT_EQUAL_TO_BALANCES", emitted=emitted, operational=operational, retained=retained, sink=sunk)
    granted = Entry.objects.filter(nature=Nature.SCENARIO_GRANT.value).aggregate(s=Sum("amount"))["s"] or 0
    if granted != emitted:
        rep.add(4, "EMITTED_NOT_EQUAL_TO_GRANTS", emitted=emitted, granted=granted)
    ctx.update(emitted=emitted, operational=operational, retained=retained, sunk=sunk)


def _transactions(rep: AuditReport, ctx: Dict[str, Any]) -> None:
    """7, 8, 16: cada transação confere (chave, hash, conteúdo canônico, instante, ator, referência, dia) com seus lançamentos."""
    ctx["uses"] = []
    dup = Transaction.objects.values("key").annotate(n=Count("pk")).filter(n__gt=1).count()
    if dup:
        rep.add(8, "DUPLICATE_IDEMPOTENCY_KEYS", count=dup)
    chunk: List[Transaction] = []

    def check(txs: Sequence[Transaction]) -> None:
        by_tx: Dict[int, List[Entry]] = defaultdict(list)
        for e in Entry.objects.filter(transaction_id__in=[t.pk for t in txs]).order_by("seq"):
            by_tx[e.transaction_id].append(e)
        for tx in txs:
            entries = by_tx.get(tx.pk, [])
            if not entries:
                rep.add(7, "TRANSACTION_WITHOUT_ENTRIES", transaction=tx.pk, key=tx.key)
                continue
            if not tx.key:
                rep.add(16, "TRANSACTION_KEY_EMPTY", transaction=tx.pk)
            first = entries[0]
            if any(e.at != tx.at for e in entries):
                rep.add(16, "TRANSACTION_AT_MISMATCH", transaction=tx.pk, key=tx.key, at=tx.at)
            if any(e.actor != tx.actor for e in entries):
                rep.add(16, "TRANSACTION_ACTOR_MISMATCH", transaction=tx.pk, key=tx.key, actor=tx.actor)
            if any((e.reference_kind, e.reference_id, e.competence_day) != (first.reference_kind, first.reference_id,
                                                                            first.competence_day) for e in entries):
                rep.add(16, "TRANSACTION_ENTRIES_INCONSISTENT", transaction=tx.pk, key=tx.key)
            payload = tx.payload
            request = payload.get("request") if isinstance(payload, dict) else None
            effective_day = payload.get("competence_day") if isinstance(payload, dict) else None
            if not isinstance(request, dict) or _as_int(effective_day) is None:
                rep.add(16, "TRANSACTION_PAYLOAD_INVALID", transaction=tx.pk, key=tx.key)
                continue
            try:
                digest = payload_digest(request)
            except (TypeError, ValueError):
                rep.add(16, "TRANSACTION_PAYLOAD_INVALID", transaction=tx.pk, key=tx.key)
                continue
            if digest != tx.payload_hash:
                rep.add(16, "TRANSACTION_HASH_MISMATCH", transaction=tx.pk, key=tx.key)
            legs = [[e.from_account_id, e.to_account_id, e.amount, e.nature, e.category, e.operation] for e in entries]
            if request.get("legs") != legs:
                rep.add(16, "TRANSACTION_PAYLOAD_MISMATCH", transaction=tx.pk, key=tx.key, part="legs")
            if request.get("reference") != [first.reference_kind, first.reference_id]:
                rep.add(16, "TRANSACTION_PAYLOAD_MISMATCH", transaction=tx.pk, key=tx.key, part="reference")
            # o dia EFETIVO do payload é sempre o dia gravado em TODOS os lançamentos (mesmo sem dia informado na requisição)
            if any(e.competence_day != effective_day for e in entries):
                rep.add(16, "TRANSACTION_DAY_MISMATCH", transaction=tx.pk, key=tx.key, payload_day=effective_day,
                        entry_days=sorted({e.competence_day for e in entries}))
            requested_day = request.get("competence_day")
            if requested_day is not None and requested_day != effective_day:
                rep.add(16, "TRANSACTION_PAYLOAD_MISMATCH", transaction=tx.pk, key=tx.key, part="requested_day")
            if request.get("reverses") != first.reverses_id or any(e.reverses_id is not None for e in entries[1:]):
                rep.add(16, "TRANSACTION_PAYLOAD_MISMATCH", transaction=tx.pk, key=tx.key, part="reverses")
            uses = request.get("uses")
            valid = isinstance(uses, list) and all(
                isinstance(u, list) and len(u) == 2 and _as_int(u[0]) is not None and _as_int(u[1]) is not None and u[1] > 0
                for u in uses)
            if not valid:
                rep.add(16, "TRANSACTION_USES_INVALID", transaction=tx.pk, key=tx.key)
                continue
            for hold_id, amount in uses:
                ctx["uses"].append({"transaction": tx.pk, "key": tx.key, "hold": hold_id, "amount": amount,
                                    "from_accounts": {e.from_account_id for e in entries}})

    for tx in Transaction.objects.order_by("pk").iterator(chunk_size=_CHUNK):
        chunk.append(tx)
        if len(chunk) >= _CHUNK:
            check(chunk)
            chunk = []
    if chunk:
        check(chunk)
    ctx["uses_complete"] = True


def _holds_and_obligations(rep: AuditReport, ctx: Dict[str, Any]) -> None:
    """9: reservas ativas ≤ saldo bruto; obrigação nunca paga acima do devido; estados coerentes."""
    accounts = ctx["accounts"]
    held: Dict[int, int] = defaultdict(int)
    holds: Dict[int, Hold] = {}
    for h in Hold.objects.all():
        holds[h.pk] = h
        status = rep.enum(HoldStatus, h.status, "Hold", "status", h.pk)
        if status == HoldStatus.ACTIVE:
            held[h.account_id] += h.amount
        if h.amount > h.original_amount or h.amount < 0:
            rep.add(9, "HOLD_AMOUNT_INVALID", hold=h.pk)
    if ctx.get("uses_complete"):
        # o que as transações dizem ter consumido de cada reserva = o que a reserva diz ter perdido (original − restante)
        consumed: Dict[int, int] = defaultdict(int)
        for u in ctx["uses"]:
            hold = holds.get(u["hold"])
            if hold is None:
                rep.add(9, "HOLD_USE_UNKNOWN_HOLD", transaction=u["transaction"], key=u["key"], hold=u["hold"])
                continue
            if hold.account_id not in u["from_accounts"]:
                rep.add(9, "HOLD_USE_ACCOUNT_MISMATCH", transaction=u["transaction"], key=u["key"], hold=hold.pk)
            consumed[hold.pk] += u["amount"]
        for pk, h in holds.items():
            if consumed.get(pk, 0) != h.original_amount - h.amount:
                rep.add(9, "HOLD_CONSUMPTION_MISMATCH", hold=pk, in_transactions=consumed.get(pk, 0),
                        in_hold=h.original_amount - h.amount)
    for pk, amount in held.items():
        account = accounts.get(pk)
        if account is None or amount > account.balance:
            rep.add(9, "HOLDS_EXCEED_BALANCE", account=pk, held=amount, balance=account.balance if account else None)
    for ob in Obligation.objects.all():
        status = rep.enum(ObligationStatus, ob.status, "Obligation", "status", ob.pk)
        rep.enum(Nature, ob.nature, "Obligation", "nature", ob.pk)
        if ob.amount_paid > ob.amount_due:
            rep.add(9, "OBLIGATION_OVERPAID", obligation=ob.pk)
        if status == ObligationStatus.PAID and ob.amount_paid != ob.amount_due:
            rep.add(9, "OBLIGATION_PAID_STATUS_INCONSISTENT", obligation=ob.pk)
        if status == ObligationStatus.OPEN and ob.amount_paid == ob.amount_due:
            rep.add(9, "OBLIGATION_OPEN_BUT_SETTLED", obligation=ob.pk)
    for pk, a in accounts.items():
        if a.closed and (a.balance != 0 or held.get(pk)):
            rep.add(3, "CLOSED_ACCOUNT_NOT_EMPTY", account=pk)


def _remuneration(rep: AuditReport, ctx: Dict[str, Any]) -> None:
    """10: `C_S`/`C_T`/`C_P`/`P_liberada` = soma do reconhecido por (jogador, competência)."""
    paid_keys = set(Transaction.objects.filter(key__startswith="remuneration:").values_list("key", flat=True))
    expected: Dict[tuple, Dict[str, int]] = defaultdict(lambda: {"c_s": 0, "c_t": 0, "c_p": 0, "p_released": 0})
    for r in RemunerationRequest.objects.all():
        nature = rep.enum(Nature, r.nature, "RemunerationRequest", "nature", r.pk)
        status = rep.enum(RequestStatus, r.status, "RemunerationRequest", "status", r.pk)
        rep.enum(Policy, r.policy, "RemunerationRequest", "policy", r.pk)
        if nature is not None and nature not in REMUNERATION_NATURES:
            rep.add(11, "REQUEST_NATURE_NOT_REMUNERATION", request=r.key, nature=r.nature)
        if status == RequestStatus.SUBMITTED and (r.recognized or r.paid or r.pending):
            rep.add(10, "REQUEST_STATE_INCONSISTENT", request=r.key)
        if status != RequestStatus.RECOGNIZED or nature is None:
            continue
        row = expected[(r.player_id, r.competence_day)]
        row["c_t"] += r.recognized
        if nature == Nature.POLITICAL_SALARY:
            row["c_p"] += r.recognized
            released = r.explained.get("released", 0) if isinstance(r.explained, dict) else None
            if _as_int(released) is None:
                rep.add(10, "REQUEST_EXPLAINED_INVALID", request=r.key)
            else:
                row["p_released"] += released
        else:
            row["c_s"] += r.recognized
        if r.recognized != r.paid + r.pending:
            rep.add(10, "REQUEST_RECOGNIZED_NOT_PAID_PLUS_PENDING", request=r.key)
        if r.paid and f"remuneration:{r.key}" not in paid_keys and r.tax != r.recognized:
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


def _grants(rep: AuditReport, ctx: Dict[str, Any]) -> None:
    """
    18: cada dotação (`SCENARIO_GRANT`) corresponde a uma linha explícita do cenário: cenário existente, papel conhecido e
    compatível com o tipo da conta de destino, valor IGUAL ao da linha, chave `grant:<cenário>:<conta>`, uma só por
    (cenário, conta) e transação de uma única perna. Dado que falta ou está malformado é achado, não exceção. O estado ATIVO do
    cenário não é reconferido aqui: ele pode mudar depois da emissão; quem o exige é o serviço, na hora de emitir.
    """
    kind_of = ctx["kind_of"]
    scenarios = {sc.name: sc.pk for sc in LedgerScenario.objects.all()}
    lines = {(l.scenario_id, l.role): l.amount for l in ScenarioGrantLine.objects.all()}
    grants = Entry.objects.filter(nature=Nature.SCENARIO_GRANT.value)
    multi = set(Entry.objects.filter(transaction_id__in=grants.values("transaction_id")).values("transaction_id")
                .annotate(n=Count("pk")).filter(n__gt=1).values_list("transaction_id", flat=True))
    seen: Dict[Any, int] = {}
    for e in grants.select_related("transaction").order_by("seq").iterator(chunk_size=2000):
        where = {"seq": e.seq, "scenario": e.reference_id, "account": e.to_account_id}
        explained = e.explained if isinstance(e.explained, dict) else {}
        if e.reference_kind != "scenario" or e.reference_id not in scenarios:
            rep.add(18, "GRANT_SCENARIO_UNKNOWN", reference_kind=e.reference_kind, **where)
            continue
        scenario_pk = scenarios[e.reference_id]
        if explained.get("scenario") != e.reference_id:
            rep.add(18, "GRANT_EXPLAINED_MISMATCH", recorded=repr(explained.get("scenario"))[:80], **where)
        if e.transaction.key != f"grant:{e.reference_id}:{e.to_account_id}":
            rep.add(18, "GRANT_KEY_MISMATCH", key=e.transaction.key, **where)
        if e.transaction_id in multi:
            rep.add(18, "GRANT_TRANSACTION_NOT_SINGLE", transaction=e.transaction_id, **where)
        if (scenario_pk, e.to_account_id) in seen:
            rep.add(18, "GRANT_DUPLICATE", first_seq=seen[(scenario_pk, e.to_account_id)], **where)
        seen.setdefault((scenario_pk, e.to_account_id), e.seq)
        role = explained.get("role")
        allowed = GRANT_ROLE_KINDS.get(role) if isinstance(role, str) else None
        if allowed is None:
            rep.add(18, "GRANT_ROLE_INVALID", role=repr(role)[:80], **where)
            continue
        dest_kind = kind_of.get(e.to_account_id)
        if dest_kind not in allowed:
            rep.add(18, "GRANT_ROLE_ACCOUNT_MISMATCH", role=role, account_kind=getattr(dest_kind, "value", None), **where)
        configured = lines.get((scenario_pk, role))
        if configured is None:
            rep.add(18, "GRANT_LINE_MISSING", role=role, **where)
        elif configured != e.amount:
            rep.add(18, "GRANT_AMOUNT_MISMATCH", role=role, configured=configured, amount=e.amount, **where)


_SECTIONS: Sequence[tuple] = (
    ("accounts", _accounts), ("log", _log), ("emission", _emission), ("grants", _grants), ("transactions", _transactions),
    ("holds_and_obligations", _holds_and_obligations), ("remuneration", _remuneration),
)


def audit_ledger() -> AuditReport:
    rep = AuditReport()
    ctx: Dict[str, Any] = {}
    for name, section in _SECTIONS:
        try:
            section(rep, ctx)
        except Exception as exc:        # nunca encerra por dado inesperado: o problema vira achado e as outras seções rodam
            rep.add(0, "AUDIT_SECTION_FAILED", section=name, error=f"{type(exc).__name__}: {exc}"[:200])
            if name == "accounts":      # sem o mapa de contas as demais seções não têm base
                break
    rep.stats = {"accounts": len(ctx.get("accounts", {})), "entries": ctx.get("entries"), "emitted": ctx.get("emitted"),
                 "operational": ctx.get("operational"), "retained": ctx.get("retained"), "sink": ctx.get("sunk"),
                 "grants": Entry.objects.filter(nature=Nature.SCENARIO_GRANT.value).count()}
    return rep


def ledger_metrics() -> Dict[str, Any]:
    """Números para o Dashboard (design/24 §24.17; CLAUDE.md §8–9). Só leitura; tolera tipos desconhecidos no banco."""
    accounts = list(Account.objects.all())
    by_kind: Dict[str, Dict[str, int]] = defaultdict(lambda: {"accounts": 0, "balance": 0})
    for a in accounts:
        by_kind[a.kind]["accounts"] += 1
        by_kind[a.kind]["balance"] += a.balance
    emitted = -sum(a.balance for a in accounts if a.kind == AccountKind.ISSUANCE.value)
    circulation = sum(a.balance for a in accounts if a.kind in _OPERATIONAL_VALUES)
    retained = sum(a.balance for a in accounts if a.kind == AccountKind.RETENTION.value)
    sink = sum(a.balance for a in accounts if a.kind == AccountKind.SINK.value)
    grants = Entry.objects.filter(nature=Nature.SCENARIO_GRANT.value)
    grant_by_scenario = {row["reference_id"]: row["s"] for row in grants.values("reference_id").annotate(s=Sum("amount"))}
    by_nature = {row["nature"]: {"count": row["n"], "amount": row["s"]} for row in
                 Entry.objects.values("nature").annotate(n=Count("pk"), s=Sum("amount"))}
    reserved = Hold.objects.filter(status=HoldStatus.ACTIVE.value).aggregate(s=Sum("amount"))["s"] or 0
    pending_rows = Obligation.objects.filter(status=ObligationStatus.OPEN.value).values_list("amount_due", "amount_paid")
    counters = RemunerationCounter.objects.aggregate(rows=Count("pk"), c_s=Sum("c_s"), c_t=Sum("c_t"), c_p=Sum("c_p"))
    return {
        "emitted_total": emitted, "emitted_by_scenario": grant_by_scenario,
        "accounts_granted": grants.values("to_account").distinct().count(),
        "in_circulation": circulation, "retained": retained, "sink_destroyed": sink, "reserved": reserved,
        "pending_obligations": sum(d - p for d, p in pending_rows), "pending_obligations_count": len(pending_rows),
        "by_account_kind": dict(by_kind), "by_nature": by_nature, "entries": Entry.objects.count(),
        "counters": {k: (v or 0) for k, v in counters.items()},
        "remuneration_requests": {row["status"]: row["n"] for row in
                                  RemunerationRequest.objects.values("status").annotate(n=Count("pk"))},
    }
