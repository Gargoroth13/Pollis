"""
Auditoria do processo legislativo (design/07 §07.25-§07.26). Só LÊ. Invariantes (numeração própria deste app):
  1  versões: numeradas de 1 até a versão atual; a última confere com os parâmetros e a descrição da proposta; a 1ª é do autor
  2  estado × campos: votação aberta ⇔ estado de votação (principal/derrubada) com prazo = fim da votação; sanção sem Presidente não tem prazo;
     aguardando vigor tem `force_at` = prazo, num weekly tick, depois da decisão; estados terminais não têm prazo e têm encerramento
  3  votações: composição = nº de cadeiras; só votam cadeiras da composição congelada, dentro da janela; votação fechada confere com o placar guardado
     (contagem, exigido, aprovação); anulada tem motivo
  4  fluxo: cada estado é coerente com as votações anteriores (rejeitada ⇒ última principal reprovada; sanção/vigor ⇒ aprovada; veto mantido ⇒ derrubada reprovada)
  5  conflito: no máximo uma proposta ativa por escopo (também restrição no banco); o escopo tem a forma esperada
  6  leis: a lei vigente = última mudança registrada; cada proposta em vigor tem UMA mudança no instante `force_at`; revogada ⇔ última mudança é revogação
  7  histórico: eventos em ordem de instante; o primeiro é a criação
"""
from __future__ import annotations

from collections import defaultdict

from ledger.audit import AuditReport

from . import calendar
from .constants import ACTIVE, TERMINAL, Kind, LawStatus, RoundKind, RoundStatus, Status
from .models import Law, LawChange, Proposal, VoteRound
from .voting import tally


def audit_legislation() -> AuditReport:
    report = AuditReport()
    proposals = list(Proposal.objects.order_by("pk"))
    rounds = defaultdict(list)
    for r in VoteRound.objects.order_by("proposal_id", "number"):
        rounds[r.proposal_id].append(r)
    for p in proposals:
        _versions(report, p)
        _state(report, p, rounds[p.pk])
        _rounds(report, p, rounds[p.pk])
        _flow(report, p, rounds[p.pk])
        _events(report, p)
    _conflicts(report, proposals)
    _laws(report, proposals)
    report.stats.update(proposals=len(proposals), rounds=sum(len(v) for v in rounds.values()))
    return report


def _versions(report, p):
    versions = list(p.versions.order_by("number"))
    if [v.number for v in versions] != list(range(1, p.version + 1)):
        report.add(1, "VERSIONS_NOT_CONTIGUOUS", proposal=p.pk, have=[v.number for v in versions], expected_last=p.version)
        return
    last = versions[-1]
    if last.params != p.params or last.description != p.description:
        report.add(1, "LAST_VERSION_MISMATCH", proposal=p.pk)
    if versions[0].by_id != p.author_id:
        report.add(1, "FIRST_VERSION_NOT_BY_AUTHOR", proposal=p.pk)


def _state(report, p, rnds):
    st = Status(p.status)
    open_rounds = [r for r in rnds if r.status == RoundStatus.OPEN.value]
    voting = st in (Status.VOTING, Status.OVERRIDE_VOTING)
    if voting != (len(open_rounds) == 1) or len(open_rounds) > 1:
        report.add(2, "OPEN_ROUND_MISMATCH", proposal=p.pk, status=p.status, open_rounds=len(open_rounds))
    elif voting:
        want = RoundKind.MAIN.value if st is Status.VOTING else RoundKind.OVERRIDE.value
        if open_rounds[0].kind != want or p.deadline_at != open_rounds[0].ends_at:
            report.add(2, "OPEN_ROUND_KIND_OR_DEADLINE", proposal=p.pk, kind=open_rounds[0].kind, deadline=p.deadline_at, ends_at=open_rounds[0].ends_at)
    if st is Status.SANCTION and p.president_id is None and p.deadline_at is not None:
        report.add(2, "SANCTION_WITHOUT_PRESIDENT_HAS_DEADLINE", proposal=p.pk)
    if st is Status.AWAITING_FORCE:
        if p.force_at is None or p.force_at != p.deadline_at or not calendar.is_weekly_tick(p.force_at):
            report.add(2, "FORCE_AT_INVALID", proposal=p.pk, force_at=p.force_at, deadline=p.deadline_at)
        elif p.decided_at is not None and p.force_at <= p.decided_at:
            report.add(2, "FORCE_BEFORE_DECISION", proposal=p.pk)
    if st in TERMINAL and (p.deadline_at is not None or p.closed_at is None):
        report.add(2, "TERMINAL_STATE_FIELDS", proposal=p.pk, status=p.status)
    if st in ACTIVE and p.closed_at is not None:
        report.add(2, "ACTIVE_STATE_HAS_CLOSED_AT", proposal=p.pk)
    if st is Status.DISCUSSION and p.deadline_at is not None and p.deadline_at < p.discussion_ends_at:
        report.add(2, "WINDOW_BEFORE_DISCUSSION_END", proposal=p.pk)


def _rounds(report, p, rnds):
    for r in rnds:
        if r.seats_count != len(r.seats) or len(set(r.seats)) != len(r.seats):
            report.add(3, "SEATS_MISMATCH", proposal=p.pk, round=r.number)
        seats = set(r.seats)
        for rec in r.records.all():
            if rec.deputy_id not in seats:
                report.add(3, "VOTE_OUTSIDE_COMPOSITION", proposal=p.pk, round=r.number, deputy=rec.deputy_id)
            if not r.started_at <= rec.at < r.ends_at:
                report.add(3, "VOTE_OUTSIDE_WINDOW", proposal=p.pk, round=r.number, deputy=rec.deputy_id, at=rec.at)
        if r.status == RoundStatus.CLOSED.value:
            expected = tally(r)
            if r.tally is None or any(r.tally.get(k) != expected[k] for k in ("yes", "no", "abstain", "absent", "required_yes", "approved", "seats")):
                report.add(3, "TALLY_MISMATCH", proposal=p.pk, round=r.number, stored=r.tally, expected=expected)
            if r.approved != expected["approved"]:
                report.add(3, "APPROVAL_MISMATCH", proposal=p.pk, round=r.number)
        elif r.status == RoundStatus.VOIDED.value and not r.void_reason:
            report.add(3, "VOID_WITHOUT_REASON", proposal=p.pk, round=r.number)


def _flow(report, p, rnds):
    closed = [r for r in rnds if r.status == RoundStatus.CLOSED.value]
    mains = [r for r in closed if r.kind == RoundKind.MAIN.value]
    overrides = [r for r in closed if r.kind == RoundKind.OVERRIDE.value]
    st = Status(p.status)
    if st is Status.REJECTED and not (mains and mains[-1].approved is False):
        report.add(4, "REJECTED_WITHOUT_FAILED_VOTE", proposal=p.pk)
    if st in (Status.SANCTION, Status.VETOED, Status.OVERRIDE_VOTING, Status.AWAITING_FORCE, Status.ENACTED, Status.VETO_SUSTAINED) \
            and not (mains and mains[-1].approved is True):
        report.add(4, "STAGE_WITHOUT_APPROVED_VOTE", proposal=p.pk, status=p.status)
    if st is Status.VETO_SUSTAINED and not (overrides and overrides[-1].approved is False):
        report.add(4, "VETO_SUSTAINED_WITHOUT_FAILED_OVERRIDE", proposal=p.pk)
    if st in (Status.VETOED, Status.OVERRIDE_VOTING, Status.VETO_SUSTAINED) and p.decided_by_id is None:
        report.add(4, "VETO_WITHOUT_RESPONSIBLE", proposal=p.pk)
    if st in (Status.AWAITING_FORCE, Status.ENACTED) and p.decided_at is None and not (overrides and overrides[-1].approved):
        report.add(4, "FORCE_WITHOUT_DECISION", proposal=p.pk)
    if st is Status.DISCUSSION and closed:
        report.add(4, "DISCUSSION_WITH_CLOSED_ROUNDS", proposal=p.pk)


def _conflicts(report, proposals):
    seen = {}
    for p in proposals:
        if p.status in {s.value for s in ACTIVE}:
            if p.scope in seen:
                report.add(5, "TWO_ACTIVE_PROPOSALS_IN_SCOPE", scope=p.scope, proposals=[seen[p.scope], p.pk])
            seen[p.scope] = p.pk
        if not (p.scope == f"law:{p.law_key}" or p.scope.startswith("group:")):
            report.add(5, "BAD_SCOPE", proposal=p.pk, scope=p.scope)


def _laws(report, proposals):
    changes = defaultdict(list)
    for c in LawChange.objects.order_by("id"):
        changes[c.law_key].append(c)
    enacted = {p.pk: p for p in proposals if p.status == Status.ENACTED.value}
    by_proposal = defaultdict(list)
    for key, lst in changes.items():
        for c in lst:
            by_proposal[c.proposal_id].append(c)
        if [c.at for c in lst] != sorted(c.at for c in lst):
            report.add(6, "LAW_CHANGES_OUT_OF_ORDER", law=key)
    for pid, p in enacted.items():
        got = by_proposal.get(pid, [])
        if len(got) != 1 or got[0].at != p.force_at or got[0].kind != p.kind:
            report.add(6, "ENACTED_PROPOSAL_CHANGE_MISMATCH", proposal=pid, changes=len(got))
    for pid in by_proposal:
        if pid not in enacted:
            report.add(6, "CHANGE_WITHOUT_ENACTED_PROPOSAL", proposal=pid)
    for law in Law.objects.all():
        lst = changes.get(law.key, [])
        if not lst:
            report.add(6, "LAW_WITHOUT_CHANGES", law=law.key)
            continue
        last = lst[-1]
        if law.status == LawStatus.IN_FORCE.value and (last.kind != Kind.CHANGE.value or last.new_params != law.params or law.revoked_at is not None):
            report.add(6, "LAW_STATE_MISMATCH", law=law.key)
        if law.status == LawStatus.REVOKED.value and (last.kind != Kind.REVOKE.value or law.revoked_at != last.at):
            report.add(6, "REVOKED_LAW_MISMATCH", law=law.key)
    for key in changes:
        if not Law.objects.filter(key=key).exists():
            report.add(6, "CHANGES_WITHOUT_LAW", law=key)


def _events(report, p):
    evs = list(p.events.order_by("id"))
    if not evs or evs[0].kind != "created":
        report.add(7, "FIRST_EVENT_NOT_CREATION", proposal=p.pk)
    if [e.at for e in evs] != sorted(e.at for e in evs):
        report.add(7, "EVENTS_OUT_OF_ORDER", proposal=p.pk)
