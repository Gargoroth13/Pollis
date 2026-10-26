"""
Auditoria dos Imóveis (design/10). Só LÊ. Invariantes (numeração própria deste app):
  1  título: o dono atual do lote = o destino do último `TitleEvent`; governo não tem título explícito com dono; titular existe
  2  histórico de aquisição: sequência contínua 1..n por lote; cada origem = destino do evento anterior (a 1ª vem do governo);
     preço positivo; cada evento tem o lançamento monetário da sua chave, pelo valor, da natureza esperada (leilão: `AUCTION_PAYMENT`
     do arrematante ao Município do lote; venda: `SALE` do comprador ao vendedor, SEM imposto)
  3  leilão: lances contínuos 1..n, estritamente crescentes, sem repetir o líder em seguida, o último = o lance líder; extensões
     coerentes (cada lance `extended` soma uma extensão); vendido ⇒ título + pagamento do lance líder; sem lances ⇒ não vendido;
     invalidado ⇒ sem lançamento nem título; aberto vencido além do que o tick processou é só estatística
  4  anúncio: vendido ⇒ comprador, título e `SALE` pelo preço; aberto ⇒ o vendedor ainda é o dono e não há obra ativa no lote
  5  imóvel: um por lote, unidades/QoL do tipo, lote OCUPADO, dono não é o governo; obra concluída ⇔ imóvel; obra ativa ⇒ obra da
     Construtora ainda ativa, dona do lote, lote vazio
  6  unidades: cada imóvel tem exatamente `units` unidades, índices 1..n
  7  residência ativa: uma unidade por jogador e um jogador por unidade; o morador tem direito à unidade (proprietário jogador com a unidade
     sem aluguel em vigor, ou inquilino de contrato em vigor); a moradia inicial é a ausência de linha
  8  aluguel: cada `Tenancy` aponta um contrato `rent` cujos termos (lote, unidade) conferem e cujo inquilino é o registrado; no máximo um
     contrato em vigor por unidade; o locador VIGENTE do contrato em vigor é o proprietário atual do lote (a venda cede o contrato, 10 §13);
     anúncio de aluguel aberto: dono do lote, unidade livre; alugado: contrato existente com os termos do anúncio
"""
from __future__ import annotations

from typing import Dict, Optional

from contracts.constants import RUNNING_STATUSES, ContractType
from contracts.models import Contract
from companies.models import ConstructionJob
from companies.constants import ProjectStatus
from geography.constants import Occupation
from geography.models import Lot
from ledger.audit import AuditReport
from ledger.constants import AccountKind, Nature
from ledger.models import Account, Entry, Transaction

from . import params
from .constants import AuctionStatus, ListingStatus, OwnerKind, SiteStatus, TitleReason
from .constants import RentListingStatus
from .models import (ActiveResidence, Auction, Building, ConstructionSite, Listing, LotTitle, RentListing, Tenancy, TitleEvent, Unit)


def _payment(key: str, nature: Nature) -> Optional[Entry]:
    tx = Transaction.objects.filter(key=key).first()
    if tx is None:
        return None
    return Entry.objects.filter(transaction=tx, nature=nature.value).first()


def audit_properties() -> AuditReport:
    report = AuditReport()
    _titles(report)
    _auctions(report)
    _listings(report)
    _buildings(report)
    _units(report)
    _residences(report)
    _rent(report)
    return report


def _titles(report: AuditReport) -> None:
    last: Dict[int, TitleEvent] = {}
    n = 0
    for e in TitleEvent.objects.order_by("lot_id", "sequence"):
        n += 1
        prev = last.get(e.lot_id)
        expected_seq = 1 if prev is None else prev.sequence + 1
        if e.sequence != expected_seq:
            report.add(2, "TITLE_SEQUENCE_GAP", lot=e.lot_id, sequence=e.sequence, expected=expected_seq)
        origin = (OwnerKind.GOVERNMENT.value, None) if prev is None else (prev.to_kind, prev.to_id)
        if (e.from_kind, e.from_id) != origin:
            report.add(2, "TITLE_CHAIN_BROKEN", lot=e.lot_id, sequence=e.sequence, from_=[e.from_kind, e.from_id], expected=list(origin))
        reason = report.enum(TitleReason, e.reason, "TitleEvent", "reason", e.pk)
        last[e.lot_id] = e
        if reason is None:
            continue
        nature = Nature.AUCTION_PAYMENT if reason is TitleReason.AUCTION else Nature.SALE
        entry = _payment(e.ledger_key, nature)
        if entry is None:
            report.add(2, "TITLE_WITHOUT_PAYMENT", lot=e.lot_id, sequence=e.sequence, key=e.ledger_key)
        elif entry.amount != e.price_cents:
            report.add(2, "TITLE_PRICE_MISMATCH", lot=e.lot_id, sequence=e.sequence, paid=entry.amount, price=e.price_cents)
        elif reason is TitleReason.AUCTION:
            account = Account.objects.filter(pk=entry.to_account_id).first()
            if account is None or account.kind != AccountKind.MUNICIPALITY.value:
                report.add(2, "AUCTION_NOT_PAID_TO_MUNICIPALITY", lot=e.lot_id, sequence=e.sequence)
        elif Entry.objects.filter(transaction__key=e.ledger_key).exclude(pk=entry.pk).exists():
            report.add(2, "PROPERTY_SALE_HAS_EXTRA_LEG", lot=e.lot_id, sequence=e.sequence)       # 24 §24.7: sem imposto
    report.stats["title_events"] = n
    seen = set()
    for t in LotTitle.objects.order_by("lot_id"):
        seen.add(t.lot_id)
        event = last.get(t.lot_id)
        if event is None or (event.to_kind, event.to_id) != (t.owner_kind, t.owner_id):
            report.add(1, "TITLE_NOT_LAST_EVENT", lot=t.lot_id, owner=[t.owner_kind, t.owner_id])
        kind = report.enum(OwnerKind, t.owner_kind, "LotTitle", "owner_kind", t.pk)
        if kind is OwnerKind.GOVERNMENT and t.owner_id is not None:
            report.add(1, "GOVERNMENT_WITH_OWNER_ID", lot=t.lot_id)
    for lot_id in set(last) - seen:
        report.add(1, "EVENTS_WITHOUT_TITLE", lot=lot_id)
    report.stats["titled_lots"] = len(seen)


def _auctions(report: AuditReport) -> None:
    n = 0
    for a in Auction.objects.order_by("id"):
        n += 1
        status = report.enum(AuctionStatus, a.status, "Auction", "status", a.pk)
        if status is None:
            continue
        bids = list(a.bid_rows.order_by("sequence"))
        if [b.sequence for b in bids] != list(range(1, len(bids) + 1)) or a.bids != len(bids):
            report.add(3, "BID_SEQUENCE_BROKEN", auction=a.pk, count=a.bids, rows=len(bids))
        previous = None
        for b in bids:
            floor = a.min_bid_cents if previous is None else previous.amount_cents + params.MIN_BID_INCREMENT_CENTS
            if b.amount_cents < floor:
                report.add(3, "BID_BELOW_FLOOR", auction=a.pk, sequence=b.sequence, amount=b.amount_cents, floor=floor)
            if previous is not None and (previous.bidder_kind, previous.bidder_id) == (b.bidder_kind, b.bidder_id):
                report.add(3, "TOP_BIDDER_OUTBID_SELF", auction=a.pk, sequence=b.sequence)
            if b.at >= a.ends_at:
                report.add(3, "BID_AFTER_END", auction=a.pk, sequence=b.sequence)
            previous = b
        if bids:
            top = bids[-1]
            if (a.top_bid_cents, a.top_bidder_kind, a.top_bidder_id) != (top.amount_cents, top.bidder_kind, top.bidder_id):
                report.add(3, "TOP_BID_MISMATCH", auction=a.pk)
        elif a.top_bid_cents is not None or a.top_bidder_id is not None:
            report.add(3, "TOP_BID_WITHOUT_BIDS", auction=a.pk)
        if a.extensions != sum(1 for b in bids if b.extended) or a.ends_at < a.base_ends_at:
            report.add(3, "EXTENSIONS_INCONSISTENT", auction=a.pk, extensions=a.extensions)
        event = TitleEvent.objects.filter(ledger_key=f"auction:{a.pk}:payment").first()
        paid = _payment(f"auction:{a.pk}:payment", Nature.AUCTION_PAYMENT)
        if status is AuctionStatus.SOLD:
            if not bids or event is None or paid is None:
                report.add(3, "SOLD_WITHOUT_TITLE_OR_PAYMENT", auction=a.pk)
            elif event.price_cents != a.top_bid_cents or paid.amount != a.top_bid_cents or (event.to_kind, event.to_id) != (
                    a.top_bidder_kind, a.top_bidder_id) or event.lot_id != a.lot_id:
                report.add(3, "SOLD_RESULT_MISMATCH", auction=a.pk)
        else:
            if event is not None or paid is not None:
                report.add(3, "PAYMENT_OR_TITLE_WITHOUT_SALE", auction=a.pk, status=a.status)
            if status is AuctionStatus.UNSOLD and bids:
                report.add(3, "UNSOLD_WITH_BIDS", auction=a.pk)
            if status is AuctionStatus.INVALIDATED and not bids:
                report.add(3, "INVALIDATED_WITHOUT_BIDS", auction=a.pk)
            if status is AuctionStatus.OPEN and a.closed_at is not None:
                report.add(3, "OPEN_WITH_CLOSE_TIME", auction=a.pk)
        if status is not AuctionStatus.OPEN and a.closed_at is None:
            report.add(3, "CLOSED_WITHOUT_TIME", auction=a.pk)
    report.stats["auctions"] = n


def _listings(report: AuditReport) -> None:
    n = 0
    for li in Listing.objects.order_by("id"):
        n += 1
        status = report.enum(ListingStatus, li.status, "Listing", "status", li.pk)
        if status is ListingStatus.SOLD:
            event = TitleEvent.objects.filter(ledger_key=f"listing:{li.pk}:sale").first()
            if (event is None or _payment(f"listing:{li.pk}:sale", Nature.SALE) is None or event.price_cents != li.price_cents
                    or (event.to_kind, event.to_id) != (li.buyer_kind, li.buyer_id) or (event.from_kind, event.from_id) != (
                        li.seller_kind, li.seller_id)):
                report.add(4, "SOLD_LISTING_INCONSISTENT", listing=li.pk)
        elif status is ListingStatus.OPEN:
            title = LotTitle.objects.filter(lot_id=li.lot_id).first()
            if title is None or (title.owner_kind, title.owner_id) != (li.seller_kind, li.seller_id):
                report.add(4, "OPEN_LISTING_SELLER_NOT_OWNER", listing=li.pk)
            if ConstructionSite.objects.filter(lot_id=li.lot_id, status=SiteStatus.ACTIVE.value).exists():
                report.add(4, "OPEN_LISTING_WITH_ACTIVE_SITE", listing=li.pk)
        elif status is not None and TitleEvent.objects.filter(ledger_key=f"listing:{li.pk}:sale").exists():
            report.add(4, "CANCELLED_LISTING_WITH_TITLE", listing=li.pk)
    report.stats["listings"] = n


def _buildings(report: AuditReport) -> None:
    n = 0
    for b in Building.objects.order_by("lot_id"):
        n += 1
        kind = params.BUILDING_TYPES.get(b.kind)
        if kind is None:
            report.add(5, "UNKNOWN_BUILDING_KIND", lot=b.lot_id, kind=b.kind)
        elif (b.units, b.qol_bonus) != (kind.units, kind.qol_bonus):
            report.add(5, "BUILDING_DOES_NOT_MATCH_TYPE", lot=b.lot_id)
        if Lot.objects.filter(pk=b.lot_id).values_list("occupation", flat=True).first() != Occupation.OCCUPIED.value:
            report.add(5, "BUILDING_LOT_NOT_OCCUPIED", lot=b.lot_id)
        title = LotTitle.objects.filter(lot_id=b.lot_id).first()
        if title is None or title.owner_kind == OwnerKind.GOVERNMENT.value:
            report.add(5, "BUILDING_WITHOUT_PRIVATE_OWNER", lot=b.lot_id)
        if b.job_id is not None and not ConstructionSite.objects.filter(job_id=b.job_id, lot_id=b.lot_id, status=SiteStatus.COMPLETED.value).exists():
            report.add(5, "BUILDING_WITHOUT_COMPLETED_SITE", lot=b.lot_id)
    report.stats["buildings"] = n
    for s in ConstructionSite.objects.order_by("id"):
        status = report.enum(SiteStatus, s.status, "ConstructionSite", "status", s.pk)
        job = ConstructionJob.objects.filter(pk=s.job_id).first()
        if job is None or job.company_id != s.company_id or job.project != s.project:
            report.add(5, "SITE_JOB_MISMATCH", site=s.pk)
            continue
        if status is SiteStatus.ACTIVE:
            title = LotTitle.objects.filter(lot_id=s.lot_id).first()
            if job.status != ProjectStatus.ACTIVE.value:
                report.add(5, "ACTIVE_SITE_JOB_NOT_ACTIVE", site=s.pk)
            if title is None or (title.owner_kind, title.owner_id) != (OwnerKind.COMPANY.value, s.company_id):
                report.add(5, "SITE_LOT_NOT_OWNED_BY_BUILDER", site=s.pk)
            if Building.objects.filter(lot_id=s.lot_id).exists():
                report.add(5, "ACTIVE_SITE_ON_BUILT_LOT", site=s.pk)
        elif status is SiteStatus.COMPLETED:
            if job.status != ProjectStatus.COMPLETED.value or not Building.objects.filter(lot_id=s.lot_id, job_id=s.job_id).exists():
                report.add(5, "COMPLETED_SITE_WITHOUT_BUILDING", site=s.pk)
    report.stats["sites"] = ConstructionSite.objects.count()


def _units(report: AuditReport) -> None:
    n = 0
    for b in Building.objects.order_by("lot_id"):
        indexes = list(b.unit_rows.order_by("index").values_list("index", flat=True))
        n += len(indexes)
        if indexes != list(range(1, b.units + 1)):
            report.add(6, "UNITS_DO_NOT_MATCH_BUILDING", lot=b.lot_id, units=b.units, rows=len(indexes))
    report.stats["units"] = n


def _residences(report: AuditReport) -> None:
    from . import housing
    n = 0
    for r in ActiveResidence.objects.select_related("unit__building").order_by("player_id"):
        n += 1
        lease = housing.running_lease(r.unit_id)
        if lease is not None:
            tenancy = Tenancy.objects.get(contract_id=lease.pk)
            if (tenancy.tenant_kind, tenancy.tenant_id) != (OwnerKind.PLAYER.value, r.player_id):
                report.add(7, "RESIDENT_NOT_THE_TENANT", player=r.player_id, unit=r.unit_id)
        else:
            title = LotTitle.objects.filter(lot_id=r.unit.building.lot_id).first()
            if title is None or (title.owner_kind, title.owner_id) != (OwnerKind.PLAYER.value, r.player_id):
                report.add(7, "RESIDENT_WITHOUT_RIGHT", player=r.player_id, unit=r.unit_id)
    report.stats["residences"] = n


def _rent(report: AuditReport) -> None:
    running = {}
    n = 0
    for t in Tenancy.objects.select_related("unit__building").order_by("id"):
        n += 1
        c = Contract.objects.filter(pk=t.contract_id).first()
        if c is None or c.type != ContractType.RENT.value:
            report.add(8, "TENANCY_WITHOUT_RENT_CONTRACT", contract=t.contract_id)
            continue
        if (c.terms.get("lot"), c.terms.get("unit")) != (t.unit.building.lot_id, t.unit.index):
            report.add(8, "TENANCY_TERMS_MISMATCH", contract=c.pk)
        if (c.party_b_kind, c.party_b_id) != (t.tenant_kind, t.tenant_id):
            report.add(8, "TENANCY_TENANT_MISMATCH", contract=c.pk)
        if c.status in {s.value for s in RUNNING_STATUSES}:
            if t.unit_id in running:
                report.add(8, "TWO_RUNNING_LEASES_ON_UNIT", unit=t.unit_id, contracts=[running[t.unit_id], c.pk])
            running[t.unit_id] = c.pk
            title = LotTitle.objects.filter(lot_id=t.unit.building.lot_id).first()
            if title is None or (title.owner_kind, title.owner_id) != (c.party_a_kind, c.party_a_id):
                report.add(8, "LANDLORD_IS_NOT_THE_OWNER", contract=c.pk, lot=t.unit.building.lot_id)
    report.stats["tenancies"] = n
    for li in RentListing.objects.select_related("unit__building").order_by("id"):
        status = report.enum(RentListingStatus, li.status, "RentListing", "status", li.pk)
        if status is RentListingStatus.OPEN:
            title = LotTitle.objects.filter(lot_id=li.unit.building.lot_id).first()
            if title is None or (title.owner_kind, title.owner_id) != (li.landlord_kind, li.landlord_id):
                report.add(8, "OPEN_RENT_LISTING_LANDLORD_NOT_OWNER", listing=li.pk)
            if li.unit_id in running:
                report.add(8, "OPEN_RENT_LISTING_ON_LEASED_UNIT", listing=li.pk)
        elif status is RentListingStatus.RENTED:
            c = Contract.objects.filter(pk=li.contract_id).first() if li.contract_id else None
            if c is None or c.type != ContractType.RENT.value or c.terms.get("amount_cents") != li.amount_cents or (
                    c.terms.get("lot"), c.terms.get("unit")) != (li.unit.building.lot_id, li.unit.index):
                report.add(8, "RENTED_LISTING_WITHOUT_MATCHING_CONTRACT", listing=li.pk)
