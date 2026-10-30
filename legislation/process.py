"""
Motor do calendário legislativo (design/07 §07.6-§07.19).

Cada proposta ativa guarda o PRÓXIMO instante em que algo acontece com ela (`deadline_at`) e o estado diz o quê:
  DISCUSSION       primeira segunda-feira 00:00 ≥ fim da discussão → abre a votação (composição congelada; 3 dias)
  VOTING           fim do prazo → apura (maioria absoluta das cadeiras): rejeita ou envia à sanção (3 dias)
  SANCTION         fim do prazo sem decisão → SANÇÃO AUTOMÁTICA; entra em vigor no próximo weekly tick
  VETOED           primeira segunda-feira depois do veto → abre a votação de derrubada (2/3 das cadeiras; 3 dias)
  OVERRIDE_VOTING  fim do prazo → derrubado (aguarda vigor) ou veto mantido (encerra)
  AWAITING_FORCE   `weekly tick` → entra em vigor (`laws.Law` + `LawChange`); não retroativo
`advance(at)` executa, em ordem de instante, tudo que venceu até `at`, usando o instante LÓGICO (o prazo), não o do processamento: um atraso do
tick não muda prazos nem resultados. É idempotente. A composição da Câmara e o Presidente vêm dos provedores no momento do processamento (granularidade
do tick de 10 minutos; design/07a, L3).

Interregno (07 §07.19): sem Câmara constituída os prazos ficam suspensos; ao voltar, discussões são prorrogadas pela duração, votações em andamento
são anuladas e reiniciadas com 3 dias completos, e propostas que aguardavam sanção/veto/derrubada voltam a uma votação completa da nova Câmara.
Leis já sancionadas que aguardam só o vigor seguem o calendário normal. Mudança de Presidente com proposta aguardando sanção: nova votação completa (07 §07.18).
"""
from __future__ import annotations

from typing import List, Optional

from django.db import transaction

from core import ticks
from core.timeline import Tick, TickKind

from . import authority, calendar, catalog, params
from .common import event
from .constants import ACTIVE, EventKind, Kind, LawStatus, RoundKind, RoundStatus, Status
from .models import Interregnum, Law, LawChange, LegislativeState, Proposal
from .voting import open_round, tally

TICK_NAME = "legislation.advance"
_NEEDS_CHAMBER = frozenset({Status.DISCUSSION.value, Status.VETOED.value})


def register_tick() -> None:
    ticks.register(ticks.WORLD, TickKind.TEN_MINUTES, TICK_NAME, priority=30)(_tick)


def _tick(tick: Tick, context) -> None:
    advance(tick.at)


def advance(at: int) -> int:
    """Processa tudo que venceu até `at`; devolve quantas transições aplicou."""
    with transaction.atomic():
        state = LegislativeState.load(for_update=True)
        applied = 0
        seats = authority.deputies()
        # 1) vence o que podia vencer ANTES de qualquer interregno (instantes lógicos)
        applied += _fire_due(at, state, chamber_present=bool(seats) and state.interregnum_since is None)
        # (com interregno aberto, abrir votação é sempre adiado: o prazo será prorrogado na retomada)
        # 2) detecta entrada/saída de interregno
        if not seats and state.interregnum_since is None:
            state.interregnum_since = at
            Interregnum.objects.create(started_at=at)
        elif seats and state.interregnum_since is not None:
            applied += _resume(state, at)
            applied += _fire_due(at, state, chamber_present=True)
        # 3) Presidente mudou/vagou com proposta aguardando sanção → nova votação completa (07 §07.18-§07.19)
        if seats:
            applied += _president_checks(at)
        state.last_advanced_at = max(state.last_advanced_at, at)
        state.save(update_fields=["interregnum_since", "last_advanced_at"])
        return applied


# --- vencimentos ------------------------------------------------------------------------------------------------------------------------------
def _due(at: int, state: LegislativeState, chamber_present: bool) -> Optional[Proposal]:
    bound = state.interregnum_since
    for p in Proposal.objects.select_for_update().filter(status__in=[s.value for s in ACTIVE], deadline_at__isnull=False,
                                                        deadline_at__lte=at).order_by("deadline_at", "pk"):
        if p.status == Status.AWAITING_FORCE.value:
            return p                                   # "seguem o calendário normal" mesmo no interregno (07 §07.19)
        if bound is not None and p.deadline_at > bound:
            continue                                   # suspenso
        if p.status in _NEEDS_CHAMBER and not chamber_present:
            continue
        return p
    return None


def _fire_due(at: int, state: LegislativeState, chamber_present: bool) -> int:
    n = 0
    while True:
        p = _due(at, state, chamber_present)
        if p is None:
            return n
        _transition(p, p.deadline_at)
        n += 1


def _transition(p: Proposal, t: int) -> None:
    status = Status(p.status)
    if status is Status.DISCUSSION:
        _open_vote(p, t, RoundKind.MAIN, EventKind.VOTE_OPENED)
    elif status is Status.VOTING:
        _close_main(p, t)
    elif status is Status.SANCTION:
        _auto_sanction(p, t)
    elif status is Status.VETOED:
        _open_vote(p, t, RoundKind.OVERRIDE, EventKind.OVERRIDE_OPENED)
    elif status is Status.OVERRIDE_VOTING:
        _close_override(p, t)
    elif status is Status.AWAITING_FORCE:
        _enter_force(p, t)


def _open_vote(p: Proposal, t: int, kind: RoundKind, ev: EventKind, **extra) -> None:
    seats = authority.deputies()
    ends = t + params.VOTING_SECONDS
    rnd = open_round(p, kind, t, seats, ends)
    p.status = Status.VOTING.value if kind is RoundKind.MAIN else Status.OVERRIDE_VOTING.value
    p.deadline_at, p.president_id = ends, None
    p.save(update_fields=["status", "deadline_at", "round_no", "president_id"])
    event(p, ev, t, None, round=rnd.number, seats=rnd.seats_count, ends_at=ends, composition=list(seats), **extra)


def _close_round(p: Proposal, t: int) -> dict:
    rnd = p.rounds.select_for_update().get(status=RoundStatus.OPEN.value)
    result = tally(rnd)
    rnd.status, rnd.closed_at, rnd.tally, rnd.approved = RoundStatus.CLOSED.value, t, result, result["approved"]
    rnd.save(update_fields=["status", "closed_at", "tally", "approved"])
    return result


def _close_main(p: Proposal, t: int) -> None:
    result = _close_round(p, t)
    event(p, EventKind.VOTE_CLOSED, t, None, **result)
    if not result["approved"]:
        p.status, p.deadline_at, p.closed_at, p.rejection_params = Status.REJECTED.value, None, t, p.params
        p.save(update_fields=["status", "deadline_at", "closed_at", "rejection_params"])
        return
    _to_sanction(p, t)


def _to_sanction(p: Proposal, t: int) -> None:
    president = authority.president()
    p.status, p.president_id = Status.SANCTION.value, president
    p.deadline_at = t + params.SANCTION_SECONDS if president is not None else None     # sem Presidente o prazo só corre quando houver um (L7)
    p.save(update_fields=["status", "president_id", "deadline_at"])


def _auto_sanction(p: Proposal, t: int) -> None:
    force_at = calendar.monday_after(t)
    p.status, p.decided_by_id, p.decided_at, p.force_at, p.deadline_at = Status.AWAITING_FORCE.value, None, t, force_at, force_at
    p.save(update_fields=["status", "decided_by_id", "decided_at", "force_at", "deadline_at"])
    event(p, EventKind.AUTO_SANCTIONED, t, None, force_at=force_at, president=p.president_id)


def _close_override(p: Proposal, t: int) -> None:
    result = _close_round(p, t)
    event(p, EventKind.OVERRIDE_CLOSED, t, None, **result)
    if result["approved"]:
        force_at = calendar.monday_after(t)                 # o veto derrubado NÃO volta ao Presidente (07 §07.15)
        p.status, p.force_at, p.deadline_at = Status.AWAITING_FORCE.value, force_at, force_at
        p.save(update_fields=["status", "force_at", "deadline_at"])
    else:
        p.status, p.deadline_at, p.closed_at = Status.VETO_SUSTAINED.value, None, t
        p.save(update_fields=["status", "deadline_at", "closed_at"])


def _enter_force(p: Proposal, t: int) -> None:
    old = Law.objects.select_for_update().filter(key=p.law_key).first()
    spec = catalog.get(p.law_key)
    before = None if old is None or old.status != LawStatus.IN_FORCE.value else dict(old.params)
    if before is None and spec is not None and p.kind == Kind.CHANGE.value:
        before = spec.defaults()
    if p.kind == Kind.REVOKE.value:
        old.status, old.revoked_at, old.proposal = LawStatus.REVOKED.value, t, p
        old.save(update_fields=["status", "revoked_at", "proposal"])
        new = None
    else:
        new = dict(p.params)
        if old is None:
            Law.objects.create(key=p.law_key, status=LawStatus.IN_FORCE.value, params=new, in_force_since=t, proposal=p)
        else:
            old.status, old.params, old.in_force_since, old.revoked_at, old.proposal = LawStatus.IN_FORCE.value, new, t, None, p
            old.save(update_fields=["status", "params", "in_force_since", "revoked_at", "proposal"])
    LawChange.objects.create(law_key=p.law_key, proposal=p, kind=p.kind, at=t, old_params=before, new_params=new)
    p.status, p.deadline_at, p.closed_at = Status.ENACTED.value, None, t
    p.save(update_fields=["status", "deadline_at", "closed_at"])
    event(p, EventKind.IN_FORCE, t, None, law=p.law_key, kind=p.kind, old_params=before, new_params=new)


# --- interregno e Presidente ------------------------------------------------------------------------------------------------------------------
def _resume(state: LegislativeState, at: int) -> int:
    since = state.interregnum_since
    duration = at - since
    n = 0
    Interregnum.objects.filter(ended_at__isnull=True).update(ended_at=at)
    state.interregnum_since = None
    for p in Proposal.objects.select_for_update().filter(status__in=[s.value for s in ACTIVE]).order_by("pk"):
        status = Status(p.status)
        if status is Status.DISCUSSION:
            shift = at - max(since, p.created_at)
            p.discussion_ends_at += shift
            p.deadline_at = calendar.monday_at_or_after(p.discussion_ends_at)
            p.save(update_fields=["discussion_ends_at", "deadline_at"])
            event(p, EventKind.DEADLINES_SHIFTED, at, None, seconds=shift, discussion_ends_at=p.discussion_ends_at)
            n += 1
        elif status in (Status.VOTING, Status.SANCTION, Status.VETOED, Status.OVERRIDE_VOTING):
            _return_to_vote(p, at, f"interregnum:{duration}")
            n += 1
    return n


def _return_to_vote(p: Proposal, at: int, reason: str) -> None:
    """Anula a votação aberta (se houver) e abre uma nova votação COMPLETA da Câmara (07 §07.18-§07.19); nada é aproveitado."""
    for rnd in p.rounds.select_for_update().filter(status=RoundStatus.OPEN.value):
        rnd.status, rnd.closed_at, rnd.void_reason = RoundStatus.VOIDED.value, at, reason
        rnd.save(update_fields=["status", "closed_at", "void_reason"])
        event(p, EventKind.VOTE_VOIDED, at, None, round=rnd.number, reason=reason)
    event(p, EventKind.RETURNED_TO_VOTE, at, None, from_status=p.status, reason=reason)
    _open_vote(p, at, RoundKind.MAIN, EventKind.VOTE_OPENED, reason=reason)


def _president_checks(at: int) -> int:
    n = 0
    president = authority.president()
    for p in Proposal.objects.select_for_update().filter(status=Status.SANCTION.value).order_by("pk"):
        if p.president_id is None and president is not None:
            p.president_id, p.deadline_at = president, at + params.SANCTION_SECONDS
            p.save(update_fields=["president_id", "deadline_at"])
            n += 1
        elif p.president_id is not None and president != p.president_id:
            _return_to_vote(p, at, "president_changed" if president is not None else "president_vacant")
            n += 1
    return n
