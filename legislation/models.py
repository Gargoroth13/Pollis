from django.db import models
from django.db.models import Q

from .constants import ACTIVE, Choice, EventKind, Kind, LawStatus, RoundKind, RoundStatus, Status, SuggestionStatus


def _choices(enum_cls):
    return [(m.value, m.value) for m in enum_cls]


_ACTIVE_VALUES = sorted(s.value for s in ACTIVE)


class LegislativeState(models.Model):
    """Linha única: trava global do avanço do calendário e o interregno aberto (07 §07.19)."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    interregnum_since = models.BigIntegerField(null=True, blank=True)       # início do interregno aberto (sem Câmara); None = há Câmara
    last_advanced_at = models.BigIntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name="legislativestate_single_row")]

    @classmethod
    def load(cls, for_update=False):
        qs = cls.objects.select_for_update() if for_update else cls.objects
        obj = qs.filter(pk=1).first()
        if obj is None:
            cls.objects.get_or_create(pk=1)
            obj = (cls.objects.select_for_update() if for_update else cls.objects).get(pk=1)
        return obj


class Interregnum(models.Model):
    """Período sem Câmara constituída (07 §07.19). Histórico imutável depois de fechado."""

    started_at = models.BigIntegerField()
    ended_at = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["id"]


class Proposal(models.Model):
    """
    Proposta legislativa (07 §07.4). O histórico NUNCA é apagado (07 §07.25). `scope` é a chave de conflito (07 §07.17): no máximo UMA proposta ativa
    por escopo (restrição parcial no banco). `deadline_at` é o próximo instante em que o motor age sobre ela (nulo = nada agendado).
    """

    author_id = models.BigIntegerField()
    law_key = models.CharField(max_length=80)
    scope = models.CharField(max_length=100)
    kind = models.CharField(max_length=8, choices=_choices(Kind))
    status = models.CharField(max_length=16, choices=_choices(Status), default=Status.DISCUSSION.value)
    params = models.JSONField(null=True, blank=True)                 # parâmetros X vigentes na versão atual (None na revogação)
    description = models.TextField(blank=True, default="")
    version = models.PositiveIntegerField(default=1)
    created_at = models.BigIntegerField()
    discussion_ends_at = models.BigIntegerField()
    deadline_at = models.BigIntegerField(null=True, blank=True)
    round_no = models.PositiveIntegerField(default=0)                # votações da Câmara abertas (principal + derrubada + reaberturas)
    president_id = models.BigIntegerField(null=True, blank=True)     # Presidente a quem a sanção foi dirigida
    decided_by_id = models.BigIntegerField(null=True, blank=True)    # quem sancionou/vetou (nulo = sanção automática)
    decided_at = models.BigIntegerField(null=True, blank=True)
    veto_justification = models.TextField(blank=True, default="")
    force_at = models.BigIntegerField(null=True, blank=True)         # `weekly tick` em que entra em vigor
    closed_at = models.BigIntegerField(null=True, blank=True)        # encerramento (rejeição, retirada, veto mantido, vigor)
    rejection_params = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["status", "deadline_at"]), models.Index(fields=["law_key", "id"])]
        constraints = [
            models.UniqueConstraint(fields=["scope"], condition=Q(status__in=_ACTIVE_VALUES), name="proposal_one_active_per_scope"),
            models.CheckConstraint(condition=Q(kind="revoke") | Q(params__isnull=False),
                                   name="proposal_change_has_params"),
        ]


class ProposalVersion(models.Model):
    """Versão da proposta (07 §07.25: parâmetros X de cada versão). Só se acrescenta."""

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    params = models.JSONField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    at = models.BigIntegerField()
    by_id = models.BigIntegerField()

    class Meta:
        ordering = ["proposal_id", "number"]
        constraints = [models.UniqueConstraint(fields=["proposal", "number"], name="proposalversion_unique_number")]


class VoteRound(models.Model):
    """Uma votação da Câmara com a composição CONGELADA (07 §07.7). `seats` = ids das cadeiras ocupadas no congelamento."""

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="rounds")
    number = models.PositiveIntegerField()
    kind = models.CharField(max_length=10, choices=_choices(RoundKind))
    status = models.CharField(max_length=8, choices=_choices(RoundStatus), default=RoundStatus.OPEN.value)
    seats = models.JSONField()
    seats_count = models.PositiveIntegerField()
    started_at = models.BigIntegerField()
    ends_at = models.BigIntegerField()
    closed_at = models.BigIntegerField(null=True, blank=True)
    tally = models.JSONField(null=True, blank=True)          # resultado estruturado (votos, exigido, regra)
    approved = models.BooleanField(null=True, blank=True)
    void_reason = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        ordering = ["proposal_id", "number"]
        constraints = [
            models.UniqueConstraint(fields=["proposal", "number"], name="voteround_unique_number"),
            models.UniqueConstraint(fields=["proposal"], condition=Q(status="open"), name="voteround_one_open_per_proposal"),
            models.CheckConstraint(condition=Q(seats_count__gt=0), name="voteround_has_seats"),
        ]


class VoteRecord(models.Model):
    """Voto nominal e público (07 §07.8). Alterar o voto ACRESCENTA um registro; vale o último do Deputado na votação."""

    round = models.ForeignKey(VoteRound, on_delete=models.CASCADE, related_name="records")
    deputy_id = models.BigIntegerField()
    choice = models.CharField(max_length=8, choices=_choices(Choice))
    at = models.BigIntegerField()

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["round", "deputy_id", "id"])]


class ProposalEvent(models.Model):
    """Histórico permanente (07 §07.25). Só se acrescenta."""

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="events")
    kind = models.CharField(max_length=20, choices=_choices(EventKind))
    at = models.BigIntegerField()
    actor_id = models.BigIntegerField(null=True, blank=True)
    data = models.JSONField(default=dict)

    class Meta:
        ordering = ["id"]


class Law(models.Model):
    """Estado vigente de uma lei do catálogo (07 §07.21-§07.22). Nunca apagada: a revogação marca `revoked_at`; o histórico está em `LawChange`."""

    key = models.CharField(max_length=80, unique=True)
    status = models.CharField(max_length=10, choices=_choices(LawStatus), default=LawStatus.IN_FORCE.value)
    params = models.JSONField()
    in_force_since = models.BigIntegerField()
    revoked_at = models.BigIntegerField(null=True, blank=True)
    proposal = models.ForeignKey(Proposal, on_delete=models.PROTECT, related_name="+")


class LawChange(models.Model):
    """Cada entrada em vigor (criação, alteração ou revogação). Imutável."""

    law_key = models.CharField(max_length=80)
    proposal = models.ForeignKey(Proposal, on_delete=models.PROTECT, related_name="law_changes")
    kind = models.CharField(max_length=8, choices=_choices(Kind))
    at = models.BigIntegerField()
    old_params = models.JSONField(null=True, blank=True)
    new_params = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["law_key", "id"])]


class Suggestion(models.Model):
    """Sugestão de Governador/Prefeito ao Presidente (07 §07.3). Não é proposta: o Presidente decide se a formaliza."""

    author_id = models.BigIntegerField()
    law_key = models.CharField(max_length=80)
    kind = models.CharField(max_length=8, choices=_choices(Kind))
    params = models.JSONField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=10, choices=_choices(SuggestionStatus), default=SuggestionStatus.PENDING.value)
    created_at = models.BigIntegerField()
    decided_at = models.BigIntegerField(null=True, blank=True)
    decided_by_id = models.BigIntegerField(null=True, blank=True)
    proposal = models.ForeignKey(Proposal, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["id"]
