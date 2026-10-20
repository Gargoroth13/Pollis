"""
Auditoria das Empresas (design/02 §16-17; 24). Só LÊ. Invariantes (numeração própria deste app):
  1  toda empresa tem exatamente um cargo Dono ocupado (02 §16) e uma conta `COMPANY` no registro monetário
  2  a fundação tem o lançamento `COMPANY_FOUNDING` (fundador → União) com o valor cobrado; o valor cobrado é positivo
  3  cada aporte tem o lançamento `DONATION` (jogador → conta da empresa) com o mesmo valor, e o aporte vem do Dono
  4  cargos e vagas: status coerente com o ocupante; cargo permitido ao tipo da empresa; ocupante de vaga tem evento de contratação;
     vaga aberta tem evento de abertura; um só emprego contratado por jogador (o Dono não conta)
  5  candidaturas: pendente só em vaga ABERTA; aprovada tem o evento de contratação; eventos são imutáveis e ordenados no tempo
  6  salário de trabalho: cada `WorkWage` tem pedido de remuneração `WAGE` (pagador = conta da empresa, beneficiário = o jogador,
     devido = salário do cargo), reconhecido + descartado = devido, pago + pendente = reconhecido, pendente com obrigação aberta/
     paga do mesmo valor; sequência do jogador sem buracos nem repetição
  7  folha do Dono: exatamente UM pedido `OWNER_SALARY` por empresa e dia de tick diário depois da fundação (sem dia pulado nem
     pagamento duplicado), pago pela conta da empresa ao Dono pelo salário do cargo, sem pedido esquecido em `SUBMITTED`
"""
from __future__ import annotations

from collections import defaultdict

from core.models import WorldClock
from core.timeline import TickKind, ticks_between
from ledger import services as ledger
from ledger.audit import AuditReport
from ledger.constants import AccountKind, Nature, RequestStatus
from ledger.models import Account, Entry, Obligation, RemunerationRequest
from ledger.money import competence_day_of

from . import params
from .constants import ApplicationStatus, CompanyType, EventKind, PositionKind, PositionStatus
from .models import Application, CapitalContribution, Company, Position, PositionEvent, WorkWage


def audit_companies() -> AuditReport:
    report = AuditReport()
    union_id = ledger.union_account().pk
    companies = 0
    for c in Company.objects.order_by("id").iterator():
        companies += 1
        owners = list(Position.objects.filter(company=c, kind=PositionKind.OWNER.value))
        if len(owners) != 1 or owners[0].holder_id is None:
            report.add(1, "OWNER_POSITION_INVALID", company=c.pk, owners=len(owners))
        account = Account.objects.filter(kind=AccountKind.COMPANY.value, owner_id=c.pk).first()
        if account is None:
            report.add(1, "COMPANY_ACCOUNT_MISSING", company=c.pk)
        entry = Entry.objects.filter(transaction__key=c.founding_key, nature=Nature.COMPANY_FOUNDING.value).first()
        if entry is None:
            report.add(2, "FOUNDING_ENTRY_MISSING", company=c.pk)
        elif (entry.amount != c.founding_cost or entry.from_account.owner_id != c.founder_id
              or entry.from_account.kind != AccountKind.PLAYER.value or entry.to_account_id != union_id):
            report.add(2, "FOUNDING_ENTRY_MISMATCH", company=c.pk, cost=c.founding_cost, entry=entry.seq)
    contributions = 0
    for k in CapitalContribution.objects.select_related("company").order_by("id").iterator():
        contributions += 1
        entry = Entry.objects.filter(transaction__key=k.ledger_key, nature=Nature.DONATION.value).first()
        if entry is None:
            report.add(3, "CONTRIBUTION_ENTRY_MISSING", contribution=k.pk)
        elif (entry.amount != k.amount or entry.from_account.kind != AccountKind.PLAYER.value
              or entry.from_account.owner_id != k.player_id or entry.to_account.kind != AccountKind.COMPANY.value
              or entry.to_account.owner_id != k.company_id):
            report.add(3, "CONTRIBUTION_ENTRY_MISMATCH", contribution=k.pk, amount=k.amount, entry=entry.seq)
    _audit_positions(report)
    _audit_applications(report)
    _audit_work_wages(report)
    _audit_owner_payroll(report)
    report.stats.update({"companies": companies, "contributions": contributions,
                         "capital": sum(CapitalContribution.objects.values_list("amount", flat=True))})
    return report


def _events_by_position() -> dict:
    out = defaultdict(list)
    for e in PositionEvent.objects.order_by("id").iterator():
        out[e.position_id].append(e)
    return out


def _audit_positions(report: AuditReport) -> None:
    events = _events_by_position()
    jobs_by_player = defaultdict(int)
    for p in Position.objects.select_related("company").order_by("id").iterator():
        kinds = {e.kind for e in events.get(p.pk, ())}
        if (p.status == PositionStatus.FILLED.value) != (p.holder_id is not None):
            report.add(4, "POSITION_STATUS_HOLDER_MISMATCH", position=p.pk, status=p.status, holder=p.holder_id)
        if p.kind == PositionKind.OWNER.value:
            continue
        if PositionKind(p.kind) not in params.HIRABLE_KINDS[CompanyType(p.company.type)]:
            report.add(4, "POSITION_KIND_NOT_ALLOWED", position=p.pk, kind=p.kind, company_type=p.company.type)
        if EventKind.POSITION_OPENED.value not in kinds:
            report.add(4, "POSITION_WITHOUT_OPEN_EVENT", position=p.pk)
        if p.holder_id is not None:
            jobs_by_player[p.holder_id] += 1
            hired = [e for e in events.get(p.pk, ()) if e.kind == EventKind.HIRED.value]
            if not hired or hired[-1].subject != p.holder_id:
                report.add(4, "FILLED_POSITION_WITHOUT_HIRE_EVENT", position=p.pk, holder=p.holder_id)
        if p.status == PositionStatus.CLOSED.value and not (kinds & {EventKind.POSITION_CLOSED.value, EventKind.RESIGNED.value,
                                                                     EventKind.DISMISSED.value}):
            report.add(4, "CLOSED_POSITION_WITHOUT_CLOSE_EVENT", position=p.pk)
    for player_id, n in sorted(jobs_by_player.items()):
        if n > 1:
            report.add(4, "MORE_THAN_ONE_JOB", player=player_id, jobs=n)


def _audit_applications(report: AuditReport) -> None:
    events = _events_by_position()
    for a in Application.objects.select_related("position").order_by("id").iterator():
        if a.status == ApplicationStatus.PENDING.value and a.position.status != PositionStatus.OPEN.value:
            report.add(5, "PENDING_APPLICATION_ON_CLOSED_POSITION", application=a.pk, position=a.position_id)
        if a.status == ApplicationStatus.APPROVED.value and not any(
                e.kind == EventKind.HIRED.value and e.subject == a.applicant_id and e.explained.get("application") == a.pk
                for e in events.get(a.position_id, ())):
            report.add(5, "APPROVED_WITHOUT_HIRE_EVENT", application=a.pk)
    previous = None
    for e in PositionEvent.objects.order_by("id").iterator():
        if previous is not None and e.at < previous:
            report.add(5, "EVENT_OUT_OF_ORDER", event=e.pk)
        previous = e.at


def _audit_work_wages(report: AuditReport) -> None:
    last = {}
    for w in WorkWage.objects.select_related("position").order_by("player_id", "sequence").iterator():
        if w.sequence != last.get(w.player_id, 0) + 1:
            report.add(6, "WAGE_SEQUENCE_GAP", player=w.player_id, sequence=w.sequence)
        last[w.player_id] = w.sequence
        r = RemunerationRequest.objects.filter(key=w.request_key).first()
        if r is None:
            report.add(6, "WAGE_REQUEST_MISSING", wage=w.pk)
            continue
        company_account = Account.objects.filter(kind=AccountKind.COMPANY.value, owner_id=w.company_id).first()
        if (r.nature != Nature.WAGE.value or r.player_id != w.player_id or r.due != w.due or w.due != w.position.salary
                or company_account is None or r.payer_id != company_account.pk):
            report.add(6, "WAGE_REQUEST_MISMATCH", wage=w.pk, request=r.key)
        if r.status != RequestStatus.RECOGNIZED.value:
            report.add(6, "WAGE_REQUEST_NOT_RECOGNIZED", wage=w.pk, status=r.status)
            continue
        if r.recognized + r.discarded != r.due or r.paid + r.pending != r.recognized:
            report.add(6, "WAGE_AMOUNTS_INCONSISTENT", wage=w.pk, due=r.due, recognized=r.recognized, paid=r.paid,
                       pending=r.pending)
        if r.pending:
            ob = Obligation.objects.filter(pk=r.obligation_id).first()
            if ob is None or ob.amount_due != r.pending:
                report.add(6, "WAGE_PENDING_WITHOUT_OBLIGATION", wage=w.pk, pending=r.pending)


def _audit_owner_payroll(report: AuditReport) -> None:
    world_until = WorldClock.load().world_processed_until
    requests = defaultdict(list)
    for r in RemunerationRequest.objects.filter(reference_kind="owner_payroll").order_by("id").iterator():
        company_id, _, day = r.reference_id.partition(":")
        requests[int(company_id)].append((int(day), r))
        if r.status == RequestStatus.SUBMITTED.value:
            report.add(7, "PAYROLL_REQUEST_LEFT_SUBMITTED", request=r.key)
    for c in Company.objects.order_by("id").iterator():
        owner = Position.objects.filter(company=c, kind=PositionKind.OWNER.value).first()
        if owner is None or owner.holder_id is None:
            continue
        account = Account.objects.filter(kind=AccountKind.COMPANY.value, owner_id=c.pk).first()
        days = [d for d, _ in requests.get(c.pk, ())]
        if len(days) != len(set(days)):
            report.add(7, "PAYROLL_DUPLICATED_DAY", company=c.pk)
        if owner.salary > 0:
            expected = sorted({competence_day_of(t.at) for t in ticks_between(c.founded_at, world_until, [TickKind.DAILY])
                               if t.at > c.founded_at})
            if sorted(set(days)) != expected:
                report.add(7, "PAYROLL_DAYS_MISMATCH", company=c.pk, expected=len(expected), found=len(set(days)))
        for day, r in requests.get(c.pk, ()):
            if (r.nature != Nature.OWNER_SALARY.value or r.player_id != owner.holder_id or r.due != owner.salary
                    or account is None or r.payer_id != account.pk or r.competence_day != day):
                report.add(7, "PAYROLL_REQUEST_MISMATCH", company=c.pk, request=r.key)

