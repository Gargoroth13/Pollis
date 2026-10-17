"""
Modelos do registro monetário (design/24). Todo valor é INTEIRO EM CENTAVOS.

`Account.balance` é CACHE de desempenho; a verdade é a soma dos `Entry` (R9; `audit.py` reconstrói e compara).
`Entry` é IMUTÁVEL: nenhuma API de escrita a altera ou apaga (erro se corrige com `REVERSAL`).
"""
from django.db import models
from django.db.models import Q

from .constants import (AccountKind, HoldStatus, Nature, ObligationStatus, Policy, RequestStatus)


def _choices(enum_cls):
    return [(m.value, m.name) for m in enum_cls]


class LedgerImmutableError(Exception):
    """Tentativa de alterar ou apagar um lançamento (ou uma transação) gravado."""


class _ImmutableQuerySet(models.QuerySet):
    """
    Nenhuma operação em lote do ORM altera ou apaga linhas imutáveis. `bulk_update` e `update_or_create` passam por
    `update()`/`save()` e herdam a recusa; `bulk_create` com `update_conflicts` (upsert) é recusado aqui.
    """

    def update(self, **kwargs):
        raise LedgerImmutableError("registros imutáveis do ledger não podem ser alterados")

    def update_or_create(self, *args, **kwargs):
        raise LedgerImmutableError("registros imutáveis do ledger não podem ser alterados")

    def bulk_update(self, *args, **kwargs):
        raise LedgerImmutableError("registros imutáveis do ledger não podem ser alterados")

    def delete(self):
        raise LedgerImmutableError("registros imutáveis do ledger não podem ser apagados")

    def _raw_delete(self, using):
        raise LedgerImmutableError("registros imutáveis do ledger não podem ser apagados")

    def bulk_create(self, objs, *args, update_conflicts=False, **kwargs):
        if update_conflicts:
            raise LedgerImmutableError("registros imutáveis do ledger não aceitam upsert")
        return super().bulk_create(objs, *args, update_conflicts=False, **kwargs)


class Account(models.Model):
    """Conta de um dono (jogador, empresa, governo, milícia) ou de sistema. Nunca é excluída."""

    kind = models.CharField(max_length=16, choices=_choices(AccountKind))
    owner_id = models.BigIntegerField(default=0)           # 0 = sem dono (singletons e retenções)
    owner_ref = models.CharField(max_length=120, blank=True, default="")   # retenção: identificador opaco do fato
    purpose = models.CharField(max_length=60, blank=True, default="")      # retenção: para quê
    balance = models.BigIntegerField(default=0)            # SALDO BRUTO em centavos (inclui o reservado)
    closed = models.BooleanField(default=False)
    created_at = models.BigIntegerField(default=0)         # tempo de jogo

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["kind", "owner_id", "owner_ref"], name="account_unique_owner"),
            models.CheckConstraint(
                condition=(Q(kind=AccountKind.ISSUANCE.value, balance__lte=0)
                           | (~Q(kind=AccountKind.ISSUANCE.value) & Q(balance__gte=0))),
                name="account_balance_sign_by_kind"),
        ]

    def __str__(self):
        return f"Account({self.kind}:{self.owner_id}{':' + self.owner_ref if self.owner_ref else ''})"


class Transaction(models.Model):
    """Conjunto de lançamentos gravados juntos (atômico) sob uma chave de idempotência."""

    key = models.CharField(max_length=200, unique=True)
    payload_hash = models.CharField(max_length=64)         # sha256 do `payload` canônico (a auditoria confere os dois)
    payload = models.JSONField(default=dict)               # conteúdo canônico: pernas, referência, dia, reservas usadas, estorno
    actor = models.CharField(max_length=60, default="system")
    at = models.BigIntegerField()                          # tempo de jogo
    created_real = models.DateTimeField(auto_now_add=True)

    objects = _ImmutableQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise LedgerImmutableError("transações são imutáveis")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise LedgerImmutableError("transações são imutáveis")


class Entry(models.Model):
    """Uma movimentação de UMA conta para outra. `seq` é a ordem do registro monetário (11 §11.1.0)."""

    seq = models.BigAutoField(primary_key=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="entries")
    from_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="debits")
    to_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="credits")
    amount = models.BigIntegerField()
    nature = models.CharField(max_length=32, choices=_choices(Nature))
    competence_day = models.IntegerField()
    at = models.BigIntegerField()
    created_real = models.DateTimeField(auto_now_add=True)
    category = models.CharField(max_length=60, blank=True, default="")
    operation = models.CharField(max_length=60, blank=True, default="")
    reference_kind = models.CharField(max_length=40)
    reference_id = models.CharField(max_length=120)
    actor = models.CharField(max_length=60, default="system")
    from_balance_before = models.BigIntegerField()
    from_balance_after = models.BigIntegerField()
    to_balance_before = models.BigIntegerField()
    to_balance_after = models.BigIntegerField()
    explained = models.JSONField(default=dict, blank=True)
    reverses = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by")

    objects = _ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ["seq"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="entry_amount_positive"),
            models.CheckConstraint(condition=~Q(from_account=models.F("to_account")), name="entry_not_same_account"),
            models.CheckConstraint(condition=~Q(reference_kind="") & ~Q(reference_id=""), name="entry_reference_required"),
        ]
        indexes = [models.Index(fields=["competence_day", "nature"]),
                   models.Index(fields=["reference_kind", "reference_id"])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise LedgerImmutableError("lançamentos são imutáveis")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise LedgerImmutableError("lançamentos são imutáveis")


class Hold(models.Model):
    """Reserva: parte do saldo bruto da própria conta marcada como indisponível (§24.7). Não é lançamento."""

    key = models.CharField(max_length=200, unique=True)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="holds")
    original_amount = models.BigIntegerField()
    amount = models.BigIntegerField()                      # restante reservado
    status = models.CharField(max_length=10, choices=_choices(HoldStatus), default=HoldStatus.ACTIVE.value)
    reference_kind = models.CharField(max_length=40)
    reference_id = models.CharField(max_length=120)
    created_at = models.BigIntegerField()
    resolved_at = models.BigIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0, amount__lte=models.F("original_amount")),
                                   name="hold_amount_within_original"),
            models.CheckConstraint(condition=Q(original_amount__gt=0), name="hold_original_positive"),
        ]


class Obligation(models.Model):
    """Valor devido e não pago por falta de caixa. NÃO é dinheiro (§24.9)."""

    key = models.CharField(max_length=200, unique=True)
    debtor = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="obligations_owed")
    creditor = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="obligations_due")
    amount_due = models.BigIntegerField()                  # bruto
    amount_paid = models.BigIntegerField(default=0)        # bruto já quitado
    nature = models.CharField(max_length=32, choices=_choices(Nature))
    competence_day = models.IntegerField()
    reference_kind = models.CharField(max_length=40)
    reference_id = models.CharField(max_length=120)
    # imposto retido do bruto na quitação (remuneração): taxa, território opaco e quanto já foi recolhido
    tax_rate = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    tax_territory = models.CharField(max_length=60, blank=True, default="")
    tax_paid = models.BigIntegerField(default=0)
    status = models.CharField(max_length=10, choices=_choices(ObligationStatus), default=ObligationStatus.OPEN.value)
    created_at = models.BigIntegerField()
    cancel_reason = models.CharField(max_length=200, blank=True, default="")
    cancelled_at = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["competence_day", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount_due__gt=0, amount_paid__gte=0, amount_paid__lte=models.F("amount_due")),
                                   name="obligation_paid_within_due"),
        ]


class RemunerationCounter(models.Model):
    """`C_S`, `C_T` e `C_P` (política reconhecida) de um jogador num dia de competência (11 §11.1.0)."""

    player_id = models.BigIntegerField()
    competence_day = models.IntegerField()
    c_s = models.BigIntegerField(default=0)
    c_t = models.BigIntegerField(default=0)
    c_p = models.BigIntegerField(default=0)
    p_released = models.BigIntegerField(default=0)           # reserva política LIBERADA (devida e não reconhecida por T)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player_id", "competence_day"], name="counter_unique_player_day"),
            models.CheckConstraint(condition=Q(c_s__gte=0, c_t__gte=0, c_p__gte=0, p_released__gte=0, c_p__lte=models.F("c_t")),
                                   name="counter_non_negative_and_political_within_total"),
        ]


class RemunerationRequest(models.Model):
    """Pedido de remuneração submetido por um sistema e liquidado em lote, em ordem estável (§24.12.4)."""

    key = models.CharField(max_length=200, unique=True)
    payload_hash = models.CharField(max_length=64)
    player_id = models.BigIntegerField()
    payer = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="remuneration_requests")
    nature = models.CharField(max_length=32, choices=_choices(Nature))
    due = models.BigIntegerField()
    competence_day = models.IntegerField()
    earned_at = models.BigIntegerField()
    policy = models.CharField(max_length=8, choices=_choices(Policy))
    reference_kind = models.CharField(max_length=40)
    reference_id = models.CharField(max_length=120)
    tax_rate = models.DecimalField(max_digits=9, decimal_places=6, default=0)
    tax_territory = models.CharField(max_length=60, blank=True, default="")
    status = models.CharField(max_length=10, choices=_choices(RequestStatus), default=RequestStatus.SUBMITTED.value)
    recognized = models.BigIntegerField(default=0)
    discarded = models.BigIntegerField(default=0)
    paid = models.BigIntegerField(default=0)
    pending = models.BigIntegerField(default=0)
    tax = models.BigIntegerField(default=0)
    net = models.BigIntegerField(default=0)
    position = models.IntegerField(null=True, blank=True)    # posição na ordenação do lote
    batch = models.CharField(max_length=60, blank=True, default="")
    explained = models.JSONField(default=dict, blank=True)
    liquidated_at = models.BigIntegerField(null=True, blank=True)
    obligation = models.ForeignKey(Obligation, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(due__gt=0), name="request_due_positive")]
        indexes = [models.Index(fields=["status", "competence_day"])]


class LedgerScenario(models.Model):
    """Cenário monetário: linhas de dotação por papel de conta (§24.11). No máximo um ativo."""

    name = models.CharField(max_length=80, unique=True)
    active = models.BooleanField(default=False)
    created_at = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            # no máximo um cenário ativo, garantido pelo banco (defesa em profundidade do protocolo de travamento)
            models.UniqueConstraint(fields=["active"], condition=Q(active=True), name="ledger_single_active_scenario"),
        ]


class ScenarioGrantLine(models.Model):
    """Dotação inicial EXPLÍCITA por papel (`player`, `union`, `state`, `municipality`, `militia_bank`...). NULL = não especificada."""

    scenario = models.ForeignKey(LedgerScenario, on_delete=models.CASCADE, related_name="lines")
    role = models.CharField(max_length=40)
    amount = models.BigIntegerField(null=True, blank=True)   # centavos; 0 é válido; NULL = ausente

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scenario", "role"], name="grantline_unique_role"),
            models.CheckConstraint(condition=Q(amount__isnull=True) | Q(amount__gte=0), name="grantline_non_negative"),
        ]
