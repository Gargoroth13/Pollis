"""
Remuneração com contadores `C_S`, `C_T` e `C_P` (design/24 §24.12, que implementa 11 §11.1.0 sem alterar a regra).

Serviços NÃO pagam remuneração: eles SUBMETEM pedidos (`submit_remuneration`) e uma LIQUIDAÇÃO (`liquidate_remuneration`)
os processa como um conjunto, na ordem estável da chave do próprio pedido, nunca na ordem de chegada. Remuneração de trabalho
(nasce de uma ação) usa `pay_remuneration_now` = submeter + liquidar um pedido.

Limites vêm de um PROVEDOR (`register_limits_provider`, ligado a `skills`/leis pelo sistema dono): sem provedor a liquidação
recusa (`REMUNERATION_LIMITS_UNSPECIFIED`); o registro não inventa salário mínimo nem teto.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from django.db import IntegrityError, transaction

from core import clock as game_clock
from core.breakdown import Calc
from players.services import ActionResult

from .constants import (COUNTS_IN_C_S, REMUNERATION_NATURES, Nature, Policy, RequestStatus)
from .models import Account, Obligation, RemunerationCounter, RemunerationRequest
from .money import (amount_problem, canonical_rate, competence_day_of, percent_of, tax_rate_problem,
                    tax_territory_problem)
from . import obligations as obligations_mod
from . import services as ledger

# (jogador, natureza, instante) -> (W, S, T) em centavos; T None = sem teto legal
LimitsProvider = Callable[[int, Nature, int], Tuple[int, int, Optional[int]]]
# (jogador, dia de competência) -> salário político devido no dia, em centavos
PoliticalDueProvider = Callable[[int, int], int]

_limits_provider: Optional[LimitsProvider] = None
_political_provider: Optional[PoliticalDueProvider] = None


def register_limits_provider(fn: LimitsProvider) -> None:
    global _limits_provider
    if _limits_provider is not None and _limits_provider is not fn:
        raise ValueError("Provedor de limites de remuneração já registrado")
    _limits_provider = fn


def register_political_due_provider(fn: PoliticalDueProvider) -> None:
    global _political_provider
    if _political_provider is not None and _political_provider is not fn:
        raise ValueError("Provedor de salário político já registrado")
    _political_provider = fn


def clear_providers() -> None:  # para testes
    global _limits_provider, _political_provider
    _limits_provider = None
    _political_provider = None


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


# --- cálculo puro -------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RemunerationInputs:
    nature: Nature
    due: int
    W: int
    S: int
    T: Optional[int]          # None = sem teto legal
    c_s: int
    c_t: int
    c_p: int
    p_released: int
    p_due: int                # P_dia: salário político devido no dia (provedor)

    @property
    def political(self) -> bool:
        return self.nature == Nature.POLITICAL_SALARY

    @property
    def p_reserved(self) -> int:
        """`P_reservada = max(0, P_dia − C_P − liberado)`: derivada, nunca guardada (§24.12.2)."""
        return max(0, self.p_due - self.c_p - self.p_released)


def compute_recognition(i: RemunerationInputs, at: Optional[int] = None) -> Dict[str, Any]:
    """
    Fórmula do §24.12.3 com `Explained`. Devolve `recognized`, `discarded`, `released` (reserva política liberada), os fatores
    e qual limite restringiu. Função pura: a liquidação e a prévia usam exatamente esta.
    """
    cap_s = max(i.W, i.S)
    p_res = i.p_reserved
    factors: Dict[str, Any] = {"due": i.due, "W": i.W, "S": i.S, "T": i.T, "cap_S": cap_s, "C_S": i.c_s, "C_T": i.c_t,
                               "C_P": i.c_p, "P_dia": i.p_due, "P_reservada": p_res, "P_liberada": i.p_released}
    calc = Calc("due", i.due)
    if i.political:
        if i.T is not None:
            factors["room_T"] = i.T - i.c_t
            calc.cap("room_T", i.T - i.c_t)
    else:
        factors["sobra_S"] = cap_s - i.c_s
        calc.cap("sobra_S", cap_s - i.c_s)
        if i.T is not None:
            factors["sobra_T"] = i.T - i.c_t - p_res
            calc.cap("sobra_T", i.T - i.c_t - p_res)
    calc.floor("no_negative", 0)
    explained = calc.result(at)
    recognized = int(explained.value)
    released = max(0, min(i.due, p_res) - recognized) if i.political else 0
    return {"recognized": recognized, "discarded": i.due - recognized, "released": released, "factors": factors,
            "restricted_by": list(explained.restricted_by), "formula": explained.to_dict()}


def _limits(player_id: int, nature: Nature, at: int) -> Tuple[int, int, Optional[int]]:
    w, s, t = _limits_provider(player_id, nature, at)
    for name, v in (("W", w), ("S", s)):
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError(f"limite {name} inválido: {v!r}")
    if t is not None and (not isinstance(t, int) or isinstance(t, bool) or t < 0):
        raise ValueError(f"limite T inválido: {t!r}")
    return w, s, t


def _political_due(player_id: int, day: int) -> int:
    if _political_provider is None:
        return 0
    v = _political_provider(player_id, day)
    if not isinstance(v, int) or isinstance(v, bool) or v < 0:
        raise ValueError(f"salário político devido inválido: {v!r}")
    return v


def preview_remuneration(player_id: int, nature: Nature, due: int, *, competence_day: Optional[int] = None,
                         at: Optional[int] = None) -> ActionResult:
    """O que seria reconhecido AGORA para este valor (sem gravar nada): base do feedback ao jogador (doc 20)."""
    problem = amount_problem(due)
    if problem:
        return _refuse(problem, amount=due)
    if nature not in REMUNERATION_NATURES:
        return _refuse("NATURE_INVALID", nature=str(nature))
    if _limits_provider is None:
        return _refuse("REMUNERATION_LIMITS_UNSPECIFIED")
    at = game_clock.now() if at is None else at
    day = competence_day_of(at) if competence_day is None else competence_day
    c = RemunerationCounter.objects.filter(player_id=player_id, competence_day=day).first()
    w, s, t = _limits(player_id, nature, at)
    out = compute_recognition(RemunerationInputs(
        nature, due, w, s, t, c.c_s if c else 0, c.c_t if c else 0, c.c_p if c else 0, c.p_released if c else 0,
        _political_due(player_id, day)), at)
    return ActionResult(True, "OK", out)


# --- submissão ----------------------------------------------------------------------------------------------------------

def _request_hash(fields: Sequence[Any]) -> str:
    return hashlib.sha256(json.dumps(list(fields), sort_keys=True, default=str).encode()).hexdigest()


def submit_remuneration(*, key: str, player_id: int, payer_id: int, nature: Nature, due: int, earned_at: int,
                        policy: Policy, reference_kind: str, reference_id, tax_rate: Decimal = Decimal(0),
                        tax_territory: str = "", competence_day: Optional[int] = None) -> ActionResult:
    """
    Registra o pedido; NÃO move dinheiro. `earned_at` é o instante em que a remuneração foi devida (compõe a ordem estável).
    `policy` é a decisão do sistema pagador para caixa insuficiente. Idempotente por `key`.
    """
    reference_id = str(reference_id)
    if not key or not reference_kind or not reference_id:
        return _refuse("REFERENCE_REQUIRED")
    problem = amount_problem(due)
    if problem:
        return _refuse(problem, amount=due)
    try:
        nature = Nature(nature)
        policy = Policy(policy)
    except ValueError:
        return _refuse("NATURE_INVALID", nature=str(nature))
    if nature not in REMUNERATION_NATURES:
        return _refuse("NATURE_INVALID", nature=nature.value)
    problem = tax_rate_problem(tax_rate) or tax_territory_problem(tax_territory)
    if problem:
        return _refuse(problem, rate=str(tax_rate), territory=tax_territory)
    tax_rate = canonical_rate(tax_rate)
    if not isinstance(earned_at, int) or isinstance(earned_at, bool):
        return _refuse("EARNED_AT_INVALID")
    day = competence_day_of(earned_at) if competence_day is None else competence_day
    try:
        payee = ledger.player_account(player_id)
    except ledger.LedgerRefusal as e:
        return e.result
    payer = Account.objects.filter(pk=payer_id).first()
    if payer is None:
        return _refuse("ACCOUNT_NOT_FOUND", account=payer_id)
    if payer.pk == payee.pk:
        return _refuse("SAME_ACCOUNT", account=payer_id)
    h = _request_hash([player_id, payer_id, nature.value, due, earned_at, policy.value, reference_kind, reference_id,
                       str(tax_rate), tax_territory, day])   # `tax_rate` já canônico (6 casas): 0.1 == "0.10"
    def _replay(existing: RemunerationRequest) -> ActionResult:
        if existing.payload_hash != h:
            return _refuse("IDEMPOTENCY_CONFLICT", key=key)
        return ActionResult(True, "OK", {"request_id": existing.pk, "status": existing.status, "already_posted": True})

    with transaction.atomic():
        existing = RemunerationRequest.objects.filter(key=key).first()
        if existing is not None:
            return _replay(existing)
        try:
            with transaction.atomic():
                r = RemunerationRequest.objects.create(
                    key=key, payload_hash=h, player_id=player_id, payer=payer, nature=nature.value, due=due,
                    competence_day=day, earned_at=earned_at, policy=policy.value, reference_kind=reference_kind,
                    reference_id=reference_id, tax_rate=tax_rate, tax_territory=tax_territory)
        except IntegrityError:
            winner = RemunerationRequest.objects.filter(key=key).first()
            return _replay(winner) if winner is not None else _refuse("IDEMPOTENCY_CONFLICT", key=key)
    return ActionResult(True, "OK", {"request_id": r.pk, "status": r.status, "already_posted": False})


# --- liquidação ---------------------------------------------------------------------------------------------------------

def sort_key(r: RemunerationRequest) -> Tuple:
    """Ordem estável: só dados do pedido (§24.12.4). Político primeiro; depois competência e instante do fato."""
    political = 0 if r.nature == Nature.POLITICAL_SALARY.value else 1
    return (political, r.competence_day, r.earned_at, r.payer_id, r.nature, r.reference_kind, r.reference_id, r.key)


def liquidate_remuneration(*, batch: str, at: Optional[int] = None, keys: Optional[Iterable[str]] = None) -> ActionResult:
    """
    Processa, em UM lote atômico, todos os pedidos SUBMITTED (ou só `keys`). Cada pedido vê os contadores deixados pelos
    anteriores na ordem estável. Tudo ou nada: erro de infraestrutura (ex.: roteamento tributário ambíguo) desfaz o lote.
    """
    if not batch:
        return _refuse("KEY_REQUIRED")
    at = game_clock.now() if at is None else at
    with transaction.atomic():
        qs = RemunerationRequest.objects.select_for_update().filter(status=RequestStatus.SUBMITTED.value)
        if keys is not None:
            qs = qs.filter(key__in=list(keys))
        requests = sorted(qs, key=sort_key)
        if not requests:
            return ActionResult(True, "OK", {"batch": batch, "processed": [], "count": 0})
        if _limits_provider is None:
            return _refuse("REMUNERATION_LIMITS_UNSPECIFIED")
        counters = _load_counters(requests)
        rows: List[Dict[str, Any]] = []
        try:
            for position, req in enumerate(requests):
                rows.append(_process(req, position, batch, at, counters[(req.player_id, req.competence_day)]))
        except ledger._Refuse as r:
            transaction.set_rollback(True)
            return r.result
    return ActionResult(True, "OK", {"batch": batch, "processed": rows, "count": len(rows)})


def _load_counters(requests: Sequence[RemunerationRequest]) -> Dict[Tuple[int, int], RemunerationCounter]:
    wanted = sorted({(r.player_id, r.competence_day) for r in requests})
    for player_id, day in wanted:       # cria na ordem estável, depois trava (sem deadlock entre lotes)
        RemunerationCounter.objects.get_or_create(player_id=player_id, competence_day=day)
    out: Dict[Tuple[int, int], RemunerationCounter] = {}
    for player_id, day in wanted:
        out[(player_id, day)] = RemunerationCounter.objects.select_for_update().get(player_id=player_id, competence_day=day)
    return out


def _process(req: RemunerationRequest, position: int, batch: str, at: int, counter: RemunerationCounter) -> Dict[str, Any]:
    nature = Nature(req.nature)
    policy = Policy(req.policy)
    w, s, t = _limits(req.player_id, nature, at)
    inputs = RemunerationInputs(nature, req.due, w, s, t, counter.c_s, counter.c_t, counter.c_p, counter.p_released,
                                _political_due(req.player_id, req.competence_day))
    calc = compute_recognition(inputs, at)
    recognized = calc["recognized"]
    payee = ledger.player_account(req.player_id)
    tax = percent_of(recognized, req.tax_rate) if recognized else 0
    net = recognized - tax
    # quanto realmente SAI da conta pagadora (imposto autocompensado não sai, R2)
    outflow = recognized
    if tax:
        route = ledger.route_tax(ledger.territory_from_str(req.tax_territory), at)
        if not route.ok:
            raise ledger._Refuse(route)
        if route.detail["account_id"] == req.payer_id:
            outflow = net
    explained: Dict[str, Any] = {"request": req.key, "nature": nature.value, "policy": policy.value, "position": position,
                                 "batch": batch, **calc}
    outcome: str
    paid = pending = 0
    obligation = None
    if recognized == 0:
        outcome = "NO_ROOM"
    elif ledger.available_of(req.payer_id) >= outflow:
        pay = ledger.post_taxed_payment(
            req.payer_id, payee.pk, recognized, nature=nature, tax_rate=req.tax_rate,
            territory=ledger.territory_from_str(req.tax_territory), tax_nature=Nature.TAX_INCOME,
            key=f"remuneration:{req.key}", reference_kind=req.reference_kind, reference_id=req.reference_id, at=at,
            competence_day=req.competence_day, actor="payroll", operation="remuneration",
            explained_extra={"request": req.key, "position": position}, _internal=True)
        if not pay.ok:
            raise ledger._Refuse(pay)
        outcome, paid = "PAID", recognized
    elif policy == Policy.PENDING:
        opened = obligations_mod.open_obligation(
            req.payer_id, payee.pk, recognized, nature, key=f"obligation:{req.key}", reference_kind=req.reference_kind,
            reference_id=req.reference_id, competence_day=req.competence_day, tax_rate=req.tax_rate,
            tax_territory=req.tax_territory, at=at)
        if not opened.ok:
            raise ledger._Refuse(opened)
        obligation = Obligation.objects.get(pk=opened.detail["obligation_id"])
        outcome, pending = "PENDING", recognized
    else:   # REFUSE: nada é reconhecido; o limite que sobrar vale para o próximo pedido da sequência
        explained.update({"outcome": "REFUSED", "code": "INSUFFICIENT_FUNDS",
                          "available": ledger.available_of(req.payer_id), "needed": outflow})
        RemunerationRequest.objects.filter(pk=req.pk).update(
            status=RequestStatus.REFUSED.value, position=position, batch=batch, explained=explained, liquidated_at=at)
        return {"key": req.key, "status": RequestStatus.REFUSED.value, "code": "INSUFFICIENT_FUNDS", "recognized": 0,
                "position": position}
    # reconhecido: contadores (bruto, na competência do pedido; R1)
    counter.c_t += recognized
    if nature in COUNTS_IN_C_S:
        counter.c_s += recognized
    if nature == Nature.POLITICAL_SALARY:
        counter.c_p += recognized
        counter.p_released += calc["released"]
    counter.save(update_fields=["c_s", "c_t", "c_p", "p_released"])
    explained.update({"outcome": outcome, "paid": paid, "pending": pending, "tax": tax, "net": net,
                      "counters_after": {"C_S": counter.c_s, "C_T": counter.c_t, "C_P": counter.c_p,
                                         "P_liberada": counter.p_released}})
    RemunerationRequest.objects.filter(pk=req.pk).update(
        status=RequestStatus.RECOGNIZED.value, recognized=recognized, discarded=calc["discarded"], paid=paid,
        pending=pending, tax=tax, net=net, position=position, batch=batch, explained=explained, liquidated_at=at,
        obligation=obligation)
    return {"key": req.key, "status": RequestStatus.RECOGNIZED.value, "outcome": outcome, "recognized": recognized,
            "discarded": calc["discarded"], "paid": paid, "pending": pending, "tax": tax, "net": net, "position": position}


def pay_remuneration_now(**kwargs) -> ActionResult:
    """Submeter + liquidar um pedido (trabalho: remuneração que nasce de uma ação). Devolve o pedido já processado."""
    key = kwargs.get("key")
    submitted = submit_remuneration(**kwargs)
    if not submitted.ok:
        return submitted
    req = RemunerationRequest.objects.get(pk=submitted.detail["request_id"])
    if req.status == RequestStatus.SUBMITTED.value:
        done = liquidate_remuneration(batch=f"now:{key}", keys=[key])
        if not done.ok:
            return done
        req.refresh_from_db()
    ok = req.status == RequestStatus.RECOGNIZED.value
    detail = {"request_id": req.pk, "status": req.status, "recognized": req.recognized, "discarded": req.discarded,
              "paid": req.paid, "pending": req.pending, "tax": req.tax, "net": req.net, "explained": req.explained,
              "already_posted": submitted.detail["already_posted"]}
    return ActionResult(ok, "OK" if ok else req.explained.get("code", "REFUSED"), detail)
