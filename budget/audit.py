"""
Auditoria do Orçamento (design/09 §34; 24 §24.17). Só LÊ. Invariantes (numeração própria deste app):
  1  decisão de repasse: nível permitido (União→Estado, Estado→Município do Estado), valor positivo, lançamento da chave `ledger_key` (`GOV_TRANSFER`,
     categoria `transfer`) com o valor, a origem e o destino da decisão, ator = quem decidiu
  2  todo lançamento `GOV_TRANSFER` entre contas de governo é um repasse previsto: tem decisão registrada e respeita a hierarquia
  3  plano: rascunho não tem dados de confirmação; confirmado tem decisão `plan_confirmed` única, total = soma das linhas, linhas só de áreas municipais
  4  confirmação: cada piso (Educação/Saúde/Infraestrutura) atendido na foto registrada, soma dos pisos ≤ 100%, total ≤ disponível registrado
"""
from __future__ import annotations

from collections import Counter

from geography.models import City
from ledger.audit import AuditReport
from ledger.constants import AccountKind, Nature
from ledger.models import Account, Entry, Transaction

from .constants import FLOOR_AREAS, MUNICIPAL_AREAS, DecisionKind, Level, PlanStatus
from .govs import account_of, parse_gov
from .models import BudgetPlan, GovernmentDecision

_LEVEL_KIND = {AccountKind.UNION.value: Level.UNION, AccountKind.STATE.value: Level.STATE, AccountKind.MUNICIPALITY.value: Level.MUNICIPALITY}
_ALLOWED = {(Level.UNION, Level.STATE), (Level.STATE, Level.MUNICIPALITY)}


def audit_budget() -> AuditReport:
    report = AuditReport()
    _transfers(report)
    _gov_entries(report)
    _plans(report)
    return report


def _transfers(report: AuditReport) -> None:
    n = 0
    for d in GovernmentDecision.objects.filter(kind=DecisionKind.TRANSFER.value).order_by("pk"):
        n += 1
        data = d.data or {}
        src, dst = parse_gov(data.get("from")), parse_gov(data.get("to"))
        if not isinstance(src, tuple) or not isinstance(dst, tuple):
            report.add(1, "TRANSFER_BAD_PARTIES", decision=d.pk)
            continue
        if (src[0], dst[0]) not in _ALLOWED:
            report.add(1, "TRANSFER_LEVEL_NOT_ALLOWED", decision=d.pk, **{"from": src[0].value, "to": dst[0].value})
        elif src[0] is Level.STATE and City.objects.filter(pk=dst[1]).values_list("state_id", flat=True).first() != src[1]:
            report.add(1, "TRANSFER_MUNICIPALITY_NOT_IN_STATE", decision=d.pk)
        if not isinstance(data.get("amount"), int) or data["amount"] <= 0:
            report.add(1, "TRANSFER_BAD_AMOUNT", decision=d.pk, amount=repr(data.get("amount")))
            continue
        if (d.level, d.territory_id) != (src[0].value, src[1]):
            report.add(1, "TRANSFER_DECISION_LEVEL_MISMATCH", decision=d.pk)
        tx = Transaction.objects.filter(key=d.ledger_key).first() if d.ledger_key else None
        entry = Entry.objects.filter(transaction=tx).first() if tx else None
        if entry is None:
            report.add(1, "TRANSFER_WITHOUT_LEDGER_ENTRY", decision=d.pk, ledger_key=d.ledger_key)
            continue
        src_acc, dst_acc = account_of(*src).pk, account_of(*dst).pk
        if (entry.from_account_id, entry.to_account_id) != (src_acc, dst_acc):
            report.add(1, "TRANSFER_ENTRY_PARTIES_DIFFER", decision=d.pk, entry=entry.seq)
        if entry.amount != data["amount"]:
            report.add(1, "TRANSFER_ENTRY_AMOUNT_DIFFERS", decision=d.pk, entry=entry.seq, decided=data["amount"], posted=entry.amount)
        if entry.nature != Nature.GOV_TRANSFER.value or entry.category != "transfer":
            report.add(1, "TRANSFER_ENTRY_NATURE", decision=d.pk, entry=entry.seq, nature=entry.nature, category=entry.category)
        if tx.actor != f"player:{d.actor_id}":
            report.add(1, "TRANSFER_ACTOR_DIFFERS", decision=d.pk, actor=tx.actor, decided_by=d.actor_id)
    report.stats["transfer_decisions"] = n


def _gov_entries(report: AuditReport) -> None:
    gov_kinds = list(_LEVEL_KIND)
    accounts = {a.pk: a.kind for a in Account.objects.filter(kind__in=gov_kinds)}
    decided = set(GovernmentDecision.objects.filter(kind=DecisionKind.TRANSFER.value).values_list("ledger_key", flat=True))
    n = 0
    for e in Entry.objects.filter(nature=Nature.GOV_TRANSFER.value, from_account_id__in=accounts, to_account_id__in=accounts).select_related("transaction").order_by("seq"):
        n += 1
        if e.transaction.key not in decided:
            report.add(2, "GOV_TRANSFER_WITHOUT_DECISION", entry=e.seq, key=e.transaction.key)
        if (_LEVEL_KIND[accounts[e.from_account_id]], _LEVEL_KIND[accounts[e.to_account_id]]) not in _ALLOWED:
            report.add(2, "GOV_TRANSFER_HIERARCHY", entry=e.seq)
    report.stats["gov_transfer_entries"] = n


def _plans(report: AuditReport) -> None:
    municipal = {a.value for a in MUNICIPAL_AREAS}
    decisions = Counter()
    by_plan = {}
    for d in GovernmentDecision.objects.filter(kind=DecisionKind.PLAN_CONFIRMED.value).order_by("pk"):
        pid = (d.data or {}).get("plan")
        decisions[pid] += 1
        by_plan[pid] = d
    n = 0
    for plan in BudgetPlan.objects.order_by("pk"):
        n += 1
        lines = {l.area: l.amount_cents for l in plan.lines.all()}
        if set(lines) - municipal:
            report.add(3, "PLAN_NON_MUNICIPAL_AREA", plan=plan.pk, areas=sorted(set(lines) - municipal))
        if plan.status == PlanStatus.DRAFT.value:
            if plan.confirmed_at is not None or plan.confirmed_by_id is not None or plan.confirmed_total is not None or plan.confirmation is not None:
                report.add(3, "DRAFT_PLAN_WITH_CONFIRMATION", plan=plan.pk)
            if decisions.get(plan.pk):
                report.add(3, "DRAFT_PLAN_WITH_DECISION", plan=plan.pk)
            continue
        if decisions.get(plan.pk, 0) != 1:
            report.add(3, "CONFIRMED_PLAN_DECISION_COUNT", plan=plan.pk, decisions=decisions.get(plan.pk, 0))
        else:
            d = by_plan[plan.pk]
            if d.data.get("lines") != {k: lines[k] for k in sorted(lines)} or d.territory_id != plan.city_id or d.actor_id != plan.confirmed_by_id:
                report.add(3, "CONFIRMED_PLAN_DECISION_DIFFERS", plan=plan.pk, decision=d.pk)
        if plan.confirmed_total != sum(lines.values()):
            report.add(3, "CONFIRMED_PLAN_TOTAL_DIFFERS", plan=plan.pk, confirmed=plan.confirmed_total, lines=sum(lines.values()))
        check = plan.confirmation or {}
        floors = {f.get("area"): f for f in check.get("floors", [])}
        for area in FLOOR_AREAS:
            f = floors.get(area.value)
            if f is None:
                report.add(4, "PLAN_FLOOR_NOT_RECORDED", plan=plan.pk, area=area.value)
            elif lines.get(area.value, 0) < f.get("required", 0):
                report.add(4, "PLAN_FLOOR_NOT_MET", plan=plan.pk, area=area.value, planned=lines.get(area.value, 0), required=f.get("required"))
        if not check.get("floors_total_valid", False):
            report.add(4, "PLAN_FLOORS_OVER_100", plan=plan.pk)
        if check.get("available") is None or plan.confirmed_total > check["available"]:
            report.add(4, "PLAN_OVER_AVAILABLE", plan=plan.pk, total=plan.confirmed_total, available=check.get("available"))
    report.stats["plans"] = n
