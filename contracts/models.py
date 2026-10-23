"""
Contratos (design/18): o contrato, o histórico imutável de eventos (18.11) e cada ocorrência de execução (18.5). Partes são ids simples
(jogador ou empresa); a identidade real fica registrada mesmo quando um tipo futuro a esconder do público (18.14).
"""
from __future__ import annotations

import hashlib
import json

from django.db import models
from django.db.models import Q

from .constants import (ContractType, EventKind, ExecutionStatus, Frequency, PartyKind, Responsible, Side, Status)


def _choices(enum_cls):
    return [(m.value, m.name) for m in enum_cls]


class ContractsImmutableError(Exception):
    code = "CONTRACTS_IMMUTABLE"


class _Immutable(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ContractsImmutableError(f"{type(self).__name__} é imutável")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ContractsImmutableError(f"{type(self).__name__} é imutável")


def terms_digest(*, type, a_kind, a_id, b_kind, b_id, proposed_by, terms, frequency, starts_on, ends_on, penalty_cents, max_failures) -> str:
    """Impressão digital dos termos (18.4: congelados depois do aceite). A auditoria recalcula e compara."""
    payload = {"type": type, "a": [a_kind, a_id], "b": [b_kind, b_id], "proposed_by": proposed_by, "terms": terms,
               "frequency": frequency, "starts_on": starts_on, "ends_on": ends_on, "penalty_cents": penalty_cents,
               "max_failures": max_failures}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Contract(models.Model):
    """
    A parte A é quem ENTREGA o objeto (vendedor, credor, locador...) e B quem o recebe; os papéis vêm do handler do tipo. Os termos
    (`terms`, frequência, datas, multa, condição) são congelados na criação: `terms_hash` os sela e `save` recusa qualquer alteração.
    """

    type = models.CharField(max_length=12, choices=_choices(ContractType))
    status = models.CharField(max_length=10, choices=_choices(Status), default=Status.PROPOSED.value)
    party_a_kind = models.CharField(max_length=8, choices=_choices(PartyKind))
    party_a_id = models.BigIntegerField()
    party_b_kind = models.CharField(max_length=8, choices=_choices(PartyKind))
    party_b_id = models.BigIntegerField()
    proposed_by = models.CharField(max_length=1, choices=_choices(Side))
    terms = models.JSONField(default=dict)
    frequency = models.CharField(max_length=8, choices=_choices(Frequency))
    starts_on = models.IntegerField(null=True, blank=True)         # dia de competência da proposta (fornecimento); empréstimo: nulo
    ends_on = models.IntegerField(null=True, blank=True)
    penalty_cents = models.BigIntegerField(default=0)
    max_failures = models.PositiveIntegerField(null=True, blank=True)    # condição (18.6): falhas até a quebra por inadimplência
    terms_hash = models.CharField(max_length=64)
    occurrences = models.PositiveIntegerField()                    # nº total de ocorrências previstas
    # --- estado de execução (muda; os termos acima não) ---
    anchor_day = models.IntegerField(null=True, blank=True)        # dia da ativação em que a série foi ancorada (calendário derivado)
    last_due_day = models.IntegerField(null=True, blank=True)      # dia da última ocorrência (derivado na ativação)
    next_sequence = models.PositiveIntegerField(default=0)         # próxima ocorrência a executar
    next_due_day = models.IntegerField(null=True, blank=True)      # dia dela (None = nada a executar)
    failures = models.PositiveIntegerField(default=0)
    accepted_a_at = models.BigIntegerField(null=True, blank=True)
    accepted_b_at = models.BigIntegerField(null=True, blank=True)
    created_at = models.BigIntegerField()
    activated_at = models.BigIntegerField(null=True, blank=True)
    ended_at = models.BigIntegerField(null=True, blank=True)
    end_reason = models.CharField(max_length=40, blank=True, default="")

    FROZEN = ("type", "party_a_kind", "party_a_id", "party_b_kind", "party_b_id", "proposed_by", "terms", "frequency", "starts_on",
              "ends_on", "penalty_cents", "max_failures")

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=~(Q(party_a_kind=models.F("party_b_kind")) & Q(party_a_id=models.F("party_b_id"))),
                                   name="contract_distinct_parties"),
            models.CheckConstraint(condition=Q(penalty_cents__gte=0), name="contract_penalty_non_negative"),
            models.CheckConstraint(condition=Q(next_sequence__lte=models.F("occurrences")), name="contract_sequence_within_occurrences"),
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(status__in=["cancelled", "closed", "broken"]),
                                   name="contract_ended_only_when_ended"),
        ]
        indexes = [models.Index(fields=["status", "next_due_day"], name="contract_status_due"),
                   models.Index(fields=["party_a_kind", "party_a_id"], name="contract_party_a"),
                   models.Index(fields=["party_b_kind", "party_b_id"], name="contract_party_b")]

    def frozen_digest(self) -> str:
        return terms_digest(type=self.type, a_kind=self.party_a_kind, a_id=self.party_a_id, b_kind=self.party_b_kind,
                            b_id=self.party_b_id, proposed_by=self.proposed_by, terms=self.terms, frequency=self.frequency,
                            starts_on=self.starts_on, ends_on=self.ends_on, penalty_cents=self.penalty_cents,
                            max_failures=self.max_failures)

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.terms_hash = self.terms_hash or self.frozen_digest()
        elif self.terms_hash != self.frozen_digest():
            raise ContractsImmutableError("os termos do contrato são congelados (18.4)")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ContractsImmutableError("contratos não são apagados (18.9: o histórico permanece)")

    def party(self, side: Side):
        return (self.party_a_kind, self.party_a_id) if side is Side.A else (self.party_b_kind, self.party_b_id)


class ContractEvent(_Immutable):
    """Evento do histórico (18.11). `seq` é contínuo por contrato; `ref` identifica a coisa a que o evento se refere (idempotência)."""

    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="events")
    seq = models.PositiveIntegerField()
    kind = models.CharField(max_length=20, choices=_choices(EventKind))
    at = models.BigIntegerField()
    competence_day = models.IntegerField()
    actor_kind = models.CharField(max_length=8, blank=True, default="")      # "" = o sistema
    actor_id = models.BigIntegerField(null=True, blank=True)
    ref = models.CharField(max_length=60, blank=True, default="")
    ledger_key = models.CharField(max_length=200, blank=True, default="")
    data = models.JSONField(default=dict)

    class Meta:
        ordering = ["contract_id", "seq"]
        constraints = [
            models.UniqueConstraint(fields=["contract", "seq"], name="contract_event_seq_unique"),
            models.UniqueConstraint(fields=["contract", "kind", "ref"], condition=~Q(ref=""), name="contract_event_ref_unique"),
        ]


class ContractExecution(_Immutable):
    """Uma ocorrência (18.5) com seu resultado auditável. Única por (contrato, sequência): idempotência da execução automática."""

    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="executions")
    sequence = models.PositiveIntegerField()
    due_day = models.IntegerField()
    at = models.BigIntegerField()
    status = models.CharField(max_length=8, choices=_choices(ExecutionStatus))
    failure_code = models.CharField(max_length=60, blank=True, default="")
    responsible = models.CharField(max_length=6, blank=True, default="", choices=[("", "")] + _choices(Responsible))
    pending_quantity = models.BigIntegerField(null=True, blank=True)          # 18.6: o que ficou pendente
    pending_cents = models.BigIntegerField(null=True, blank=True)
    ledger_key = models.CharField(max_length=200, blank=True, default="")
    detail = models.JSONField(default=dict)

    class Meta:
        ordering = ["contract_id", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["contract", "sequence"], name="contract_execution_unique"),
            models.CheckConstraint(
                condition=(Q(status="success", failure_code="", responsible="") | (Q(status="failed") & ~Q(failure_code="") & ~Q(responsible=""))),
                name="contract_execution_failure_fields"),
        ]
