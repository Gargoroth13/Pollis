"""
Transparência de Mercado (design/17): histórico bruto de vendas, agregados diários por produto e histórico agregado de custos
da empresa. O histórico é IMUTÁVEL; os agregados são derivados e podem ser recalculados (a auditoria confere).
"""
from django.db import models
from django.db.models import F, Q

from .constants import Channel, PartyKind


def _choices(enum_cls):
    return [(m.value, m.name) for m in enum_cls]


class MarketImmutableError(Exception):
    code = "MARKET_IMMUTABLE"


class MarketTransaction(models.Model):
    """
    UMA venda concluída (17.2). Só nasce depois de o dinheiro ter se movido: `ledger_key` aponta a transação do registro monetário
    (natureza `SALE`, do comprador ao vendedor, pelo valor total). Valores inteiros: preço em centavos por unidade.
    `buyer_*`/`seller_*` são ids simples (jogador ou empresa), sem chave estrangeira.
    """

    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="market_transactions")
    quantity = models.BigIntegerField()
    unit_price_cents = models.BigIntegerField()
    total_cents = models.BigIntegerField()
    at = models.BigIntegerField()
    competence_day = models.IntegerField()
    buyer_kind = models.CharField(max_length=10, choices=_choices(PartyKind))
    buyer_id = models.BigIntegerField()
    seller_kind = models.CharField(max_length=10, choices=_choices(PartyKind))
    seller_id = models.BigIntegerField()
    channel = models.CharField(max_length=16, choices=_choices(Channel))
    ledger_key = models.CharField(max_length=200, unique=True)
    created_real = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="markettx_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price_cents__gt=0), name="markettx_price_positive"),
            models.CheckConstraint(condition=Q(total_cents=F("quantity") * F("unit_price_cents")), name="markettx_total_is_qty_times_price"),
        ]
        indexes = [models.Index(fields=["product", "at"], name="markettx_product_at"),
                   models.Index(fields=["buyer_kind", "buyer_id", "competence_day"], name="markettx_buyer_day"),
                   models.Index(fields=["competence_day"], name="markettx_day")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise MarketImmutableError("transações de mercado são imutáveis")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise MarketImmutableError("transações de mercado são imutáveis")


class DailyProductStat(models.Model):
    """
    Agregado diário por produto (17.10, 17.19): só de dias JÁ FECHADOS. Vendas (nº, quantidade, valor, menor/maior preço) e usos
    reais (produção e consumo). `min/max_price_cents` NULL = nenhuma venda no dia (≠ 0). `available_stock` NULL = a oferta do Mercado
    ainda não existe/não foi informada (≠ 0).
    """

    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="daily_stats")
    day = models.IntegerField()
    transactions = models.IntegerField(default=0)
    volume = models.BigIntegerField(default=0)
    value_cents = models.BigIntegerField(default=0)
    min_price_cents = models.BigIntegerField(null=True, blank=True)
    max_price_cents = models.BigIntegerField(null=True, blank=True)
    production = models.BigIntegerField(default=0)
    consumption = models.BigIntegerField(default=0)
    available_stock = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["day", "product_id"]
        constraints = [models.UniqueConstraint(fields=["product", "day"], name="dailyproductstat_unique")]
        indexes = [models.Index(fields=["day"], name="dailyproductstat_day")]


class CompanyCostDay(models.Model):
    """Custo diário agregado da empresa por categoria (17.16): `input:<produto>`, `salaries`, `taxes`. Dia fechado; derivado."""

    company_id = models.BigIntegerField()
    day = models.IntegerField()
    category = models.CharField(max_length=80)
    amount_cents = models.BigIntegerField()

    class Meta:
        ordering = ["day", "company_id", "category"]
        constraints = [
            models.UniqueConstraint(fields=["company_id", "day", "category"], name="companycostday_unique"),
            models.CheckConstraint(condition=Q(amount_cents__gt=0), name="companycostday_positive"),
        ]
        indexes = [models.Index(fields=["company_id", "day"], name="companycostday_company_day")]


class RollupMark(models.Model):
    """Dia fechado já agregado (idempotência do fechamento). Um registro por dia."""

    day = models.IntegerField(unique=True)
    computed_at = models.BigIntegerField()

    class Meta:
        ordering = ["day"]
