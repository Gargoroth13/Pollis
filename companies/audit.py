"""
Auditoria das Empresas (design/02 §16-17; 24). Só LÊ. Invariantes (numeração própria deste app):
  1  toda empresa tem exatamente um cargo Dono ocupado (02 §16) e uma conta `COMPANY` no registro monetário
  2  a fundação tem o lançamento `COMPANY_FOUNDING` (fundador → União) com o valor cobrado; o valor cobrado é positivo
  3  cada aporte tem o lançamento `DONATION` (jogador → conta da empresa) com o mesmo valor, e o aporte vem do Dono
"""
from __future__ import annotations

from ledger import services as ledger
from ledger.audit import AuditReport
from ledger.constants import AccountKind, Nature
from ledger.models import Account, Entry

from .constants import PositionKind
from .models import CapitalContribution, Company, Position


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
    report.stats.update({"companies": companies, "contributions": contributions,
                         "capital": sum(CapitalContribution.objects.values_list("amount", flat=True))})
    return report
