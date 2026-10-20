"""
Modelos das Empresas (design/02). P1.04a: a empresa, o cargo Dono e o aporte. P1.04b: vagas/cargos, candidaturas, trilha de eventos e
salário de trabalho. Produção, Varejo e Construtora entram em etapas seguintes, mantidas no escopo do Bot Test (`TASK_QUEUE.md`).

O dinheiro da empresa NÃO vive aqui: é a conta `COMPANY` do registro monetário (`ledger`, design/24), cujo dono é `Company.pk`.
"""
from django.db import models
from django.db.models import Q

from .constants import ApplicationStatus, CompanyType, EventKind, PositionKind, PositionStatus


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
    """
    Cargo da empresa. O Dono (02 §16) existe desde a fundação, com o salário que o fundador definiu. Os demais cargos são VAGAS
    (02 §15): abertas pelo Dono, ocupadas por UM jogador por vez, com `status` coerente com o ocupante (restrição abaixo).

    `salary` (centavos): do Dono, valor devido POR DIA (folha diária); do funcionário, valor devido POR AÇÃO DE TRABALHO (01 §1.7:
    o limite é diário, não por clique). O teto real é S/T no pagamento (24 §24.12). `requirements` = {skill: nível mínimo} (01 §1.9).
    """

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="positions")
    kind = models.CharField(max_length=16, choices=_choices(PositionKind))
    salary = models.BigIntegerField()
    holder = models.ForeignKey("players.Player", null=True, blank=True, on_delete=models.PROTECT, related_name="positions")
    status = models.CharField(max_length=8, choices=_choices(PositionStatus), default=PositionStatus.FILLED.value)
    requirements = models.JSONField(default=dict, blank=True)
    created_at = models.BigIntegerField()
    hired_at = models.BigIntegerField(null=True, blank=True)
    closed_at = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["company"], condition=Q(kind=PositionKind.OWNER.value),
                                    name="position_one_owner_per_company"),
            models.CheckConstraint(condition=Q(salary__gte=0), name="position_salary_non_negative"),
            models.CheckConstraint(condition=~Q(kind=PositionKind.OWNER.value) | Q(holder__isnull=False),
                                   name="position_owner_has_holder"),
            # status coerente com o ocupante: FILLED <=> há ocupante
            models.CheckConstraint(
                condition=(Q(status=PositionStatus.FILLED.value, holder__isnull=False)
                           | (~Q(status=PositionStatus.FILLED.value) & Q(holder__isnull=True))),
                name="position_status_matches_holder"),
            # 02 §16: o Dono não conta para o limite de UM emprego contratado; qualquer outro cargo conta
            models.UniqueConstraint(fields=["holder"], condition=~Q(kind=PositionKind.OWNER.value) & Q(holder__isnull=False),
                                    name="position_one_job_per_player"),
            models.CheckConstraint(condition=Q(kind=PositionKind.OWNER.value) | Q(salary__gt=0),
                                   name="position_hired_salary_positive"),
        ]


class Application(models.Model):
    """Candidatura a uma vaga do mural (02 §15). Só o Dono decide (GD 2026-10-19; `02` §25.3)."""

    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="applications")
    applicant = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="applications")
    status = models.CharField(max_length=10, choices=_choices(ApplicationStatus), default=ApplicationStatus.PENDING.value)
    created_at = models.BigIntegerField()
    decided_at = models.BigIntegerField(null=True, blank=True)
    decided_by = models.ForeignKey("players.Player", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reason = models.CharField(max_length=40, blank=True, default="")
    explained = models.JSONField(default=dict, blank=True)         # requisitos no momento da candidatura (20)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["position", "applicant"], condition=Q(status=ApplicationStatus.PENDING.value),
                                    name="application_one_pending_per_position"),
        ]


class _Immutable(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise CompaniesImmutableError(f"{type(self).__name__} é imutável")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise CompaniesImmutableError(f"{type(self).__name__} é imutável")


class PositionEvent(_Immutable):
    """Trilha imutável do mural e do vínculo: abrir/fechar vaga, candidatura, contratação, saída (auditoria; 20)."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="events")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=20, choices=_choices(EventKind))
    # Ids simples, SEM chave estrangeira de propósito: inserir um evento não toma `FOR KEY SHARE` na linha de jogadores que a
    # operação não travou (a limpeza de candidaturas toca jogadores de fora do protocolo de travamento; ver `jobs`).
    subject = models.BigIntegerField(null=True, blank=True)       # jogador afetado
    actor = models.BigIntegerField(null=True, blank=True)         # quem agiu
    at = models.BigIntegerField()
    explained = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]


class WorkWage(_Immutable):
    """
    Salário devido por UMA ação de Trabalhar do funcionário (24 §24.13: o salário de trabalho nasce no ato). Liga a ação ao pedido
    de remuneração do registro monetário (`request_key`), onde estão o reconhecido, o pago, o pendente e o imposto.
    """

    player = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="work_wages")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="wages")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="wages")
    sequence = models.IntegerField()                                # nº do salário do jogador: chave estável do pedido
    due = models.BigIntegerField()
    request_key = models.CharField(max_length=120, unique=True)
    at = models.BigIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["player", "sequence"], name="workwage_unique_player_sequence"),
            models.CheckConstraint(condition=Q(due__gt=0), name="workwage_due_positive"),
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
