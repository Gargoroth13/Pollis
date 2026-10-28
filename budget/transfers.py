"""
Repasses entre níveis de governo (09 §3-§4, §27, §30, §40): União → Estados (Presidente) e Estado → Municípios (Governador).

É dinheiro EXISTENTE que muda de caixa (`GOV_TRANSFER`, 24 §24.13): nada é criado. Não há fórmula de equalização (§28, §30): o valor é decisão política,
registrada e pública (`GovernmentDecision`). Para a União e os Estados, o repasse não é "despesa" para o teto de déficit (24 §24.16); para o destinatário,
é receita.

REGRA DA P1.09 (lacuna K3, `design/09a`): o governo só repassa o que sobra DEPOIS do orçamento comprometido (reservas, 09 §10) e das obrigações pendentes
já assumidas (09 §11 manda priorizá-las; 24 §24.9 deixa a decisão à P1.09). `params.TRANSFERS_RESPECT_PENDING_OBLIGATIONS` `[PROV]`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.db import transaction

from core import clock as game_clock
from ledger import services as ledger
from ledger.constants import Nature
from ledger.models import Account
from ledger.money import competence_day_of
from players.services import ActionResult

from . import params
from .authority import authority_refusal
from .constants import DecisionKind, Level
from .govs import account_of, is_int, parse_gov, ref, refuse, state_of_city
from .models import GovernmentDecision

KEYS = frozenset({"from", "to", "amount"})
OPTIONAL = frozenset({"reason"})
ALLOWED = {(Level.UNION, Level.STATE), (Level.STATE, Level.MUNICIPALITY)}      # 09 §2: Federal → Estados → Municípios, sem pular nível nem voltar
MAX_REASON = 200


class _Refused(Exception):
    def __init__(self, result: ActionResult):
        self.result = result


def _parse(target: Any):
    if not isinstance(target, dict) or not KEYS <= set(target) or not set(target) <= KEYS | OPTIONAL:
        return refuse("INVALID_PARAMS", expected=sorted(KEYS), optional=sorted(OPTIONAL))
    src, dst = parse_gov(target["from"]), parse_gov(target["to"])
    for p in (src, dst):
        if isinstance(p, ActionResult):
            return p
    amount, reason = target["amount"], target.get("reason", "")
    if not is_int(amount) or amount <= 0:
        return refuse("INVALID_AMOUNT", amount=repr(amount)[:30])
    if not isinstance(reason, str) or len(reason) > MAX_REASON:
        return refuse("INVALID_REASON", max_length=MAX_REASON)
    return src, dst, amount, reason


def funds_quote(source: Account, amount: int) -> Dict[str, Any]:
    """Quanto o governo PODE repassar: saldo − comprometido − obrigações pendentes já assumidas (K3). Estrutura para a UI (20)."""
    quote = ledger.quote(source.pk, amount).detail
    pending = ledger.pending_total(source.pk) if params.TRANSFERS_RESPECT_PENDING_OBLIGATIONS else 0
    spendable = quote["available"] - pending
    return {"requested": amount, "gross": quote["gross"], "committed": quote["reserved"], "available_after_commitments": quote["available"],
            "pending_obligations": pending, "spendable": spendable, "shortfall": max(0, amount - spendable), "ok": spendable >= amount,
            "explained": quote["explained"]}


def transfer_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    """Recusas que só LEEM. PLAYER_NOT_FOUND, INVALID_*, GOVERNMENT_NOT_FOUND, TRANSFER_NOT_ALLOWED, MUNICIPALITY_NOT_IN_STATE, OFFICE_*, INSUFFICIENT_FUNDS."""
    parsed = _parse(target)
    if isinstance(parsed, ActionResult):
        return parsed
    (src_level, src_id), (dst_level, dst_id), amount, _ = parsed
    if not is_int(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    if (src_level, dst_level) not in ALLOWED:
        return refuse("TRANSFER_NOT_ALLOWED", from_level=src_level.value, to_level=dst_level.value,
                      allowed=[[a.value, b.value] for a, b in sorted(ALLOWED, key=lambda x: x[0].value)])
    if src_level is Level.STATE and state_of_city(dst_id) != src_id:
        return refuse("MUNICIPALITY_NOT_IN_STATE", state=src_id, municipality=dst_id)
    refusal = authority_refusal(actor_id, src_level, src_id)
    if refusal is not None:
        return refusal
    funds = funds_quote(account_of(src_level, src_id), amount)
    if not funds["ok"]:
        return refuse("INSUFFICIENT_FUNDS", **funds)
    return None


def transfer_budget(actor_id: Any, target: Any) -> ActionResult:
    """O Presidente repassa a um Estado, o Governador a um Município do seu Estado. Decisão registrada, pública e sem criar dinheiro."""
    parsed = _parse(target)
    if isinstance(parsed, ActionResult):
        return parsed
    (src_level, src_id), (dst_level, dst_id), amount, reason = parsed
    try:
        with transaction.atomic():
            source, dest = account_of(src_level, src_id), account_of(dst_level, dst_id)
            list(Account.objects.select_for_update().filter(pk__in=[source.pk, dest.pk]).order_by("pk"))      # ordem crescente, como o registro
            refusal = transfer_refusal(actor_id, target)
            if refusal is not None:
                raise _Refused(refusal)
            now = game_clock.now()
            funds = funds_quote(source, amount)
            decision = GovernmentDecision.objects.create(
                kind=DecisionKind.TRANSFER.value, level=src_level.value, territory_id=src_id, actor_id=actor_id, at=now,
                competence_day=competence_day_of(now),
                data={"from": ref(src_level, src_id), "to": ref(dst_level, dst_id), "amount": amount, "reason": reason, "funds": funds})
            key = f"budget:transfer:{decision.pk}"
            paid = ledger.transfer(source.pk, dest.pk, amount, Nature.GOV_TRANSFER, key=key, reference_kind="budget_decision",
                                   reference_id=str(decision.pk), at=now, actor=f"player:{actor_id}", category="transfer", operation="repasse")
            if not paid.ok:
                raise _Refused(paid)
            GovernmentDecision.objects.filter(pk=decision.pk).update(ledger_key=key)
    except _Refused as refused:
        return refused.result
    return ActionResult(True, "OK", {"decision": decision.pk, "from": ref(src_level, src_id), "to": ref(dst_level, dst_id), "amount": amount,
                                     "ledger_key": key, "funds": funds})
