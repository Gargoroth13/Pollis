"""
Imóveis (design/10): a propriedade dos lotes (inicialmente do governo, 10 §2), o histórico de aquisição (10 §3), leilões (10 §4),
anúncios de venda (10 §8), o imóvel construído (10 §5-6) e a ligação da obra da Construtora ao lote (10 §28).

Lote e imóvel são conceitos diferentes (10 §31): `geography.Lot` é o terreno; `Building` é o que foi construído. Lote sem `LotTitle`
é do governo (estado inicial: nenhuma linha por lote até a primeira transferência).
"""
from __future__ import annotations

from django.db import models
from django.db.models import Q

from .constants import AuctionStatus, ListingStatus, OwnerKind, SiteStatus, TitleReason


def _choices(enum_cls):
    return [(m.value, m.name) for m in enum_cls]


class PropertiesImmutableError(Exception):
    code = "PROPERTIES_IMMUTABLE"


class _Immutable(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PropertiesImmutableError(f"{type(self).__name__} é imutável")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PropertiesImmutableError(f"{type(self).__name__} é imutável")


class LotTitle(models.Model):
    """Dono ATUAL do lote (e do imóvel nele: 10 §3 'mesmo ativo'). Sem linha = governo. A verdade auditável é a cadeia de `TitleEvent`."""

    lot = models.OneToOneField("geography.Lot", on_delete=models.PROTECT, related_name="title")
    owner_kind = models.CharField(max_length=10, choices=_choices(OwnerKind))
    owner_id = models.BigIntegerField(null=True, blank=True)
    since = models.BigIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(owner_kind="government", owner_id__isnull=True)
                                              | (~Q(owner_kind="government") & Q(owner_id__isnull=False))),
                                   name="lottitle_owner_matches_kind"),
        ]
        indexes = [models.Index(fields=["owner_kind", "owner_id"], name="lottitle_owner")]


class TitleEvent(_Immutable):
    """Aquisição registrada (10 §3 'o histórico da aquisição deve permanecer registrável'). Cadeia contínua por lote."""

    lot = models.ForeignKey("geography.Lot", on_delete=models.PROTECT, related_name="title_events")
    sequence = models.PositiveIntegerField()
    reason = models.CharField(max_length=10, choices=_choices(TitleReason))
    from_kind = models.CharField(max_length=10, choices=_choices(OwnerKind))
    from_id = models.BigIntegerField(null=True, blank=True)
    to_kind = models.CharField(max_length=10, choices=_choices(OwnerKind))
    to_id = models.BigIntegerField(null=True, blank=True)
    price_cents = models.BigIntegerField()
    ledger_key = models.CharField(max_length=200)
    reference_kind = models.CharField(max_length=20)
    reference_id = models.CharField(max_length=40)
    at = models.BigIntegerField()

    class Meta:
        ordering = ["lot_id", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["lot", "sequence"], name="titleevent_unique_sequence"),
            models.UniqueConstraint(fields=["ledger_key"], name="titleevent_unique_ledger_key"),
            models.CheckConstraint(condition=Q(price_cents__gt=0), name="titleevent_price_positive"),
        ]


class Auction(models.Model):
    """Leilão público de lote do governo (10 §4). `ends_at` cresce com as extensões; `base_ends_at` é o encerramento original."""

    lot = models.ForeignKey("geography.Lot", on_delete=models.PROTECT, related_name="auctions")
    status = models.CharField(max_length=12, choices=_choices(AuctionStatus), default=AuctionStatus.OPEN.value)
    min_bid_cents = models.BigIntegerField()
    starts_at = models.BigIntegerField()
    base_ends_at = models.BigIntegerField()
    ends_at = models.BigIntegerField()
    extensions = models.PositiveIntegerField(default=0)
    top_bid_cents = models.BigIntegerField(null=True, blank=True)
    top_bidder_kind = models.CharField(max_length=10, blank=True, default="")
    top_bidder_id = models.BigIntegerField(null=True, blank=True)
    bids = models.PositiveIntegerField(default=0)
    closed_at = models.BigIntegerField(null=True, blank=True)
    ledger_key = models.CharField(max_length=200, blank=True, default="")
    result_note = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["lot"], condition=Q(status="open"), name="auction_one_open_per_lot"),
            models.CheckConstraint(condition=Q(min_bid_cents__gt=0, ends_at__gte=models.F("base_ends_at")), name="auction_basic_valid"),
            models.CheckConstraint(condition=Q(top_bid_cents__isnull=True) | Q(top_bid_cents__gte=models.F("min_bid_cents")),
                                   name="auction_top_bid_at_least_min"),
        ]
        indexes = [models.Index(fields=["status", "ends_at"], name="auction_status_ends")]


class AuctionBid(_Immutable):
    auction = models.ForeignKey(Auction, on_delete=models.PROTECT, related_name="bid_rows")
    sequence = models.PositiveIntegerField()
    bidder_kind = models.CharField(max_length=10, choices=_choices(OwnerKind))
    bidder_id = models.BigIntegerField()
    amount_cents = models.BigIntegerField()
    at = models.BigIntegerField()
    extended = models.BooleanField(default=False)               # este lance estendeu o encerramento (10 §4.3)
    acted_by = models.BigIntegerField()                          # jogador que deu o lance (o Dono, quando é empresa)

    class Meta:
        ordering = ["auction_id", "sequence"]
        constraints = [models.UniqueConstraint(fields=["auction", "sequence"], name="auctionbid_unique_sequence"),
                       models.CheckConstraint(condition=Q(amount_cents__gt=0), name="auctionbid_amount_positive")]


class Listing(models.Model):
    """Anúncio de venda do proprietário (10 §8): o preço é do dono; comprar é pagar o preço anunciado e receber a propriedade."""

    lot = models.ForeignKey("geography.Lot", on_delete=models.PROTECT, related_name="listings")
    seller_kind = models.CharField(max_length=10, choices=_choices(OwnerKind))
    seller_id = models.BigIntegerField()
    price_cents = models.BigIntegerField()
    status = models.CharField(max_length=10, choices=_choices(ListingStatus), default=ListingStatus.OPEN.value)
    listed_at = models.BigIntegerField()
    closed_at = models.BigIntegerField(null=True, blank=True)
    buyer_kind = models.CharField(max_length=10, blank=True, default="")
    buyer_id = models.BigIntegerField(null=True, blank=True)
    ledger_key = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["lot"], condition=Q(status="open"), name="listing_one_open_per_lot"),
            models.CheckConstraint(condition=Q(price_cents__gt=0), name="listing_price_positive"),
        ]


class Building(models.Model):
    """Imóvel construído (10 §5-6): UM por lote. As unidades e o QoL base vêm do tipo (`params.BUILDING_TYPES`)."""

    lot = models.OneToOneField("geography.Lot", on_delete=models.PROTECT, related_name="building")
    kind = models.CharField(max_length=30)
    units = models.PositiveIntegerField()
    qol_bonus = models.DecimalField(max_digits=4, decimal_places=2)
    builder_company_id = models.BigIntegerField(null=True, blank=True)
    job_id = models.BigIntegerField(null=True, blank=True, unique=True)
    completed_at = models.BigIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(units__gt=0), name="building_units_positive")]


class ConstructionSite(models.Model):
    """Liga a obra da Construtora ao lote (10 §5, §28). Uma obra ativa por lote; a conclusão gera o `Building`."""

    job_id = models.BigIntegerField(unique=True)
    lot = models.ForeignKey("geography.Lot", on_delete=models.PROTECT, related_name="sites")
    company_id = models.BigIntegerField()
    project = models.CharField(max_length=40)
    status = models.CharField(max_length=10, choices=_choices(SiteStatus), default=SiteStatus.ACTIVE.value)
    created_at = models.BigIntegerField()
    completed_at = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["lot"], condition=Q(status="active"), name="constructionsite_one_active_per_lot")]
