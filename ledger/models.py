"""
Modelos do registro monetário (design/24). Todo valor é INTEIRO EM CENTAVOS.

`Account.balance` é CACHE de desempenho; a verdade é a soma dos `Entry` (R9; `audit.py` reconstrói e compara).
`Entry` é IMUTÁVEL: nenhuma API de escrita a altera ou apaga (erro se corrige com `REVERSAL`).
"""
import contextvars

from django.db import models, transaction
from django.db.models import Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver

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


class GrantLineLockedError(LedgerImmutableError):
    """Código `GRANT_LINE_LOCKED`: a linha de dotação (ou o cenário) já tem dotações históricas e a configuração não muda."""

    code = "GRANT_LINE_LOCKED"

    def __init__(self, message, **detail):
        super().__init__(f"GRANT_LINE_LOCKED: {message}")
        self.detail = detail


# --- imutabilidade da configuração de dotação depois da primeira dotação (design/24 §24.11) ------------------------------
# Toda escrita em `ScenarioGrantLine` (e o renome/exclusão de `LedgerScenario`) passa por aqui, seja `save`, `update`,
# `bulk_update`, `bulk_create`, `update_or_create` ou exclusão (instância, QuerySet ou cascata, via `pre_delete`).
#
# PROTOCOLO DE BLOQUEIO (único; vale para toda a configuração de cenários e para a emissão):
#   * Operação de MUTAÇÃO da configuração (`activate_scenario`, `set_grant_line`, qualquer escrita em `ScenarioGrantLine`,
#     renome/exclusão de `LedgerScenario`): o PRIMEIRO passo que bloqueia é `lock_all_scenarios()`, que trava TODOS os
#     cenários em ordem crescente de pk numa só instrução. Só depois a operação lê os dados (linha, histórico) e decide. NADA
#     é lido antes para escolher o que travar e NENHUMA verificação adquire bloqueio adicional: se os dados mudarem enquanto a
#     operação esperava (outra mutação moveu a linha para outro cenário), o que ela relê já está coberto pelo conjunto
#     travado. Assim não existe aquisição fora da ordem global crescente, logo não há ciclo com `activate_scenario`.
#   * EMISSÃO (`services._check_grant`): contas em ordem crescente de id e, por último, UM só cenário (o emissor); ela nunca
#     pede outro cenário nem outro bloqueio depois. Uma mutação espera a emissão em andamento (que segura o cenário até
#     confirmar) e depois relê o histórico, que já contém a dotação.
#   * Referência a um cenário que NÃO está no conjunto travado (criado depois da instrução de bloqueio) é recusada com
#     `ScenarioSetChangedError` (repita a operação): travá-lo agora seria uma aquisição fora da ordem.
#   * Não compor, numa mesma transação externa, uma emissão (que segura um cenário) e uma mutação (que pede todos).
_UNKNOWN = object()                                  # valor vindo de expressão (F(), Case...): não dá para saber antes de gravar
_VERIFIED = contextvars.ContextVar("ledger_grant_line_verified", default=False)
_LINE_FIELDS = {"scenario": "scenario_id", "scenario_id": "scenario_id", "role": "role", "amount": "amount"}


class ScenarioSetChangedError(LedgerImmutableError):
    """Código `SCENARIO_SET_CHANGED`: a operação referencia um cenário criado depois de ela travar todos; repita a operação."""

    code = "SCENARIO_SET_CHANGED"


def lock_scenarios(ids=None, names=None):
    """`SELECT ... FOR UPDATE` dos cenários, em ordem crescente de pk. Mutações usam `lock_all_scenarios()`; a emissão usa
    `names=[seu cenário]` (um só)."""
    qs = LedgerScenario.objects.select_for_update().order_by("pk")
    if ids is not None:
        qs = qs.filter(pk__in=ids)
    if names is not None:
        qs = qs.filter(name__in=names)
    return list(qs)


def lock_all_scenarios():
    """Primeiro passo de toda mutação da configuração: trava TODOS os cenários (ordem crescente de pk). `{pk: nome}`."""
    return {sc.pk: sc.name for sc in lock_scenarios()}


def _scenario_name(locked, scenario_id):
    try:
        return locked[scenario_id]
    except KeyError:
        raise ScenarioSetChangedError(
            f"SCENARIO_SET_CHANGED: o cenário {scenario_id!r} não existe ou foi criado depois do bloqueio; repita a operação") from None


def grant_history(scenario_name, role=None):
    """Lançamentos de dotação já gravados para o cenário (e papel): o que a configuração não pode mais contradizer."""
    qs = Entry.objects.filter(nature=Nature.SCENARIO_GRANT.value, reference_kind="scenario", reference_id=scenario_name)
    return qs if role is None else qs.filter(explained__role=role)


def _check_line_changes(changes, locked):
    """
    `changes`: lista de `(antes, depois)`, cada um `(scenario_id, role, amount)` ou None (inserção / exclusão). `locked`: o
    `{pk: nome}` de `lock_all_scenarios()` (esta função NÃO bloqueia nada). Deve rodar dentro da transação que o obteve.
    Recusa (`GrantLineLockedError`) se:
      * a linha de ANTES já gerou dotações e algo nela muda (valor, cenário, papel) ou ela é excluída;
      * o par (cenário, papel) de DEPOIS já tem dotações e o valor novo difere do que foi emitido (recriar a linha).
    """
    for old, new in changes:
        if old == new:
            continue                                          # idempotente: nada muda
        if old is not None:
            name = _scenario_name(locked, old[0])
            if grant_history(name, old[1]).exists():
                raise GrantLineLockedError("a linha já gerou dotações; não pode mudar nem ser excluída",
                                           scenario=name, role=old[1], configured=old[2])
        if new is not None and new[0] is not None and (old is None or old[:2] != new[:2]):
            name = _scenario_name(locked, new[0])
            history = grant_history(name, new[1])
            conflicting = history.exists() if new[2] is _UNKNOWN else history.exclude(amount=new[2]).exists()
            if conflicting:
                raise GrantLineLockedError("já há dotações para este cenário e papel com outro valor",
                                           scenario=name, role=new[1], configured=new[2])


def _check_scenario_renames(renames):
    """`renames`: `(pk, nome_antigo, nome_novo)`; chamada com todos os cenários já travados. Um cenário com dotações não muda
    de nome (a referência do lançamento é o nome)."""
    for _, old, new in renames:
        if old != new and grant_history(old).exists():
            raise GrantLineLockedError("o cenário já tem dotações; o nome não muda", scenario=old)


def _check_scenario_deletion(name):
    if grant_history(name).exists():
        raise GrantLineLockedError("o cenário já tem dotações; não pode ser excluído", scenario=name)


def _constant(value):
    return _UNKNOWN if hasattr(value, "resolve_expression") else value


class _GrantLineQuerySet(models.QuerySet):
    def _rows(self):
        return list(self.values_list("pk", "scenario_id", "role", "amount"))

    def update(self, **kwargs):
        if _VERIFIED.get() or not set(kwargs) & set(_LINE_FIELDS):
            return super().update(**kwargs)
        new_values = {_LINE_FIELDS[k]: (v.pk if isinstance(v, models.Model) else _constant(v)) for k, v in kwargs.items()
                      if k in _LINE_FIELDS}
        if new_values.get("scenario_id") is _UNKNOWN or new_values.get("role") is _UNKNOWN:
            raise LedgerImmutableError("expressões em cenário/papel de uma linha de dotação não são suportadas")
        with transaction.atomic(using=self.db):
            locked = lock_all_scenarios()                     # 1º passo: tudo travado, em ordem; nada é lido antes
            rows = self._rows()                               # lido DEPOIS do bloqueio
            _check_line_changes([((s, r, a), (new_values.get("scenario_id", s), new_values.get("role", r),
                                              new_values.get("amount", a))) for _, s, r, a in rows], locked)
            return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        objs = list(objs)
        touched = {_LINE_FIELDS[f] for f in fields if f in _LINE_FIELDS}
        if not touched:
            return super().bulk_update(objs, fields, batch_size)
        with transaction.atomic(using=self.db):
            locked = lock_all_scenarios()
            stored = {r[0]: r[1:] for r in self.model.objects.filter(pk__in=[o.pk for o in objs])
                      .values_list("pk", "scenario_id", "role", "amount")}          # lido DEPOIS do bloqueio
            changes = []
            for o in objs:
                old = stored.get(o.pk)
                if old is None:
                    continue
                now = {"scenario_id": o.scenario_id, "role": o.role, "amount": o.amount}
                changes.append((old, tuple(now[f] if f in touched else old[i]
                                           for i, f in enumerate(("scenario_id", "role", "amount")))))
            _check_line_changes(changes, locked)
            token = _VERIFIED.set(True)                       # já verificado: `update()` não repete
            try:
                return super().bulk_update(objs, fields, batch_size)
            finally:
                _VERIFIED.reset(token)

    def bulk_create(self, objs, *args, update_conflicts=False, **kwargs):
        if update_conflicts:
            raise LedgerImmutableError("linhas de dotação não aceitam upsert em lote; use set_grant_line")
        objs = list(objs)
        with transaction.atomic(using=self.db):
            locked = lock_all_scenarios()
            _check_line_changes([(None, (o.scenario_id, o.role, o.amount)) for o in objs], locked)
            return super().bulk_create(objs, *args, update_conflicts=False, **kwargs)

    def delete(self):
        # verifica ANTES do Collector: a recusa dentro do `atomic(savepoint=False)` dele envenenaria uma transação externa
        with transaction.atomic(using=self.db):
            locked = lock_all_scenarios()
            _check_line_changes([((s, r, a), None) for _, s, r, a in self._rows()], locked)   # lido DEPOIS do bloqueio
            return super().delete()

    def _raw_delete(self, using):
        raise LedgerImmutableError("linhas de dotação não são apagadas sem passar pela verificação do histórico")


class _ScenarioQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "name" not in kwargs:
            return super().update(**kwargs)
        new_name = _constant(kwargs["name"])
        with transaction.atomic(using=self.db):
            lock_all_scenarios()
            _check_scenario_renames([(pk, name, new_name) for pk, name in self.values_list("pk", "name")])
            return super().update(**kwargs)

    def delete(self):
        with transaction.atomic(using=self.db):
            lock_all_scenarios()
            for _, name in self.values_list("pk", "name"):
                _check_scenario_deletion(name)
            return super().delete()

    def _raw_delete(self, using):
        raise LedgerImmutableError("cenários não são apagados sem passar pela verificação do histórico")


class LedgerScenario(models.Model):
    """Cenário monetário: linhas de dotação por papel de conta (§24.11). No máximo um ativo."""

    name = models.CharField(max_length=80, unique=True)
    active = models.BooleanField(default=False)
    created_at = models.BigIntegerField(default=0)

    objects = _ScenarioQuerySet.as_manager()

    def delete(self, *args, **kwargs):
        with transaction.atomic(using=kwargs.get("using")):
            lock_all_scenarios()
            _check_scenario_deletion(self.name)
            return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        with transaction.atomic(using=kwargs.get("using")):
            if self.pk is not None and not self._state.adding:
                lock_all_scenarios()                                 # 1º passo; o nome guardado é lido DEPOIS
                stored = LedgerScenario.objects.filter(pk=self.pk).values_list("name", flat=True).first()
                if stored is not None:
                    _check_scenario_renames([(self.pk, stored, self.name)])
            return super().save(*args, **kwargs)

    class Meta:
        base_manager_name = "objects"          # `_base_manager` (usado pelo ORM por baixo) também passa pelas proteções
        constraints = [
            # no máximo um cenário ativo, garantido pelo banco (defesa em profundidade do protocolo de travamento)
            models.UniqueConstraint(fields=["active"], condition=Q(active=True), name="ledger_single_active_scenario"),
        ]


class ScenarioGrantLine(models.Model):
    """Dotação inicial EXPLÍCITA por papel (`player`, `union`, `state`, `municipality`, `militia_bank`...). NULL = não especificada."""

    scenario = models.ForeignKey(LedgerScenario, on_delete=models.CASCADE, related_name="lines")
    role = models.CharField(max_length=40)
    amount = models.BigIntegerField(null=True, blank=True)   # centavos; 0 é válido; NULL = ausente

    objects = _GrantLineQuerySet.as_manager()

    def _stored(self):
        if self.pk is None or self._state.adding:
            return None
        return ScenarioGrantLine.objects.filter(pk=self.pk).values_list("scenario_id", "role", "amount").first()

    def delete(self, *args, **kwargs):
        with transaction.atomic(using=kwargs.get("using")):
            locked = lock_all_scenarios()
            stored = self._stored()                                  # lido DEPOIS do bloqueio
            if stored is not None:
                _check_line_changes([(stored, None)], locked)
            return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None and len(args) >= 3:
            update_fields = args[2]
        with transaction.atomic(using=kwargs.get("using")):
            locked = lock_all_scenarios()
            stored = self._stored()                                  # lido DEPOIS do bloqueio
            now = {"scenario_id": self.scenario_id, "role": self.role, "amount": self.amount}
            fields = ("scenario_id", "role", "amount")
            if stored is not None and update_fields is not None:
                chosen = {_LINE_FIELDS.get(f, f) for f in update_fields}
                new = tuple(now[f] if f in chosen else stored[i] for i, f in enumerate(fields))
            else:
                new = tuple(now[f] for f in fields)
            _check_line_changes([(stored, new)], locked)
            return super().save(*args, **kwargs)

    class Meta:
        base_manager_name = "objects"
        constraints = [
            models.UniqueConstraint(fields=["scenario", "role"], name="grantline_unique_role"),
            models.CheckConstraint(condition=Q(amount__isnull=True) | Q(amount__gte=0), name="grantline_non_negative"),
        ]


@receiver(pre_delete, sender=ScenarioGrantLine)
def _guard_grant_line_delete(sender, instance, **kwargs):
    """Última defesa (a verificação normal roda antes, em `delete()`): qualquer exclusão que chegue ao Collector, cascata incluída."""
    locked = lock_all_scenarios()
    stored = ScenarioGrantLine.objects.filter(pk=instance.pk).values_list("scenario_id", "role", "amount").first()
    if stored is not None:
        _check_line_changes([(stored, None)], locked)


@receiver(pre_delete, sender=LedgerScenario)
def _guard_scenario_delete(sender, instance, **kwargs):
    lock_all_scenarios()
    if grant_history(instance.name).exists():
        raise GrantLineLockedError("o cenário já tem dotações; não pode ser excluído", scenario=instance.name)
