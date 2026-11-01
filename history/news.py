"""
API dos sistemas de origem (design/12 §12.2, §12.14): cada sistema CHAMA a função do seu acontecimento; o 12 não descobre nada sozinho.

Callers hoje: Empresas (`company_founded`) e Leis (`law_event`, via `legislation.news`). Sem caller ainda, por falta do sistema de origem
(documentado em design/12a): falência (não há falência de empresa no código nem no design 02), eleições e mudança de governo (06, REVIEW,
P1.11), conflitos (19, REVIEW). As funções existem e são testadas para que esses sistemas só precisem chamá-las.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from . import params, texts
from .constants import SERVER_NAME, Category, Office, Priority, RefKind, Status
from .publish import Published, publish


def _positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} inválido: {value!r}")
    return value


# --- empresas (12.5) -----------------------------------------------------------------------------------------------------------------------
def company_founded(company_id: int, name: str, company_type: str, at: int) -> Published:
    """Marco "primeira empresa de cada tipo" (12.5, 12.8): registrado UMA vez por tipo, mesmo sob fundações simultâneas (restrição única)."""
    phrase = texts.COMPANY_TYPE_PHRASE.get(company_type)
    if phrase is None:
        raise ValueError(f"tipo de empresa sem texto de marco: {company_type!r}")
    return publish("milestone.first_company", {"company": name, "type_phrase": phrase}, category=Category.MILESTONE, priority=Priority.MILESTONE, at=at,
                   ref=(RefKind.COMPANY, company_id), dedupe_key=f"milestone:first_company:{company_type}",
                   structured={"company": company_id, "name": name, "type": company_type})


def company_bankrupt(company_id: int, name: str, stars: int, at: int) -> Published:
    """Falência: só empresas de `BANKRUPTCY_MIN_STARS`★ ou mais geram notícia global (12.5, 12.12). O texto não inventa motivo."""
    _positive_int(stars, "stars")
    if stars < params.BANKRUPTCY_MIN_STARS:
        return Published(Status.NOT_NEWSWORTHY, None, "below_min_stars")
    return publish("company.bankruptcy", {"company": name, "stars": stars}, category=Category.ECONOMY, priority=Priority.BANKRUPTCY, at=at,
                   ref=(RefKind.COMPANY, company_id), dedupe_key=f"bankruptcy:{company_id}", structured={"company": company_id, "name": name, "stars": stars})


# --- política (12.6) -----------------------------------------------------------------------------------------------------------------------
def election_pct(votes: int, total_votes: int) -> Decimal:
    """Porcentagem REAL de votos do vencedor (12.6), exata (6 casas); o texto arredonda a 1 casa."""
    _positive_int(votes, "votes")
    _positive_int(total_votes, "total_votes")
    if total_votes == 0 or votes > total_votes:
        raise ValueError(f"votos inconsistentes: {votes}/{total_votes}")
    return (Decimal(votes) * 100 / Decimal(total_votes)).quantize(Decimal("0.000001"))


def election_concluded(office: Office, election_id: Any, winner_name: str, votes: int, total_votes: int, at: int,
                       jurisdiction: Optional[str] = None) -> Published:
    """Resultado de eleição de cargo único (Presidente, Governador, Prefeito) + marco da primeira eleição do cargo (12.8). Devolve o resultado."""
    if office is Office.CHAMBER:
        raise ValueError("a Câmara tem `chamber_elected`")
    pct = election_pct(votes, total_votes)
    where = f" em {jurisdiction}" if jurisdiction else ""
    result = publish("politics.election_winner", {"office": texts.OFFICE_NAME[office.value], "winner": winner_name, "pct": texts.fmt_pct(pct), "where": where},
                     category=Category.POLITICS, priority=Priority.ELECTION, at=at, ref=(RefKind.OFFICE, f"{office.value}:{election_id}"),
                     dedupe_key=f"election:{office.value}:{election_id}",
                     structured={"office": office.value, "election": str(election_id), "winner": winner_name, "votes": votes, "total_votes": total_votes,
                                 "pct": pct, "jurisdiction": jurisdiction})
    _first_election(office, election_id, at)
    return result


def chamber_elected(election_id: Any, seats: int, at: int) -> Published:
    seats = _positive_int(seats, "seats")
    result = publish("politics.chamber_elected", {"seats": seats}, category=Category.POLITICS, priority=Priority.ELECTION, at=at,
                     ref=(RefKind.OFFICE, f"chamber:{election_id}"), dedupe_key=f"election:chamber:{election_id}",
                     structured={"office": "chamber", "election": str(election_id), "seats": seats})
    _first_election(Office.CHAMBER, election_id, at)
    return result


def _first_election(office: Office, election_id: Any, at: int) -> Published:
    return publish("milestone.first_election", {"office_phrase": texts.ELECTION_PHRASE[office.value]}, category=Category.MILESTONE,
                   priority=Priority.MILESTONE, at=at, ref=(RefKind.OFFICE, f"{office.value}:{election_id}"),
                   dedupe_key=f"milestone:first_election:{office.value}", structured={"office": office.value, "election": str(election_id)})


def government_change(event_id: Any, deposed_name: str, new_name: str, at: int) -> Published:
    """Deposição presidencial: a notícia de maior prioridade (12.13, item 1)."""
    return publish("politics.government_change", {"deposed": deposed_name, "new": new_name}, category=Category.POLITICS, priority=Priority.GOVERNMENT_CHANGE,
                   at=at, ref=(RefKind.OFFICE, f"president:{event_id}"), dedupe_key=f"government_change:{event_id}",
                   structured={"event": str(event_id), "deposed": deposed_name, "new": new_name})


# --- conflitos (12.7): só início e resultado; movimentação individual de membros NÃO tem função aqui ----------------------------------
def conflict_started(action_id: Any, faction: str, target: str, at: int) -> Published:
    return publish("conflict.started", {"faction": faction, "target": target}, category=Category.CONFLICT, priority=Priority.CONFLICT, at=at,
                   ref=(RefKind.ACTION, action_id), dedupe_key=f"conflict:{action_id}:started", structured={"action": str(action_id), "faction": faction, "target": target})


def conflict_result(action_id: Any, faction: str, target: str, won: bool, at: int) -> Published:
    return publish("conflict.won" if won else "conflict.lost", {"faction": faction, "target": target}, category=Category.CONFLICT, priority=Priority.CONFLICT,
                   at=at, ref=(RefKind.ACTION, action_id), dedupe_key=f"conflict:{action_id}:result",
                   structured={"action": str(action_id), "faction": faction, "target": target, "won": bool(won)})


# --- leis (12.6, 12.14) ----------------------------------------------------------------------------------------------------------------------
LAW_EVENTS = ("approved", "vetoed", "overridden", "in_force")


def law_event(event: str, proposal_id: int, round_no: int, law_key: str, law_name: str, change_kind: str, at: int, tally: Optional[dict] = None,
              new_params: Optional[dict] = None) -> Published:
    """Aprovação, veto, derrubada de veto e entrada em vigor de uma lei marcada como noticiável NO CATÁLOGO (12.6: o 12 não julga importância)."""
    if event not in LAW_EVENTS:
        raise ValueError(f"evento de lei desconhecido: {event!r}")
    revoke = change_kind == "revoke"
    fields = {"law": law_name, "what": "revogação de" if revoke else "alteração em", "what_short": "revogação" if revoke else "alteração",
              "what_the": "a revogação" if revoke else "a alteração"}
    if tally is not None:
        fields.update(yes=tally["yes"], seats=tally["seats"], required=tally["required_yes"])
    if event == "in_force":
        fields["in_force_text"] = "A lei foi revogada e deixa de valer." if revoke else "A mudança aprovada pela Câmara passa a valer a partir de agora."
    template = {"approved": "politics.law_approved", "vetoed": "politics.law_vetoed", "overridden": "politics.veto_overridden",
                "in_force": "politics.law_in_force"}[event]
    return publish(template, fields, category=Category.POLITICS, priority=params.LAW_PRIORITY, at=at, ref=(RefKind.LAW, law_key),
                   dedupe_key=f"law:{proposal_id}:{event}:{round_no}",
                   structured={"event": event, "proposal": proposal_id, "round": round_no, "law": law_key, "kind": change_kind, "tally": tally,
                               "new_params": new_params})
