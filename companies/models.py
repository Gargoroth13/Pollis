"""
Modelos das Empresas (design/02). Esta etapa (P1.04a) entrega o núcleo: a empresa, o cargo Dono e o aporte de capital. Produção,
funcionários, mural, Varejo e Construtora entram em etapas seguintes, mantidas no escopo do Bot Test (`TASK_QUEUE.md`).

O dinheiro da empresa NÃO vive aqui: é a conta `COMPANY` do registro monetário (`ledger`, design/24), cujo dono é `Company.pk`.
"""
from django.db import models
from django.db.models import Q

from .constants import CompanyType, PositionKind


def _choices(enum_cls):
    return [(m.value, m.name) for m in enum_cls]


class CompaniesImmutableError(Exception):
    code = "COMPANIES_IMMUTABLE"


class Company(models.Model):
    name = models.CharField(max_length=80)
    type = models.CharField(max_length=16, choices=_choices(CompanyType))
    founder = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="founded_companies")
    stars = models.PositiveSmallIntegerField()                       # `[PROV]` inicial; evolução não definida no design
    founded_at = models.BigIntegerField()
    founding_sequence = models.IntegerField()                        # nº da fundação do fundador (1, 2, ...): chave estável
    founding_cost = models.BigIntegerField()                         # centavos efetivamente cobrados (02 §17)
    founding_key = models.CharField(max_length=120)
    explained = models.JSONField(default=dict, blank=True)           # `Explained.to_dict()` do custo (20)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["founder", "founding_sequence"], name="company_unique_founder_sequence"),
            models.CheckConstraint(condition=Q(stars__gte=1), name="company_stars_at_least_one"),
            models.CheckConstraint(condition=Q(founding_cost__gt=0), name="company_founding_cost_positive"),
        ]

    def __str__(self):
        return f"Company({self.pk}:{self.name})"


class Position(models.Model):
    """Cargo da empresa. O Dono (02 §16) existe desde a fundação, com o salário que o fundador definiu."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="positions")
    kind = models.CharField(max_length=16, choices=_choices(PositionKind))
    salary = models.BigIntegerField()                                # centavos; o teto real é S/T no pagamento (24 §24.12)
    holder = models.ForeignKey("players.Player", null=True, blank=True, on_delete=models.PROTECT, related_name="positions")
    created_at = models.BigIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["company"], condition=Q(kind=PositionKind.OWNER.value),
                                    name="position_one_owner_per_company"),
            models.CheckConstraint(condition=Q(salary__gte=0), name="position_salary_non_negative"),
            models.CheckConstraint(condition=~Q(kind=PositionKind.OWNER.value) | Q(holder__isnull=False),
                                   name="position_owner_has_holder"),
        ]


class CapitalContribution(models.Model):
    """Aporte do Dono ao caixa da empresa: dinheiro que JÁ existia, movido do jogador para a conta da empresa (24; sem dinheiro novo)."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="contributions")
    player = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="capital_contributions")
    sequence = models.IntegerField()                                 # nº do aporte na empresa: chave estável do lançamento
    amount = models.BigIntegerField()
    ledger_key = models.CharField(max_length=120)
    at = models.BigIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "sequence"], name="contribution_unique_company_sequence"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="contribution_amount_positive"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise CompaniesImmutableError("aportes são imutáveis")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise CompaniesImmutableError("aportes são imutáveis")
