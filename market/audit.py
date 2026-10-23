"""
Auditoria da Transparência de Mercado (design/17; 24). Só LÊ. Invariantes (numeração própria deste app):
  1  toda venda do histórico tem o lançamento `SALE` do comprador ao vendedor, da mesma transação do registro monetário, pelo valor
     total, no mesmo instante; total = quantidade × preço; dia de competência = o do instante; comprador e vendedor existem e são
     entidades diferentes; canal/tipos de parte dentro do domínio
  2  agregado diário: cada dia fechado (`RollupMark`) tem exatamente o que o histórico bruto produz hoje (vendas, produção, consumo
     e custos da empresa), sem linha a mais nem a menos; nenhum agregado de dia sem marca ou de dia ainda não terminado
  3  oferta registrada (`available_stock`) nunca negativa; a produção e o consumo agregados nunca são negativos
"""
from __future__ import annotations

from typing import Dict

from ledger.audit import AuditReport
from ledger.constants import Nature
from ledger.models import Account, Entry
from ledger.money import competence_day_of

from core import clock as game_clock

from . import rollup
from .constants import Channel, PartyKind
from .recording import find_payment
from .models import CompanyCostDay, DailyProductStat, MarketTransaction, RollupMark


def audit_market() -> AuditReport:
    report = AuditReport()
    n = 0
    for tx in MarketTransaction.objects.order_by("id").iterator():
        n += 1
        if report.enum(Channel, tx.channel, "MarketTransaction", "channel", tx.pk) is None:
            continue
        b, s = report.enum(PartyKind, tx.buyer_kind, "MarketTransaction", "buyer_kind", tx.pk), report.enum(
            PartyKind, tx.seller_kind, "MarketTransaction", "seller_kind", tx.pk)
        if b is None or s is None:
            continue
        if tx.total_cents != tx.quantity * tx.unit_price_cents:
            report.add(1, "TOTAL_MISMATCH", tx=tx.pk)
        if tx.competence_day != competence_day_of(tx.at):
            report.add(1, "COMPETENCE_DAY_MISMATCH", tx=tx.pk)
        if (b, tx.buyer_id) == (s, tx.seller_id):
            report.add(1, "SAME_PARTY", tx=tx.pk)
        buyer, seller = rollup_party_account(b, tx.buyer_id), rollup_party_account(s, tx.seller_id)
        if buyer is None or seller is None:
            report.add(1, "PARTY_MISSING", tx=tx.pk, buyer=buyer is not None, seller=seller is not None)
            continue
        sale = find_payment(tx.ledger_key, buyer, seller, tx.total_cents, include_reversed=True)
        if sale is None or sale.at != tx.at:
            report.add(1, "SALE_ENTRY_MISSING", tx=tx.pk, ledger_key=tx.ledger_key)
        elif Entry.objects.filter(reverses_id=sale.pk).exists() or Entry.objects.filter(
                reverses__transaction__key=tx.ledger_key, reverses__nature=Nature.TAX_SALES.value).exists():
            # estorno técnico do pagamento: o histórico é imutável e a venda continuaria contando nas estatísticas (decisão de design)
            report.add(1, "SALE_PAYMENT_REVERSED", tx=tx.pk, ledger_key=tx.ledger_key)
    report.stats["transactions"] = n
    _audit_aggregates(report)
    return report


def rollup_party_account(kind: PartyKind, entity_id: int):
    """Id da conta do registro monetário da parte, ou None se a entidade/conta não existe (não cria conta nenhuma)."""
    from companies.models import Company
    from players.models import Player
    from ledger.constants import AccountKind
    if kind is PartyKind.PLAYER:
        exists, account_kind = Player.objects.filter(pk=entity_id).exists(), AccountKind.PLAYER.value
    else:
        exists, account_kind = Company.objects.filter(pk=entity_id).exists(), AccountKind.COMPANY.value
    if not exists:
        return None
    return Account.objects.filter(kind=account_kind, owner_id=entity_id).values_list("pk", flat=True).first()


def _audit_aggregates(report: AuditReport) -> None:
    today = competence_day_of(game_clock.now())
    marks = set(RollupMark.objects.values_list("day", flat=True))
    report.stats["closed_days"] = len(marks)
    for day in sorted(marks):
        if day >= today:
            report.add(2, "DAY_CLOSED_BEFORE_IT_ENDED", day=day)
    stray = set(DailyProductStat.objects.values_list("day", flat=True)) | set(CompanyCostDay.objects.values_list("day", flat=True))
    for day in sorted(stray - marks):
        report.add(2, "AGGREGATE_WITHOUT_MARK", day=day)
    stats_by_day: Dict[int, Dict[int, DailyProductStat]] = {}
    for st in DailyProductStat.objects.filter(day__in=marks).iterator():
        stats_by_day.setdefault(st.day, {})[st.product_id] = st
        if st.available_stock is not None and st.available_stock < 0:
            report.add(3, "NEGATIVE_SUPPLY", day=st.day, product=st.product_id)
        if st.production < 0 or st.consumption < 0:
            report.add(3, "NEGATIVE_USAGE", day=st.day, product=st.product_id)
    costs_by_day: Dict[int, Dict] = {}
    for c in CompanyCostDay.objects.filter(day__in=marks).iterator():
        costs_by_day.setdefault(c.day, {})[(c.company_id, c.category)] = c.amount_cents
    for day in sorted(marks):
        fresh = rollup.compute_day(day)
        have = stats_by_day.get(day, {})
        for pid in sorted(set(fresh["products"]) | set(have)):
            want, got = fresh["products"].get(pid), have.get(pid)
            if want is None or got is None:
                report.add(2, "AGGREGATE_ROW_MISMATCH", day=day, product=pid, missing="stored" if got is None else "raw")
                continue
            actual = {k: getattr(got, k) for k in want}
            if actual != want:
                report.add(2, "AGGREGATE_VALUE_MISMATCH", day=day, product=pid, stored=actual, recomputed=want)
        stored_costs = costs_by_day.get(day, {})
        fresh_costs = {k: v for k, v in fresh["costs"].items() if v > 0}
        if stored_costs != fresh_costs:
            report.add(2, "COST_AGGREGATE_MISMATCH", day=day, stored=len(stored_costs), recomputed=len(fresh_costs))
