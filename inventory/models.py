"""
Modelos do Inventário pessoal (design/05). O inventário é a POSSE de Produtos do catálogo por jogador: jogador → produto →
quantidade (05 §2). Estoque de empresa é outra estrutura (05 §17) e não vive aqui. Nada do produto é copiado: o
`InventoryItem` referencia `catalog.Product` (categoria, consumível e permanente vêm do catálogo, 05 §3).

A trilha `InventoryMovement` é IMUTÁVEL e registra cada alteração de posse com origem, destino, produto, quantidade, instante
e tipo (05 §19). `InventoryItem.quantity` é cache de leitura; a verdade auditável é a soma dos movimentos (`audit.py`).
"""
from django.db import models
from django.db.models import Q

from .constants import Operation


def _choices(enum_cls):
    return [(m.value, m.name) for m in enum_cls]


class InventoryImmutableError(Exception):
    """Código `INVENTORY_IMMUTABLE`: a trilha de movimentos e os envios não se alteram nem se apagam."""

    code = "INVENTORY_IMMUTABLE"


class _ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise InventoryImmutableError("a trilha do inventário é imutável")

    def bulk_update(self, objs, fields, batch_size=None):
        raise InventoryImmutableError("a trilha do inventário é imutável")

    def delete(self):
        raise InventoryImmutableError("a trilha do inventário é imutável")

    def _raw_delete(self, using):
        raise InventoryImmutableError("a trilha do inventário é imutável")


class InventoryItem(models.Model):
    """Posse agregada: `quantity` unidades de `product` do `player` (produtos empilháveis, 05 §2). Só existe com quantidade > 0."""

    player = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="inventory_items")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="inventory_items")
    quantity = models.BigIntegerField()

    class Meta:
        ordering = ["player_id", "product_id"]
        constraints = [
            models.UniqueConstraint(fields=["player", "product"], name="inventory_item_unique_player_product"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="inventory_item_quantity_positive"),
        ]


class AutoConsumption(models.Model):
    """
    Configuração de Auto-consumo do jogador (design/04 §16): habilitado ou não e o alimento preferido (opcional). É estado de
    configuração (mutável); o que o auto-consumo FAZ fica na trilha `InventoryMovement` (`reference_kind="auto_consumption"`).
    """

    player = models.OneToOneField("players.Player", on_delete=models.PROTECT, related_name="auto_consumption")
    enabled = models.BooleanField(default=False)
    preferred_product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    updated_at = models.BigIntegerField()


class Shipment(models.Model):
    """Um envio pelo Correio (05 §11-12): item de um jogador a outro com taxa obrigatória. Imutável; guarda o detalhamento da taxa."""

    sender = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="shipments_sent")
    recipient = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="shipments_received")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="shipments")
    quantity = models.BigIntegerField()
    sequence = models.IntegerField()                       # nº do envio do remetente (1, 2, ...): chave estável do lançamento
    reference_value = models.BigIntegerField()            # centavos: base_price × quantidade (05 §12)
    fee = models.BigIntegerField()                        # centavos efetivamente cobrados (0 só se a taxa estiver calibrada a 0)
    ledger_key = models.CharField(max_length=120, blank=True, default="")
    at = models.BigIntegerField()
    explained = models.JSONField(default=dict, blank=True)  # `Explained.to_dict()` da taxa (20)

    objects = _ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["sender", "sequence"], name="shipment_unique_sender_sequence"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="shipment_quantity_positive"),
            models.CheckConstraint(condition=Q(fee__gte=0, reference_value__gte=0), name="shipment_amounts_non_negative"),
            models.CheckConstraint(condition=~Q(sender=models.F("recipient")), name="shipment_not_to_self"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise InventoryImmutableError("envios são imutáveis")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise InventoryImmutableError("envios são imutáveis")


class InventoryMovement(models.Model):
    """
    Alteração de posse (05 §19). `delta` é com sinal, do ponto de vista de `player`: entra (+) ou sai (−). `origin` e
    `destination` são referências textuais (`player:12`, `consumption`, `retail:...`, `company:7`...), para que sistemas
    futuros apareçam na trilha sem mudar este modelo. `key` torna a operação idempotente.
    """

    player = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="inventory_movements")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="inventory_movements")
    delta = models.BigIntegerField()
    quantity_after = models.BigIntegerField()
    operation = models.CharField(max_length=20, choices=_choices(Operation))
    origin = models.CharField(max_length=80)
    destination = models.CharField(max_length=80)
    key = models.CharField(max_length=160, unique=True)
    reference_kind = models.CharField(max_length=40)
    reference_id = models.CharField(max_length=120)
    at = models.BigIntegerField()
    created_real = models.DateTimeField(auto_now_add=True)
    explained = models.JSONField(default=dict, blank=True)

    objects = _ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=~Q(delta=0), name="movement_delta_not_zero"),
            models.CheckConstraint(condition=Q(quantity_after__gte=0), name="movement_quantity_after_non_negative"),
            models.CheckConstraint(condition=~Q(origin="") & ~Q(destination="") & ~Q(reference_kind="") & ~Q(reference_id=""),
                                   name="movement_origin_destination_reference_required"),
        ]
        indexes = [models.Index(fields=["player", "product", "id"]), models.Index(fields=["reference_kind", "reference_id"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise InventoryImmutableError("movimentos são imutáveis")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise InventoryImmutableError("movimentos são imutáveis")
