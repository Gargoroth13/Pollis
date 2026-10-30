"""Consultas públicas (design/07 §07.26): proposta, versões, votos nominais, decisão do Presidente, histórico e situação da lei. Só LÊ."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import calendar, laws, preview
from .constants import Status
from .models import Law, LawChange, Proposal, Suggestion
from .voting import last_choices, tally


def _round_view(rnd) -> Dict[str, Any]:
    choices = last_choices(rnd)
    return {"number": rnd.number, "kind": rnd.kind, "status": rnd.status, "started_at": rnd.started_at, "ends_at": rnd.ends_at, "closed_at": rnd.closed_at,
            "seats": rnd.seats_count, "composition": list(rnd.seats), "approved": rnd.approved, "void_reason": rnd.void_reason,
            "tally": rnd.tally if rnd.tally is not None else tally(rnd),
            "votes": {str(d): c for d, c in sorted(choices.items())},                                        # voto nominal e público
            "vote_history": [{"deputy": r.deputy_id, "choice": r.choice, "at": r.at} for r in rnd.records.order_by("id")]}


def proposal_view(proposal_id: int) -> Optional[Dict[str, Any]]:
    p = Proposal.objects.filter(pk=proposal_id).first()
    if p is None:
        return None
    return {"proposal": p.pk, "law": p.law_key, "kind": p.kind, "status": p.status, "author": p.author_id, "params": p.params, "description": p.description,
            "version": p.version, "created_at": p.created_at, "discussion_ends_at": p.discussion_ends_at, "next_deadline_at": p.deadline_at,
            "president": p.president_id, "decided_by": p.decided_by_id, "decided_at": p.decided_at, "automatic_sanction": p.status in
            (Status.AWAITING_FORCE.value, Status.ENACTED.value) and p.decided_at is not None and p.decided_by_id is None,
            "veto_justification": p.veto_justification, "force_at": p.force_at, "closed_at": p.closed_at,
            "versions": [{"number": v.number, "params": v.params, "description": v.description, "at": v.at, "by": v.by_id} for v in p.versions.all()],
            "rounds": [_round_view(r) for r in p.rounds.all()],
            "events": [{"kind": e.kind, "at": e.at, "actor": e.actor_id, "data": e.data} for e in p.events.all()],
            "preview": preview.proposal_preview(p)}


def list_proposals(status: Optional[str] = None, law: Optional[str] = None) -> List[Dict[str, Any]]:
    qs = Proposal.objects.all()
    if status:
        qs = qs.filter(status=status)
    if law:
        qs = qs.filter(law_key=law)
    return [{"proposal": p.pk, "law": p.law_key, "status": p.status, "author": p.author_id, "version": p.version, "next_deadline_at": p.deadline_at}
            for p in qs.order_by("pk")]


def law_view(key: str) -> Optional[Dict[str, Any]]:
    current = laws.current_values(key)
    if current is None:
        return None
    law = Law.objects.filter(key=key).first()
    return {"law": key, "in_force": laws.in_force(key), "params": current, "in_force_since": law.in_force_since if law else None,
            "revoked_at": law.revoked_at if law else None, "history": [{"proposal": c.proposal_id, "kind": c.kind, "at": c.at, "old": c.old_params,
                                                                           "new": c.new_params} for c in LawChange.objects.filter(law_key=key)]}


def calendar_view(now: int) -> Dict[str, Any]:
    return {"next_weekly_tick": calendar.monday_after(now)}


def suggestions_view() -> List[Dict[str, Any]]:
    return [{"suggestion": s.pk, "author": s.author_id, "law": s.law_key, "kind": s.kind, "params": s.params, "status": s.status, "proposal": s.proposal_id}
            for s in Suggestion.objects.order_by("pk")]
