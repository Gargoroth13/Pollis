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
  8  estoque: quantidade = soma dos movimentos (nunca negativa em nenhum ponto); qualidade do item = a do último movimento; total em
     estoque dentro da capacidade da estrela
  9  produção: todo movimento de produção nasce de uma ação de Trabalhar paga (WorkWage) de um funcionário de produção da própria
     empresa; os insumos consumidos são exatamente os registrados; nada é produzido sem produto escolhido
 10  linha de produção: nº de seleções = histórico; produto atual = último do histórico; só tipos que produzem; trocas respeitam o
     cooldown; fração acumulada em [0, 1)
 11  cargos de suporte: toda contribuição (`SupportWork`) tem o salário pago da mesma ação (jogador, sequência), da mesma empresa e
     cargo, de Engenheiro ou Advogado; o dia é o da ação; o valor é o do detalhamento; vagas de suporte (abertas ou ocupadas) dentro
     do limite da estrela
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from core.models import WorldClock
from core.timeline import TickKind, ticks_between
from ledger import services as ledger
from ledger.audit import AuditReport
from ledger.constants import AccountKind, Nature, RequestStatus
from ledger.models import Account, Entry, Obligation, RemunerationRequest
from ledger.money import competence_day_of

from . import params
from .constants import SUPPORT_POSITION_KINDS, ApplicationStatus, CompanyType, EventKind, PositionKind, PositionStatus
from .models import (Application, CapitalContribution, Company, Position, PositionEvent, ProductionChange, ProductionLine,
                     StockItem, StockMovement, SupportWork, WorkWage)


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
    _audit_stock(report)
    _audit_production(report)
    _audit_support(report)
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



def _audit_stock(report: AuditReport) -> None:
    running = defaultdict(int)
    last = {}
    for m in StockMovement.objects.order_by("id").iterator():
        k = (m.company_id, m.product_id)
        running[k] += m.delta
        if running[k] < 0:
            report.add(8, "STOCK_NEGATIVE", company=m.company_id, product=m.product_id, movement=m.pk)
        if running[k] != m.quantity_after:
            report.add(8, "MOVEMENT_BALANCE_MISMATCH", movement=m.pk, expected=running[k], found=m.quantity_after)
        last[k] = m
    items = {(i.company_id, i.product_id): i for i in StockItem.objects.order_by("id").iterator()}
    for k, total in running.items():
        item = items.get(k)
        if total > 0 and (item is None or item.quantity != total):
            report.add(8, "STOCK_ITEM_MISMATCH", company=k[0], product=k[1], movements=total,
                       item=None if item is None else item.quantity)
        if total == 0 and item is not None:
            report.add(8, "STOCK_ITEM_SHOULD_NOT_EXIST", company=k[0], product=k[1])
        if item is not None and last[k].quality_after != item.quality:
            report.add(8, "STOCK_QUALITY_MISMATCH", company=k[0], product=k[1])
    for k in set(items) - set(running):
        report.add(8, "STOCK_ITEM_WITHOUT_MOVEMENTS", company=k[0], product=k[1])
    from . import stock
    used = defaultdict(int)
    for i in items.values():
        used[i.company_id] += i.quantity
    for c in Company.objects.filter(pk__in=list(used)).iterator():
        capacity = int(stock.capacity_of(c.stars).value)
        if used[c.pk] > capacity:
            report.add(8, "STOCK_OVER_CAPACITY", company=c.pk, used=used[c.pk], capacity=capacity)


def _audit_production(report: AuditReport) -> None:
    for m in StockMovement.objects.filter(operation="production").select_related("product").order_by("id").iterator():
        _, _, sequence = m.reference_id.partition(":")
        wage = WorkWage.objects.select_related("position").filter(player_id=m.actor, sequence=int(sequence or 0)).first()
        if (wage is None or wage.company_id != m.company_id or wage.position.kind != PositionKind.WORKER.value
                or m.reference_kind != "work_production" or m.delta <= 0):
            report.add(9, "PRODUCTION_WITHOUT_PAID_WORK", movement=m.pk)
            continue
        line = ProductionLine.objects.filter(company_id=m.company_id).first()
        if line is None or not ProductionChange.objects.filter(company_id=m.company_id, to_product_id=m.product_id,
                                                               at__lte=m.at).exists():
            report.add(9, "PRODUCTION_WITHOUT_PRODUCT_CHOICE", movement=m.pk)
        consumed = {k: v for k, v in (m.explained.get("consumed") or {}).items()}
        booked = {}
        for i in StockMovement.objects.filter(operation="input_consumption", reference_kind="work_production",
                                              reference_id=m.reference_id, company_id=m.company_id).select_related("product"):
            booked[i.product.key] = -i.delta
        if consumed != booked:
            report.add(9, "INPUT_CONSUMPTION_MISMATCH", movement=m.pk, registered=consumed, booked=booked)


    for line in ProductionLine.objects.select_related("company", "product").order_by("company_id").iterator():
        changes = list(ProductionChange.objects.filter(company_id=line.company_id).order_by("sequence"))
        if len(changes) != line.changes or (changes and changes[-1].to_product_id != line.product_id):
            report.add(10, "PRODUCTION_HISTORY_MISMATCH", company=line.company_id, changes=len(changes), line=line.changes)
        if CompanyType(line.company.type) not in params.PRODUCING_TYPES:
            report.add(10, "COMPANY_TYPE_CANNOT_PRODUCE", company=line.company_id, company_type=line.company.type)
        if not 0 <= line.carry < 1:
            report.add(10, "CARRY_OUT_OF_RANGE", company=line.company_id, carry=str(line.carry))
        for before, after in zip(changes, changes[1:]):
            if before.cooldown_until is not None and after.at < before.cooldown_until:
                report.add(10, "COOLDOWN_VIOLATED", company=line.company_id, sequence=after.sequence)


def _audit_support(report: AuditReport) -> None:
    for w in SupportWork.objects.select_related("position").order_by("id").iterator():
        wage = WorkWage.objects.filter(player_id=w.player_id, sequence=w.sequence).first()
        if (wage is None or wage.company_id != w.company_id or wage.position_id != w.position_id or w.kind != w.position.kind
                or w.kind not in SUPPORT_POSITION_KINDS):
            report.add(11, "SUPPORT_WORK_WITHOUT_PAID_WORK", support_work=w.pk)
            continue
        if w.competence_day != competence_day_of(w.at) or wage.at != w.at:
            report.add(11, "SUPPORT_WORK_DAY_MISMATCH", support_work=w.pk, day=w.competence_day)
        if abs(w.contribution - Decimal(str(w.explained.get("value", w.contribution)))) > Decimal("0.000001"):
            report.add(11, "SUPPORT_CONTRIBUTION_MISMATCH", support_work=w.pk, contribution=str(w.contribution))
    for company in Company.objects.order_by("id").iterator():
        limit = params.SUPPORT_LIMIT_PER_STAR[company.stars]
        for kind in sorted(SUPPORT_POSITION_KINDS):
            have = Position.objects.filter(company=company, kind=kind).exclude(status=PositionStatus.CLOSED.value).count()
            if have > limit:
                report.add(11, "SUPPORT_LIMIT_EXCEEDED", company=company.pk, kind=kind, have=have, limit=limit)
