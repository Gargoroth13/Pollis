"""
Votação da Câmara, sanção e veto (design/07 §07.7-§07.10, §07.12-§07.15).

Quem decide o QUÊ e QUANDO vive em `process.py` (prazos); aqui estão as ações dos atores e a apuração. Uma ação é recusada se o prazo
registrado já passou, mesmo que o motor ainda não tenha processado a transição (o prazo, não o instante do processamento, é a verdade).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from django.db import transaction

from core import clock as game_clock
from players.services import ActionResult

from . import authority, calendar, params
from .common import event, is_int, keys_refusal, player_exists, refuse
from .constants import OPEN_VOTE, Choice, EventKind, RoundKind, RoundStatus, Status
from .models import Proposal, VoteRecord, VoteRound

VOTE_KEYS = frozenset({"proposal", "choice"})
SANCTION_KEYS = frozenset({"proposal"})
VETO_KEYS = frozenset({"proposal"})
VETO_OPTIONAL = frozenset({"justification"})


# --- apuração ---------------------------------------------------------------------------------------------------------------------------------
def required_votes(kind: RoundKind, seats: int) -> int:
    """Votos favoráveis mínimos sobre TODAS as cadeiras consideradas (07 §07.9, §07.15)."""
    if kind is RoundKind.MAIN:
        return seats // 2 + 1                                                    # mais da metade das cadeiras
    num, den = params.OVERRIDE_NUMERATOR, params.OVERRIDE_DENOMINATOR
    return -(-num * seats // den)                                                # teto de 2/3 das cadeiras


def last_choices(round_: VoteRound) -> Dict[int, str]:
    """Último voto de cada Deputado da composição congelada (votos de quem não tem cadeira na votação nunca são aceitos nem contados)."""
    seats = set(round_.seats)
    out: Dict[int, str] = {}
    for rec in round_.records.order_by("id"):
        if rec.deputy_id in seats:
            out[rec.deputy_id] = rec.choice
    return out


def tally(round_: VoteRound) -> Dict[str, Any]:
    """Resultado estruturado da votação (20): contagens, exigido, regra e se foi alcançado. Ausência não é voto favorável (07 §07.8)."""
    kind = RoundKind(round_.kind)
    choices = last_choices(round_)
    yes = sum(1 for c in choices.values() if c == Choice.YES.value)
    no = sum(1 for c in choices.values() if c == Choice.NO.value)
    abstain = sum(1 for c in choices.values() if c == Choice.ABSTAIN.value)
    required = required_votes(kind, round_.seats_count)
    return {"kind": kind.value, "seats": round_.seats_count, "yes": yes, "no": no, "abstain": abstain, "absent": round_.seats_count - len(choices),
            "required_yes": required, "rule": "absolute_majority_of_all_seats" if kind is RoundKind.MAIN else "two_thirds_of_all_seats",
            "approved": yes >= required}


def open_round(proposal: Proposal, kind: RoundKind, start: int, seats: list, ends_at: int) -> VoteRound:
    proposal.round_no += 1
    return VoteRound.objects.create(proposal=proposal, number=proposal.round_no, kind=kind.value, seats=list(seats), seats_count=len(seats),
                                    started_at=start, ends_at=ends_at)


# --- voto ---------------------------------------------------------------------------------------------------------------------------------------
def cast_refusal(actor_id: Any, target: Any, *, proposal: Optional[Proposal] = None, round_: Optional[VoteRound] = None) -> Optional[ActionResult]:
    bad = keys_refusal(target, VOTE_KEYS)
    if bad is not None:
        return bad
    if not player_exists(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    try:
        choice = Choice(target["choice"])
    except ValueError:
        return refuse("INVALID_CHOICE", allowed=[c.value for c in Choice])
    del choice
    if proposal is None and is_int(target["proposal"]):
        proposal = Proposal.objects.filter(pk=target["proposal"]).first()
    if proposal is None:
        return refuse("PROPOSAL_NOT_FOUND")
    if proposal.status not in {s.value for s in OPEN_VOTE}:
        return refuse("NOT_VOTING", proposal=proposal.pk, status=proposal.status)
    round_ = round_ or proposal.rounds.filter(status=RoundStatus.OPEN.value).first()
    if round_ is None:
        return refuse("NOT_VOTING", proposal=proposal.pk, status=proposal.status)
    now = game_clock.now()
    if now >= round_.ends_at:
        return refuse("VOTE_CLOSED", proposal=proposal.pk, ended_at=round_.ends_at)
    if actor_id not in set(round_.seats):
        return refuse("NOT_A_VOTER", proposal=proposal.pk)           # fora da composição congelada (07 §07.7)
    try:
        if actor_id not in authority.deputies():
            return refuse("NOT_A_DEPUTY", proposal=proposal.pk)      # perdeu a cadeira: não age como Deputado
    except authority.ProviderConflict as exc:
        return refuse("OFFICE_CONFLICT", detail=str(exc)[:120])
    return None


def cast_vote(actor_id: Any, target: Any) -> ActionResult:
    """Voto nominal e público; o Deputado pode mudar o voto enquanto a votação estiver aberta (cada mudança é um registro novo)."""
    with transaction.atomic():
        proposal = None
        if isinstance(target, dict) and is_int(target.get("proposal")):
            proposal = Proposal.objects.select_for_update().filter(pk=target["proposal"]).first()
        refusal = cast_refusal(actor_id, target, proposal=proposal)
        if refusal is not None:
            return refusal
        round_ = proposal.rounds.get(status=RoundStatus.OPEN.value)
        now = game_clock.now()
        rec = VoteRecord.objects.create(round=round_, deputy_id=actor_id, choice=target["choice"], at=now)
        return ActionResult(True, "OK", {"proposal": proposal.pk, "round": round_.number, "choice": rec.choice, "record": rec.pk})


# --- sanção e veto ------------------------------------------------------------------------------------------------------------------------------
def _decision_refusal(actor_id: Any, proposal: Optional[Proposal], now: int) -> Optional[ActionResult]:
    if not player_exists(actor_id):
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:30])
    if proposal is None:
        return refuse("PROPOSAL_NOT_FOUND")
    if proposal.status != Status.SANCTION.value:
        return refuse("NOT_AWAITING_SANCTION", proposal=proposal.pk, status=proposal.status)
    try:
        president = authority.president()
    except authority.ProviderConflict as exc:
        return refuse("OFFICE_CONFLICT", detail=str(exc)[:120])
    if president is None or president != actor_id:
        return refuse("NOT_PRESIDENT", proposal=proposal.pk)
    if proposal.president_id is not None and proposal.president_id != actor_id:
        return refuse("NOT_PRESIDENT", proposal=proposal.pk)         # a proposta voltará à Câmara (07 §07.18)
    if proposal.deadline_at is not None and now >= proposal.deadline_at:
        return refuse("SANCTION_DEADLINE_PASSED", proposal=proposal.pk, deadline=proposal.deadline_at)
    return None


def _lock(target: Any) -> Optional[Proposal]:
    if isinstance(target, dict) and is_int(target.get("proposal")):
        return Proposal.objects.select_for_update().filter(pk=target["proposal"]).first()
    return None


def sanction_refusal(actor_id: Any, target: Any, *, proposal: Optional[Proposal] = None) -> Optional[ActionResult]:
    bad = keys_refusal(target, SANCTION_KEYS)
    if bad is not None:
        return bad
    proposal = proposal or (Proposal.objects.filter(pk=target["proposal"]).first() if is_int(target["proposal"]) else None)
    return _decision_refusal(actor_id, proposal, game_clock.now())


def sanction(actor_id: Any, target: Any) -> ActionResult:
    with transaction.atomic():
        proposal = _lock(target)
        refusal = sanction_refusal(actor_id, target, proposal=proposal)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        force_at = calendar.monday_after(now)
        proposal.status, proposal.president_id, proposal.decided_by_id, proposal.decided_at = Status.AWAITING_FORCE.value, actor_id, actor_id, now
        proposal.force_at, proposal.deadline_at = force_at, force_at
        proposal.save(update_fields=["status", "president_id", "decided_by_id", "decided_at", "force_at", "deadline_at"])
        event(proposal, EventKind.SANCTIONED, now, actor_id, force_at=force_at)
        return ActionResult(True, "OK", {"proposal": proposal.pk, "force_at": force_at})


def veto_refusal(actor_id: Any, target: Any, *, proposal: Optional[Proposal] = None) -> Optional[ActionResult]:
    bad = keys_refusal(target, VETO_KEYS, VETO_OPTIONAL)
    if bad is not None:
        return bad
    just = target.get("justification", "")
    if not isinstance(just, str) or len(just) > params.JUSTIFICATION_MAX:
        return refuse("INVALID_JUSTIFICATION", maximum=params.JUSTIFICATION_MAX)
    proposal = proposal or (Proposal.objects.filter(pk=target["proposal"]).first() if is_int(target["proposal"]) else None)
    return _decision_refusal(actor_id, proposal, game_clock.now())


def veto(actor_id: Any, target: Any) -> ActionResult:
    """O veto registra responsável, instante e justificativa (quando fornecida); a Câmara pode derrubá-lo na próxima janela semanal (07 §07.14-§07.15)."""
    with transaction.atomic():
        proposal = _lock(target)
        refusal = veto_refusal(actor_id, target, proposal=proposal)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        window = calendar.monday_after(now)
        proposal.status, proposal.president_id, proposal.decided_by_id, proposal.decided_at = Status.VETOED.value, actor_id, actor_id, now
        proposal.veto_justification, proposal.deadline_at = target.get("justification", ""), window
        proposal.save(update_fields=["status", "president_id", "decided_by_id", "decided_at", "veto_justification", "deadline_at"])
        event(proposal, EventKind.VETOED, now, actor_id, justification=proposal.veto_justification, override_window=window)
        return ActionResult(True, "OK", {"proposal": proposal.pk, "override_window": window})
