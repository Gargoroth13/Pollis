"""
Ponte para o Histórico do Mundo (design/12 §12.6, §12.14): aprovação pela Câmara, veto, derrubada de veto e entrada em vigor geram notícia
quando — e somente quando — a lei está marcada como `newsworthy` NO CATÁLOGO. O processo legislativo não julga importância.
Rejeição, retirada, veto mantido e sanção (do Presidente ou automática) não estão na lista do design e não geram notícia.
"""
from __future__ import annotations

from typing import Any, Dict

from . import catalog
from .constants import EventKind
from .models import Proposal

_EVENTS = {EventKind.VOTE_CLOSED: "approved", EventKind.VETOED: "vetoed", EventKind.OVERRIDE_CLOSED: "overridden", EventKind.IN_FORCE: "in_force"}


def on_event(proposal: Proposal, ev: EventKind, at: int, data: Dict[str, Any]) -> None:
    news_event = _EVENTS.get(ev)
    if news_event is None:
        return
    spec = catalog.get(proposal.law_key)
    if spec is None or not spec.newsworthy:
        return
    tally = None
    if ev in (EventKind.VOTE_CLOSED, EventKind.OVERRIDE_CLOSED):
        if not data.get("approved"):
            return                                   # votação reprovada: sem notícia (12.6 lista só aprovação e derrubada)
        tally = {k: data[k] for k in ("yes", "seats", "required_yes")}
    from history import news                          # import tardio: o 12 não importa o 07 (o acoplamento é só nesta direção)
    news.law_event(news_event, proposal.pk, proposal.round_no, spec.key, spec.name, proposal.kind, at, tally=tally,
                   new_params=data.get("new_params") if ev is EventKind.IN_FORCE else None)
