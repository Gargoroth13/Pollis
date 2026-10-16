"""
Obrigações pendentes (design/24 §24.9): dívida vencida que o pagador não pôde pagar por falta de caixa.

NÃO é dinheiro: não entra em saldo nem em circulação; quitar é uma transferência comum entre contas que já existem.
Quitação determinística: competência mais antiga primeiro, depois id da obrigação (R4). Pagamento parcial é permitido.
O imposto retido (remuneração, R1) é recolhido em parcelas proporcionais ao bruto quitado; a última fecha o resto.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction

from core import clock as game_clock
from players.services import ActionResult

from .constants import REMUNERATION_NATURES, AccountKind, Nature, ObligationStatus
from .models import Account, Obligation, Transaction
from .money import amount_problem, competence_day_of, percent_of
from . import services as ledger


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def open_obligation(debtor_id: int, creditor_id: int, amount: int, nature: Nature, *, key: str, reference_kind: str,
                    reference_id, competence_day: Optional[int] = None, tax_rate: Decimal = Decimal(0),
                    tax_territory: str = "", at: Optional[int] = None) -> ActionResult:
    """Registra uma dívida (`amount` bruto) sem mover dinheiro. Idempotente por `key`; conteúdo diferente = conflito."""
    reference_id = str(reference_id)
    problem = amount_problem(amount)
    if problem:
        return _refuse(problem, amount=amount)
    if not key or not reference_kind or not reference_id:
        return _refuse("REFERENCE_REQUIRED")
    try:
        nature = Nature(nature)
    except ValueError:
        return _refuse("NATURE_INVALID", nature=str(nature))
    if debtor_id == creditor_id:
        return _refuse("SAME_ACCOUNT", account=debtor_id)
    if isinstance(tax_rate, float) or not Decimal(0) <= Decimal(tax_rate) <= Decimal(1):
        return _refuse("TAX_RATE_INVALID", rate=str(tax_rate))
    at = game_clock.now() if at is None else at
    day = competence_day_of(at) if competence_day is None else competence_day
    with transaction.atomic():
        accounts = {a.pk: a for a in Account.objects.select_for_update().filter(pk__in=[debtor_id, creditor_id]).order_by("pk")}
        for i in (debtor_id, creditor_id):
            if i not in accounts:
                return _refuse("ACCOUNT_NOT_FOUND", account=i)
            if accounts[i].closed:
                return _refuse("ACCOUNT_CLOSED", account=i)
        for i in (debtor_id, creditor_id):
            if AccountKind(accounts[i].kind) in (AccountKind.SINK, AccountKind.ISSUANCE):
                return _refuse("NATURE_ACCOUNT_MISMATCH", account=i)
        existing = Obligation.objects.filter(key=key).first()
        if existing is not None:
            same = (existing.debtor_id, existing.creditor_id, existing.amount_due, existing.nature, existing.competence_day,
                    existing.reference_kind, existing.reference_id) == (
                debtor_id, creditor_id, amount, nature.value, day, reference_kind, reference_id)
            return ActionResult(True, "OK", {"obligation_id": existing.pk, "already_posted": True}) if same \
                else _refuse("IDEMPOTENCY_CONFLICT", key=key)
        ob = Obligation.objects.create(
            key=key, debtor_id=debtor_id, creditor_id=creditor_id, amount_due=amount, nature=nature.value,
            competence_day=day, reference_kind=reference_kind, reference_id=reference_id, tax_rate=Decimal(tax_rate),
            tax_territory=tax_territory, created_at=at)
        return ActionResult(True, "OK", {"obligation_id": ob.pk, "already_posted": False, "amount": amount})


def remaining(ob: Obligation) -> int:
    return ob.amount_due - ob.amount_paid


def tax_cumulative(ob: Obligation, gross_paid_total: int) -> int:
    """Imposto acumulado devido quando `gross_paid_total` do bruto foi quitado (arredonda uma vez; o total fecha no fim)."""
    total = percent_of(ob.amount_due, ob.tax_rate)
    if gross_paid_total >= ob.amount_due:
        return total
    return min(total, percent_of(gross_paid_total, ob.tax_rate))


def _self_compensated(ob: Obligation, at: int) -> bool:
    """O imposto desta obrigação iria à própria conta devedora (governo federal pagando; imposto à União)?"""
    if ob.tax_rate == 0:
        return False
    route = ledger.route_tax(ledger.territory_from_str(ob.tax_territory), at)
    return route.ok and route.detail["account_id"] == ob.debtor_id


def _outflow(ob: Obligation, x: int, self_comp: bool) -> int:
    """Quanto SAI da conta devedora ao quitar `x` do bruto agora (imposto autocompensado não sai)."""
    if not self_comp:
        return x
    chunk = tax_cumulative(ob, ob.amount_paid + x) - ob.tax_paid
    return x - chunk


def _affordable(ob: Obligation, available: int, self_comp: bool) -> int:
    """Maior parcela do bruto (≤ restante) cuja saída cabe no disponível. `_outflow` é monótona em x."""
    limit = remaining(ob)
    if _outflow(ob, limit, self_comp) <= available:
        return limit
    lo, hi = 0, limit
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _outflow(ob, mid, self_comp) <= available:
            lo = mid
        else:
            hi = mid - 1
    return lo


def settle_obligations(debtor_id: int, *, batch_key: str, at: Optional[int] = None) -> ActionResult:
    """
    Paga o que o caixa DISPONÍVEL do devedor permite, em ordem (competência, id). Parcial permitido. Idempotente por
    `batch_key`: repetir a mesma chamada não paga de novo. Nunca cria dinheiro. `detail` traz o que foi pago por obrigação.
    """
    if not batch_key:
        return _refuse("KEY_REQUIRED")
    at = game_clock.now() if at is None else at
    paid_rows: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    with transaction.atomic():
        debtor = Account.objects.select_for_update().filter(pk=debtor_id).first()
        if debtor is None:
            return _refuse("ACCOUNT_NOT_FOUND", account=debtor_id)
        obligations = list(Obligation.objects.select_for_update()
                           .filter(debtor_id=debtor_id, status=ObligationStatus.OPEN.value)
                           .order_by("competence_day", "id"))
        for ob in obligations:
            tx_key = f"settle:{batch_key}:{ob.pk}"
            if Transaction.objects.filter(key=tx_key).exists():
                skipped.append({"obligation": ob.pk, "why": "already_settled_in_batch"})
                continue
            available = ledger.available_of(debtor_id)
            self_comp = _self_compensated(ob, at)
            x = _affordable(ob, available, self_comp)
            if x <= 0:
                skipped.append({"obligation": ob.pk, "why": "no_cash"})
                continue
            tax_chunk = tax_cumulative(ob, ob.amount_paid + x) - ob.tax_paid
            nature = Nature(ob.nature)
            res = ledger.post_taxed_payment(
                debtor_id, ob.creditor_id, x, nature=nature, tax_rate=ob.tax_rate if ob.tax_rate else Decimal(0),
                territory=ledger.territory_from_str(ob.tax_territory), tax_nature=Nature.TAX_INCOME,
                key=tx_key, reference_kind=ob.reference_kind, reference_id=ob.reference_id, at=at, actor="settlement",
                competence_day=ob.competence_day, operation="settle_obligation", tax_amount=tax_chunk,
                _internal=nature in REMUNERATION_NATURES)
            if not res.ok:
                skipped.append({"obligation": ob.pk, "why": res.code})
                continue
            ob.amount_paid += x
            ob.tax_paid += tax_chunk
            fields = ["amount_paid", "tax_paid"]
            if ob.amount_paid == ob.amount_due:
                ob.status = ObligationStatus.PAID.value
                fields.append("status")
            ob.save(update_fields=fields)
            paid_rows.append({"obligation": ob.pk, "gross": x, "tax": tax_chunk, "net": x - tax_chunk,
                              "remaining": remaining(ob), "competence_day": ob.competence_day})
    return ActionResult(True, "OK", {"paid": paid_rows, "skipped": skipped, "total_gross": sum(r["gross"] for r in paid_rows)})


def cancel_obligation(obligation_id: int, reason: str, *, at: Optional[int] = None) -> ActionResult:
    """Cancelamento por regra do sistema de origem; exige motivo e guarda o que restava (nada some sem registro)."""
    if not reason:
        return _refuse("REASON_REQUIRED")
    at = game_clock.now() if at is None else at
    with transaction.atomic():
        ob = Obligation.objects.select_for_update().filter(pk=obligation_id).first()
        if ob is None:
            return _refuse("OBLIGATION_NOT_FOUND", obligation=obligation_id)
        if ob.status != ObligationStatus.OPEN.value:
            return _refuse("OBLIGATION_NOT_OPEN", obligation=obligation_id, status=ob.status)
        left = remaining(ob)
        Obligation.objects.filter(pk=ob.pk).update(status=ObligationStatus.CANCELLED.value, cancel_reason=reason,
                                                    cancelled_at=at)
        return ActionResult(True, "OK", {"obligation_id": ob.pk, "cancelled_remaining": left})


def open_obligations(debtor_id: int) -> List[Obligation]:
    return list(Obligation.objects.filter(debtor_id=debtor_id, status=ObligationStatus.OPEN.value))


def pending_summary(debtor_id: int) -> Dict[str, Any]:
    """Para a P1.09 decidir sobre despesas discricionárias: total devido e lista pública (09 §33)."""
    rows = open_obligations(debtor_id)
    return {"total": sum(remaining(o) for o in rows),
            "obligations": [{"id": o.pk, "creditor": o.creditor_id, "remaining": remaining(o), "nature": o.nature,
                             "competence_day": o.competence_day, "reference": [o.reference_kind, o.reference_id]}
                            for o in rows]}
