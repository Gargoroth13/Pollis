"""
Motor de contratos (design/18). Proposta, aceite das duas partes (18.4), execução automática nas datas (18.5), inadimplência (18.6),
quebra voluntária (18.7), multa (18.8), encerramento (18.9) e histórico imutável (18.11). Os TIPOS vivem em `handlers`.

Quem age por uma empresa é o seu Dono (02 §16); por si, o próprio jogador. Dinheiro só se move por lançamentos do registro monetário
(multa = transferência `PENALTY`, nunca dinheiro novo) e estoque só por `companies.stock` (24; 02).

PROTOCOLO de trava: jogador que age + jogador(es)-parte (crescente) → empresa(s)-parte (crescente) → contrato → estoque → registro.
Idempotência: ocorrência única por (contrato, sequência); chaves `contract:{id}:exec:{n}` no registro monetário e no estoque.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from django.db import IntegrityError, transaction
from django.db.models import Max

from companies import services as company_services
from companies.models import Company
from core import clock as game_clock
from core import ticks
from core.timeline import TickKind
from ledger import obligations as ledger_obligations
from ledger import services as ledger
from ledger.constants import Nature, ObligationStatus
from ledger.models import Obligation
from ledger.money import competence_day_of
from players.models import Player
from players.services import ActionResult

from . import handlers
from .constants import (ENDED_STATUSES, KEY_PREFIX, REFERENCE_KIND, RUNNING_STATUSES, EventKind, ExecutionStatus, Frequency,
                        PartyKind, Responsible, Side, Status)
from .handlers import Outcome, refuse
from .models import Contract, ContractEvent, ContractExecution, terms_digest

TICK_NAME = "contracts_daily_execution"
PROPOSAL_KEYS = frozenset({"type", "role", "proposer", "counterparty", "terms", "frequency", "starts_on", "ends_on", "penalty_cents",
                           "max_failures"})
REQUIRED_PROPOSAL_KEYS = frozenset({"type", "role", "proposer", "counterparty", "terms", "frequency"})


class _Rollback(Exception):
    """Desfaz a transação inteira e devolve a recusa (o aceite que não pôde ativar não deixa meio-estado)."""

    def __init__(self, result: ActionResult):
        self.result = result


# --- identidade e autoridade --------------------------------------------------------------------------------------------

def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def parse_party(value: Any) -> Union[Tuple[PartyKind, int], ActionResult]:
    if not isinstance(value, dict) or set(value) != {"kind", "id"} or not _is_int(value["id"]) or value["id"] <= 0:
        return refuse("INVALID_PARTY", party=repr(value)[:60])
    try:
        return PartyKind(value["kind"]), value["id"]
    except ValueError:
        return refuse("INVALID_PARTY", party=repr(value)[:60])


def party_exists(kind: PartyKind, entity_id: int) -> bool:
    return (Player.objects.filter(pk=entity_id).exists() if kind is PartyKind.PLAYER else Company.objects.filter(pk=entity_id).exists())


def authority_refusal(actor_id: int, kind: PartyKind, entity_id: int) -> Optional[ActionResult]:
    """O jogador age por si; por uma empresa, só o Dono (02 §16)."""
    if kind is PartyKind.PLAYER:
        return None if entity_id == actor_id else refuse("NOT_PARTY_REPRESENTATIVE", party=[kind.value, entity_id])
    if not Company.objects.filter(pk=entity_id).exists():
        return refuse("COMPANY_NOT_FOUND", company=entity_id)
    return None if company_services.owner_of(entity_id) == actor_id else refuse("NOT_OWNER", company=entity_id)


def _lock(actor_id: int, parties: List[Tuple[str, int]]) -> None:
    """Jogador(es) crescente → empresa(s) crescente. O contrato é travado depois, por quem chama."""
    player_ids = sorted({actor_id} | {i for k, i in parties if k == PartyKind.PLAYER.value})
    list(Player.objects.select_for_update().filter(pk__in=player_ids).order_by("pk"))
    company_ids = sorted({i for k, i in parties if k == PartyKind.COMPANY.value})
    if company_ids:
        list(Company.objects.select_for_update().filter(pk__in=company_ids).order_by("pk"))


def _parties_of(c: Contract) -> List[Tuple[str, int]]:
    return [(c.party_a_kind, c.party_a_id), (c.party_b_kind, c.party_b_id)]


def _event(c: Contract, kind: EventKind, at: int, *, actor: Optional[Tuple[str, int]] = None, ref: str = "", ledger_key: str = "",
           data: Optional[Dict[str, Any]] = None) -> ContractEvent:
    seq = (ContractEvent.objects.filter(contract=c).aggregate(m=Max("seq"))["m"] or 0) + 1       # contrato travado: sem corrida
    return ContractEvent.objects.create(contract=c, seq=seq, kind=kind.value, at=at, competence_day=competence_day_of(at),
                                        actor_kind="" if actor is None else actor[0], actor_id=None if actor is None else actor[1],
                                        ref=ref, ledger_key=ledger_key, data=data or {})


def _side_of(c: Contract, party: Tuple[PartyKind, int]) -> Optional[Side]:
    if (c.party_a_kind, c.party_a_id) == (party[0].value, party[1]):
        return Side.A
    if (c.party_b_kind, c.party_b_id) == (party[0].value, party[1]):
        return Side.B
    return None


def _account(c: Contract, side: Side) -> int:
    kind, entity = c.party(side)
    return handlers.account_of(kind, entity)


def _other(side: Side) -> Side:
    return Side.B if side is Side.A else Side.A


# --- proposta ------------------------------------------------------------------------------------------------------------

@dataclass
class _Parsed:
    handler: handlers.Handler
    proposer_side: Side
    a: Tuple[PartyKind, int]
    b: Tuple[PartyKind, int]
    frequency: Frequency
    prepared: handlers.Prepared
    penalty_cents: int
    max_failures: Optional[int]


def parse_proposal(actor_id: Any, proposal: Any, now: Optional[int] = None) -> Union[ActionResult, _Parsed]:
    """Todas as recusas de uma proposta que só LEEM (o serviço usa a mesma função, de novo, com tudo travado)."""
    if not _is_int(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    if not isinstance(proposal, dict) or not REQUIRED_PROPOSAL_KEYS <= set(proposal) or not set(proposal) <= PROPOSAL_KEYS:
        return refuse("INVALID_PARAMS", required=sorted(REQUIRED_PROPOSAL_KEYS), allowed=sorted(PROPOSAL_KEYS))
    handler = handlers.get_handler(proposal["type"]) if isinstance(proposal["type"], str) else None
    if handler is None:
        return refuse("TYPE_NOT_AVAILABLE", type=repr(proposal["type"])[:30], available=handlers.registered_types())
    if proposal["role"] not in (handler.role_a, handler.role_b):
        return refuse("INVALID_ROLE", role=repr(proposal["role"])[:30], roles=[handler.role_a, handler.role_b])
    mine, theirs = parse_party(proposal["proposer"]), parse_party(proposal["counterparty"])
    for party in (mine, theirs):
        if isinstance(party, ActionResult):
            return party
    side = Side.A if proposal["role"] == handler.role_a else Side.B
    a, b = (mine, theirs) if side is Side.A else (theirs, mine)
    if a == b:
        return refuse("SAME_PARTY", party=[a[0].value, a[1]])
    if a[0] not in handler.kinds_a or b[0] not in handler.kinds_b:
        return refuse("PARTY_KIND_NOT_ALLOWED", type=handler.type.value, role_a=handler.role_a, kinds_a=sorted(k.value for k in handler.kinds_a),
                      role_b=handler.role_b, kinds_b=sorted(k.value for k in handler.kinds_b))
    for party in (a, b):
        if not party_exists(*party):
            return refuse("PARTY_NOT_FOUND", party=[party[0].value, party[1]])
    refusal = authority_refusal(actor_id, *mine)
    if refusal is not None:
        return refusal
    try:
        frequency = Frequency(proposal["frequency"])
    except ValueError:
        return refuse("INVALID_FREQUENCY", frequency=repr(proposal["frequency"])[:30], allowed=[f.value for f in Frequency])
    now = game_clock.now() if now is None else now
    today = competence_day_of(now)
    prepared = handler.prepare({"terms": proposal["terms"], "frequency": frequency, "starts_on": proposal.get("starts_on"),
                                "ends_on": proposal.get("ends_on")}, today, (a[0].value, a[1]), (b[0].value, b[1]))
    if isinstance(prepared, ActionResult):
        return prepared
    penalty = proposal.get("penalty_cents", 0)
    if not _is_int(penalty) or not 0 <= penalty <= prepared.penalty_limit:
        return refuse("INVALID_PENALTY", penalty_cents=repr(penalty)[:40], max=prepared.penalty_limit)
    max_failures = proposal.get("max_failures")
    if max_failures is not None and (not _is_int(max_failures) or max_failures < 1):
        return refuse("INVALID_MAX_FAILURES", max_failures=repr(max_failures)[:40])
    return _Parsed(handler, side, a, b, frequency, prepared, penalty, max_failures)


def propose(actor_id: int, proposal: Any) -> ActionResult:
    """
    Cria a proposta; quem propõe já aceita (18.4). Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS, TYPE_NOT_AVAILABLE, INVALID_ROLE,
    INVALID_PARTY, SAME_PARTY, PARTY_KIND_NOT_ALLOWED, PARTY_NOT_FOUND, NOT_PARTY_REPRESENTATIVE, NOT_OWNER, INVALID_FREQUENCY,
    INVALID_PENALTY, INVALID_MAX_FAILURES e as do tipo (INVALID_TERMS, UNKNOWN_PRODUCT, INVALID_SCHEDULE, ...).
    """
    first = parse_proposal(actor_id, proposal)
    if isinstance(first, ActionResult):
        return first
    with transaction.atomic():
        _lock(actor_id, [(first.a[0].value, first.a[1]), (first.b[0].value, first.b[1])])
        now = game_clock.now()
        p = parse_proposal(actor_id, proposal, now)
        if isinstance(p, ActionResult):
            return p
        c = Contract(type=p.handler.type.value, status=Status.PROPOSED.value, party_a_kind=p.a[0].value, party_a_id=p.a[1],
                     party_b_kind=p.b[0].value, party_b_id=p.b[1], proposed_by=p.proposer_side.value, terms=p.prepared.terms,
                     frequency=p.frequency.value, starts_on=p.prepared.starts_on, ends_on=p.prepared.ends_on,
                     penalty_cents=p.penalty_cents, max_failures=p.max_failures, occurrences=p.prepared.occurrences, created_at=now)
        setattr(c, f"accepted_{p.proposer_side.value}_at", now)
        c.save()
        actor = (p.a if p.proposer_side is Side.A else p.b)
        _event(c, EventKind.CREATED, now, actor=(actor[0].value, actor[1]),
               data={"type": c.type, "a": [c.party_a_kind, c.party_a_id], "b": [c.party_b_kind, c.party_b_id], "terms": c.terms,
                     "frequency": c.frequency, "starts_on": c.starts_on, "ends_on": c.ends_on, "occurrences": c.occurrences,
                     "penalty_cents": c.penalty_cents, "max_failures": c.max_failures, "acted_by_player": actor_id})
        _event(c, EventKind.ACCEPTED, now, actor=(actor[0].value, actor[1]), ref=p.proposer_side.value, data={"side": p.proposer_side.value})
        return ActionResult(True, "OK", {"contract": c.pk, "status": c.status, "terms_hash": c.terms_hash, "occurrences": c.occurrences})


# --- aceite, recusa, retirada ----------------------------------------------------------------------------------------------

def _load(contract_id: Any) -> Union[Contract, ActionResult]:
    c = Contract.objects.filter(pk=contract_id).first() if _is_int(contract_id) and -2 ** 63 <= contract_id < 2 ** 63 else None
    return refuse("CONTRACT_NOT_FOUND", contract=repr(contract_id)[:40]) if c is None else c


def _as_side(actor_id: Any, c: Contract, party_value: Any) -> Union[Side, ActionResult]:
    party = parse_party(party_value)
    if isinstance(party, ActionResult):
        return party
    side = _side_of(c, party)
    if side is None:
        return refuse("NOT_A_PARTY", contract=c.pk, party=[party[0].value, party[1]])
    refusal = authority_refusal(actor_id, *party)
    return refusal if refusal is not None else side


def accept_refusal(actor_id: Any, contract_id: Any, party: Any, now: Optional[int] = None):
    if not _is_int(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    c = _load(contract_id)
    if isinstance(c, ActionResult):
        return c
    side = _as_side(actor_id, c, party)
    if isinstance(side, ActionResult):
        return side
    if c.status != Status.PROPOSED.value:
        return refuse("NOT_PROPOSED", contract=c.pk, status=c.status)
    if getattr(c, f"accepted_{side.value}_at") is not None:
        return refuse("ALREADY_ACCEPTED", contract=c.pk, side=side.value)
    refusal = handlers.get_handler(c.type).acceptance_refusal(c, competence_day_of(game_clock.now() if now is None else now)) \
        if handlers.get_handler(c.type) else refuse("TYPE_NOT_AVAILABLE", type=c.type)
    return refusal if refusal is not None else (c, side)


def accept(actor_id: int, contract_id: Any, party: Any) -> ActionResult:
    """
    Aceite de uma parte (18.4). Com as DUAS aceitas o contrato entra em vigor (o efeito do tipo acontece nesse instante; se ele
    não puder acontecer, o aceite é desfeito). Recusas: ver `accept_refusal` + as do `activate` do tipo (ex.: LENDER_INSUFFICIENT_FUNDS).
    """
    first = accept_refusal(actor_id, contract_id, party)
    if isinstance(first, ActionResult):
        return first
    c0, _ = first
    try:
        with transaction.atomic():
            _lock(actor_id, _parties_of(c0))
            c = Contract.objects.select_for_update().get(pk=c0.pk)
            now = game_clock.now()
            again = accept_refusal(actor_id, contract_id, party, now)
            if isinstance(again, ActionResult):
                return again
            c, side = again[0], again[1]
            c = Contract.objects.select_for_update().get(pk=c.pk)
            setattr(c, f"accepted_{side.value}_at", now)
            kind, entity = c.party(side)
            _event(c, EventKind.ACCEPTED, now, actor=(kind, entity), ref=side.value, data={"side": side.value, "acted_by_player": actor_id})
            activated = c.accepted_a_at is not None and c.accepted_b_at is not None
            if activated:
                _activate(c, now)
            c.save()
            return ActionResult(True, "OK", {"contract": c.pk, "status": c.status, "activated": activated})
    except _Rollback as r:
        return r.result


def _activate(c: Contract, now: int) -> None:
    handler = handlers.get_handler(c.type)
    day = competence_day_of(now)
    c.anchor_day, c.last_due_day = handler.anchor(c, day)
    c.status, c.activated_at, c.next_sequence = Status.ACTIVE.value, now, 0
    res = handler.activate(c, now)
    if not res.ok:
        raise _Rollback(res)
    c.next_due_day = handler.due_day(c, 0)
    _event(c, EventKind.ACTIVATED, now, data={"anchor_day": c.anchor_day, "last_due_day": c.last_due_day, "first_due_day": c.next_due_day})
    if res.detail.get("ledger_key"):
        _event(c, EventKind.DISBURSED, now, ledger_key=res.detail["ledger_key"], data=dict(res.detail))


def _cancel_refusal(actor_id: Any, contract_id: Any, party: Any, *, proposer: bool):
    if not _is_int(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    c = _load(contract_id)
    if isinstance(c, ActionResult):
        return c
    side = _as_side(actor_id, c, party)
    if isinstance(side, ActionResult):
        return side
    if c.status != Status.PROPOSED.value:
        return refuse("NOT_PROPOSED", contract=c.pk, status=c.status)
    if (side.value == c.proposed_by) != proposer:
        return refuse("NOT_PROPOSER" if proposer else "IS_PROPOSER", contract=c.pk)
    return c, side


def decline_refusal(actor_id, contract_id, party):
    return _cancel_refusal(actor_id, contract_id, party, proposer=False)


def withdraw_refusal(actor_id, contract_id, party):
    return _cancel_refusal(actor_id, contract_id, party, proposer=True)


def _cancel(actor_id: int, contract_id: Any, party: Any, *, proposer: bool) -> ActionResult:
    first = _cancel_refusal(actor_id, contract_id, party, proposer=proposer)
    if isinstance(first, ActionResult):
        return first
    with transaction.atomic():
        _lock(actor_id, _parties_of(first[0]))
        Contract.objects.select_for_update().get(pk=first[0].pk)
        again = _cancel_refusal(actor_id, contract_id, party, proposer=proposer)
        if isinstance(again, ActionResult):
            return again
        c = Contract.objects.select_for_update().get(pk=again[0].pk)
        side, now = again[1], game_clock.now()
        kind = EventKind.WITHDRAWN if proposer else EventKind.DECLINED
        c.status, c.ended_at, c.end_reason = Status.CANCELLED.value, now, "withdrawn" if proposer else f"declined_by_{side.value}"
        _event(c, kind, now, actor=c.party(side), data={"side": side.value, "acted_by_player": actor_id})
        c.save()
        return ActionResult(True, "OK", {"contract": c.pk, "status": c.status, "reason": c.end_reason})


def decline(actor_id: int, contract_id: Any, party: Any) -> ActionResult:
    """A outra parte recusa a proposta: nunca entrou em vigor (estado técnico CANCELLED)."""
    return _cancel(actor_id, contract_id, party, proposer=False)


def withdraw(actor_id: int, contract_id: Any, party: Any) -> ActionResult:
    """Quem propôs retira a proposta antes do aceite da outra parte."""
    return _cancel(actor_id, contract_id, party, proposer=True)


# --- quebra voluntária (18.7) e multa (18.8) -------------------------------------------------------------------------------

def break_refusal(actor_id: Any, contract_id: Any, party: Any):
    if not _is_int(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    c = _load(contract_id)
    if isinstance(c, ActionResult):
        return c
    side = _as_side(actor_id, c, party)
    if isinstance(side, ActionResult):
        return side
    if Status(c.status) not in RUNNING_STATUSES:
        return refuse("NOT_RUNNING", contract=c.pk, status=c.status)
    return c, side


def break_contract(actor_id: int, contract_id: Any, party: Any) -> ActionResult:
    """
    Qualquer parte pede o encerramento antecipado. A multa prevista (se houver) é paga, de verdade, à outra parte ANTES de o contrato
    mudar de estado: sem caixa para ela a quebra é recusada (PENALTY_UNPAYABLE) e nada muda. Depois o tipo resolve o que restava
    (`on_terminated`) e o contrato fica QUEBRADO. Recusas: ver `break_refusal` + PENALTY_UNPAYABLE.
    """
    first = break_refusal(actor_id, contract_id, party)
    if isinstance(first, ActionResult):
        return first
    try:
        with transaction.atomic():
            _lock(actor_id, _parties_of(first[0]))
            again = break_refusal(actor_id, contract_id, party)
            if isinstance(again, ActionResult):
                return again
            c = Contract.objects.select_for_update().get(pk=again[0].pk)
            if Status(c.status) not in RUNNING_STATUSES:
                return refuse("NOT_RUNNING", contract=c.pk, status=c.status)
            side, now = again[1], game_clock.now()
            _event(c, EventKind.BREAK_REQUESTED, now, actor=c.party(side), data={"side": side.value, "acted_by_player": actor_id})
            if c.penalty_cents > 0:
                paid = ledger.transfer(_account(c, side), _account(c, _other(side)), c.penalty_cents, Nature.PENALTY,
                                       key=f"{KEY_PREFIX}{c.pk}:penalty", reference_kind=REFERENCE_KIND, reference_id=f"{c.pk}:penalty",
                                       at=now, operation="contract_penalty", explained={"contract": c.pk, "cause": "voluntary_break",
                                                                                          "responsible": side.value})
                if not paid.ok:
                    raise _Rollback(refuse("PENALTY_UNPAYABLE", contract=c.pk, penalty_cents=c.penalty_cents, why=paid.code))
                _event(c, EventKind.PENALTY_APPLIED, now, ledger_key=f"{KEY_PREFIX}{c.pk}:penalty",
                       data={"responsible": side.value, "to": _other(side).value, "amount_cents": c.penalty_cents, "paid": True})
            _terminate_broken(c, now, f"voluntary_break_by_{side.value}", "voluntary_break")
            c.save()
            return ActionResult(True, "OK", {"contract": c.pk, "status": c.status, "reason": c.end_reason, "penalty_cents": c.penalty_cents})
    except _Rollback as r:
        return r.result


def _terminate_broken(c: Contract, now: int, reason: str, cause: str) -> None:
    handler = handlers.get_handler(c.type)
    resolved = handler.on_terminated(c, now, cause)
    left = c.occurrences - c.next_sequence
    if left > 0 or resolved:
        _event(c, EventKind.REMAINING_CANCELLED, now, data={"occurrences_cancelled": left, **resolved})
    c.status, c.ended_at, c.end_reason, c.next_due_day = Status.BROKEN.value, now, reason, None
    _event(c, EventKind.BROKEN, now, data={"reason": reason})


# --- execução automática (18.5), inadimplência (18.6) -----------------------------------------------------------------------

def _open_obligations(contract_id: int):
    return Obligation.objects.filter(reference_kind=REFERENCE_KIND, reference_id__startswith=f"{contract_id}:",
                                     status=ObligationStatus.OPEN.value)


def _run_occurrence(contract_id: int, day: int, at: int) -> bool:
    """Executa a PRÓXIMA ocorrência devida do contrato (se houver). Devolve se executou. Idempotente."""
    c0 = Contract.objects.filter(pk=contract_id).first()
    if c0 is None:
        return False
    with transaction.atomic():
        _lock_parties_only(c0)
        c = Contract.objects.select_for_update().get(pk=contract_id)
        if Status(c.status) not in RUNNING_STATUSES or c.next_due_day is None or c.next_due_day > day:
            return False
        handler = handlers.get_handler(c.type)
        sequence, due = c.next_sequence, c.next_due_day
        if ContractExecution.objects.filter(contract=c, sequence=sequence).exists():
            raise RuntimeError(f"contrato {c.pk}: ocorrência {sequence} já registrada mas não avançada")
        outcome = handler.execute(c, sequence, due, at)
        _record(c, handler, sequence, due, at, outcome)
        return True


def _lock_parties_only(c: Contract) -> None:
    list(Player.objects.select_for_update().filter(pk__in=sorted({i for k, i in _parties_of(c) if k == PartyKind.PLAYER.value}))
         .order_by("pk"))
    company_ids = sorted({i for k, i in _parties_of(c) if k == PartyKind.COMPANY.value})
    if company_ids:
        list(Company.objects.select_for_update().filter(pk__in=company_ids).order_by("pk"))


def _record(c: Contract, handler: handlers.Handler, sequence: int, due: int, at: int, out: Outcome) -> None:
    ContractExecution.objects.create(
        contract=c, sequence=sequence, due_day=due, at=at,
        status=ExecutionStatus.SUCCESS.value if out.ok else ExecutionStatus.FAILED.value,
        failure_code=out.code if not out.ok else "", responsible=out.responsible.value if (not out.ok and out.responsible) else "",
        pending_quantity=out.pending_quantity, pending_cents=out.pending_cents, ledger_key=out.ledger_key, detail=out.detail)
    c.next_sequence = sequence + 1
    c.next_due_day = handler.due_day(c, sequence + 1) if c.next_sequence < c.occurrences else None
    if out.ok:
        _event(c, EventKind.EXECUTED, at, ref=str(sequence), ledger_key=out.ledger_key,
               data={"sequence": sequence, "due_day": due, **out.detail})
        if c.status == Status.DEFAULTED.value and not handler.obligation_backed and not _open_obligations(c.pk).exists():
            c.status = Status.ACTIVE.value
            _event(c, EventKind.DEFAULT_CURED, at, data={"sequence": sequence})
    else:
        c.failures += 1
        _event(c, EventKind.FAILED, at, ref=str(sequence),
               data={"sequence": sequence, "due_day": due, "code": out.code, "responsible": out.responsible.value if out.responsible else "",
                     "pending_quantity": out.pending_quantity, "pending_cents": out.pending_cents, **out.detail})
        if c.status == Status.ACTIVE.value:
            c.status = Status.DEFAULTED.value
            _event(c, EventKind.DEFAULT_ENTERED, at, data={"sequence": sequence, "code": out.code})
        if (c.max_failures is not None and c.failures >= c.max_failures
                and out.responsible in (Responsible.A, Responsible.B)):
            _break_by_default(c, at, Side(out.responsible.value))
    c.save()
    if Status(c.status) in RUNNING_STATUSES and c.next_sequence >= c.occurrences:
        _maybe_close(c, at)
        c.save()


def _break_by_default(c: Contract, now: int, responsible: Side) -> None:
    """Condição `max_failures` atingida (18.6): a multa vai do responsável à outra parte; sem caixa ela vira obrigação pendente."""
    if c.penalty_cents > 0:
        key = f"{KEY_PREFIX}{c.pk}:penalty"
        paid = ledger.transfer(_account(c, responsible), _account(c, _other(responsible)), c.penalty_cents, Nature.PENALTY, key=key,
                               reference_kind=REFERENCE_KIND, reference_id=f"{c.pk}:penalty", at=now, operation="contract_penalty",
                               explained={"contract": c.pk, "cause": "default", "responsible": responsible.value})
        pending = not paid.ok
        if pending:
            ob = ledger_obligations.open_obligation(_account(c, responsible), _account(c, _other(responsible)), c.penalty_cents,
                                                    Nature.PENALTY, key=key, reference_kind=REFERENCE_KIND,
                                                    reference_id=f"{c.pk}:penalty", at=now)
            if not ob.ok:
                raise RuntimeError(f"multa do contrato {c.pk}: {ob.code} {ob.detail}")
        _event(c, EventKind.PENALTY_APPLIED, now, ledger_key=key,
               data={"responsible": responsible.value, "to": _other(responsible).value, "amount_cents": c.penalty_cents, "paid": not pending})
    _terminate_broken(c, now, f"default_by_{responsible.value}", "default")


def _maybe_close(c: Contract, now: int) -> None:
    """Todas as ocorrências aconteceram: encerra (18.9), a menos que ainda haja dívida aberta do contrato (segue inadimplente)."""
    if _open_obligations(c.pk).exists():
        return
    c.status, c.ended_at, c.next_due_day = Status.CLOSED.value, now, None
    c.end_reason = "completed" if c.failures == 0 else "completed_with_failures"
    _event(c, EventKind.CLOSED, now, data={"reason": c.end_reason, "failures": c.failures})


def run_due(day: int, at: int) -> Dict[str, Any]:
    """Executa tudo que venceu até `day`, uma ocorrência por vez e em ordem de id (catch-up: várias, se o contrato ficou para trás)."""
    ran = []
    ids = list(Contract.objects.filter(status__in=[s.value for s in RUNNING_STATUSES], next_due_day__lte=day)
               .order_by("id").values_list("id", flat=True))
    for contract_id in ids:
        while _run_occurrence(contract_id, day, at):
            ran.append(contract_id)
    return {"executions": len(ran), "contracts": sorted(set(ran))}


def expire_proposals(day: int, at: int) -> List[int]:
    """Proposta cuja data de início já passou não pode mais ser aceita: vira CANCELLED (técnico) com motivo `expired`."""
    expired = []
    for c in Contract.objects.filter(status=Status.PROPOSED.value, starts_on__isnull=False, starts_on__lte=day).order_by("id"):
        with transaction.atomic():
            _lock_parties_only(c)
            c = Contract.objects.select_for_update().get(pk=c.pk)
            if c.status != Status.PROPOSED.value:
                continue
            c.status, c.ended_at, c.end_reason = Status.CANCELLED.value, at, "expired"
            _event(c, EventKind.WITHDRAWN, at, data={"reason": "expired", "starts_on": c.starts_on})
            c.save()
            expired.append(c.pk)
    return expired


def settle_defaults(day: int, at: int) -> Dict[str, Any]:
    """Quita (pelo caixa disponível, mais antiga primeiro) as dívidas geradas pelos contratos; depois reconcilia o histórico."""
    debtors = sorted(set(Obligation.objects.filter(reference_kind=REFERENCE_KIND, status=ObligationStatus.OPEN.value)
                         .values_list("debtor_id", flat=True)))
    paid = 0
    for debtor in debtors:
        res = ledger_obligations.settle_obligations(debtor, batch_key=f"contracts:{day}:{debtor}", at=at)
        if not res.ok:
            raise RuntimeError(f"quitação de dívidas de contratos (conta {debtor}): {res.code} {res.detail}")
        paid += res.detail["total_gross"]
    return {"settled_cents": paid, "reconciled": reconcile(at)}


def reconcile(at: int) -> int:
    """Registra no histórico as dívidas quitadas e tira da inadimplência o contrato sem dívida aberta. Idempotente."""
    n = 0
    paid_rows = Obligation.objects.filter(reference_kind=REFERENCE_KIND, status=ObligationStatus.PAID.value).values_list("pk", "reference_id")
    by_contract: Dict[int, List[int]] = {}
    for pk, ref in paid_rows:
        by_contract.setdefault(int(ref.split(":")[0]), []).append(pk)
    defaulted = list(Contract.objects.filter(status=Status.DEFAULTED.value).values_list("pk", flat=True))
    for contract_id in sorted(set(by_contract) | set(defaulted)):
        c0 = Contract.objects.get(pk=contract_id)
        known = set(ContractEvent.objects.filter(contract_id=contract_id, kind=EventKind.OBLIGATION_SETTLED.value).values_list("ref", flat=True))
        todo = [pk for pk in by_contract.get(contract_id, []) if f"ob{pk}" not in known]
        handler = handlers.get_handler(c0.type)
        if not todo and not (c0.status == Status.DEFAULTED.value and handler is not None and handler.obligation_backed):
            continue
        with transaction.atomic():
            _lock_parties_only(c0)
            c = Contract.objects.select_for_update().get(pk=contract_id)
            for pk in todo:
                ob = Obligation.objects.get(pk=pk)
                if not ContractEvent.objects.filter(contract=c, kind=EventKind.OBLIGATION_SETTLED.value, ref=f"ob{pk}").exists():
                    _event(c, EventKind.OBLIGATION_SETTLED, at, ref=f"ob{pk}", data={"obligation": pk, "reference": ob.reference_id,
                                                                                    "amount_cents": ob.amount_due})
                    n += 1
            if (c.status == Status.DEFAULTED.value and handler is not None and handler.obligation_backed
                    and not _open_obligations(c.pk).exists()):
                if c.next_sequence >= c.occurrences:
                    _maybe_close(c, at)
                else:
                    c.status = Status.ACTIVE.value
                    _event(c, EventKind.DEFAULT_CURED, at, data={"by": "obligations_settled"})
                c.save()
    return n


def _daily_tick(tick, ctx) -> None:
    day = competence_day_of(tick.at)
    expire_proposals(day, tick.at)
    settle_defaults(day, tick.at)          # dívida antiga primeiro: o caixa do dia paga o que já vencia (R4)
    run_due(day, tick.at)
    reconcile(tick.at)


def register() -> None:
    handlers.register_builtin()
    ticks.register(ticks.WORLD, TickKind.DAILY, TICK_NAME, priority=70)(_daily_tick)


# --- leitura ---------------------------------------------------------------------------------------------------------------

def contract_view(contract_id: int) -> Optional[Dict[str, Any]]:
    """Retrato completo para a UI/Bots: termos, estado, execuções e histórico (18.3, 18.11). Só LÊ."""
    c = Contract.objects.filter(pk=contract_id).first()
    if c is None:
        return None
    return {
        "id": c.pk, "type": c.type, "status": c.status, "a": [c.party_a_kind, c.party_a_id], "b": [c.party_b_kind, c.party_b_id],
        "proposed_by": c.proposed_by, "terms": c.terms, "frequency": c.frequency, "starts_on": c.starts_on, "ends_on": c.ends_on,
        "anchor_day": c.anchor_day, "last_due_day": c.last_due_day, "penalty_cents": c.penalty_cents, "max_failures": c.max_failures,
        "occurrences": c.occurrences, "next_sequence": c.next_sequence, "next_due_day": c.next_due_day, "failures": c.failures,
        "accepted": {"a": c.accepted_a_at, "b": c.accepted_b_at}, "end_reason": c.end_reason,
        "executions": [{"sequence": e.sequence, "due_day": e.due_day, "status": e.status, "failure_code": e.failure_code,
                        "responsible": e.responsible, "pending_quantity": e.pending_quantity, "pending_cents": e.pending_cents,
                        "detail": e.detail} for e in c.executions.all()],
        "events": [{"seq": e.seq, "kind": e.kind, "at": e.at, "actor": [e.actor_kind, e.actor_id], "ref": e.ref, "data": e.data}
                   for e in c.events.all()],
    }


def contracts_of(kind: PartyKind, entity_id: int) -> List[int]:
    from django.db.models import Q
    return list(Contract.objects.filter(Q(party_a_kind=kind.value, party_a_id=entity_id) | Q(party_b_kind=kind.value, party_b_id=entity_id))
                .order_by("id").values_list("id", flat=True))
