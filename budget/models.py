from django.db import models
from django.db.models import Q

from .constants import Area, DecisionKind, Level, PlanStatus


def _choices(enum_cls):
    return [(m.value, m.value) for m in enum_cls]


class GovernmentDecision(models.Model):
    """
    Decisão política de um governo, REGISTRADA E PÚBLICA (09 §27, §34). Só se acrescenta: não há edição nem exclusão pelo serviço.
    `territory_id` é o id do Estado/Município (0 = União). `data` guarda os fatores da decisão (origem, destino, valor, Explained).
    """

    kind = models.CharField(max_length=20, choices=_choices(DecisionKind))
    level = models.CharField(max_length=16, choices=_choices(Level))
    territory_id = models.BigIntegerField(default=0)
    actor_id = models.BigIntegerField()
    at = models.BigIntegerField()
    competence_day = models.IntegerField()
    data = models.JSONField(default=dict)
    ledger_key = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["level", "territory_id", "id"])]


class BudgetPlan(models.Model):
    """Distribuição do orçamento MUNICIPAL entre as áreas num período de 30 dias (09 §5, §27). Rascunho até a confirmação, que confere os pisos."""

    city = models.ForeignKey("geography.City", on_delete=models.PROTECT, related_name="budget_plans")
    period = models.IntegerField()
    status = models.CharField(max_length=12, choices=_choices(PlanStatus), default=PlanStatus.DRAFT.value)
    created_at = models.BigIntegerField()
    confirmed_at = models.BigIntegerField(null=True, blank=True)
    confirmed_by_id = models.BigIntegerField(null=True, blank=True)
    confirmed_total = models.BigIntegerField(null=True, blank=True)       # soma das linhas na confirmação (a auditoria a confere)
    confirmation = models.JSONField(null=True, blank=True)                # fatores da confirmação: base, pisos, disponível (Explained)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["city", "period"], name="budgetplan_one_per_city_period"),
            models.CheckConstraint(condition=Q(status="draft") | (Q(confirmed_at__isnull=False) & Q(confirmed_total__isnull=False)),
                                   name="budgetplan_confirmed_has_facts"),
        ]


class BudgetPlanLine(models.Model):
    plan = models.ForeignKey(BudgetPlan, on_delete=models.CASCADE, related_name="lines")
    area = models.CharField(max_length=20, choices=_choices(Area))
    amount_cents = models.BigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["plan", "area"], name="budgetplanline_one_per_area"),
            models.CheckConstraint(condition=Q(amount_cents__gte=0), name="budgetplanline_amount_not_negative"),
        ]
