"""
Modelos das Empresas (design/02). P1.04a: a empresa, o cargo Dono e o aporte. P1.04b: vagas/cargos, candidaturas, trilha de eventos e
salário de trabalho. P1.04c: linha de produção, estoque empresarial e sua trilha. Varejo e Construtora entram em etapas seguintes, mantidas no escopo do Bot Test (`TASK_QUEUE.md`).

O dinheiro da empresa NÃO vive aqui: é a conta `COMPANY` do registro monetário (`ledger`, design/24), cujo dono é `Company.pk`.
"""
from django.db import models
from django.db.models import Q

from .constants import ApplicationStatus, CompanyType, EventKind, PositionKind, PositionStatus, StockOperation


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


class SupportWork(_Immutable):
    """
    Uma ação de Trabalhar de Engenheiro ou Advogado (02 §9): a contribuição ao efeito DIÁRIO da empresa (bônus de produção ou redução
    do risco de Burnout). Imutável; liga-se ao salário pago pela mesma ação (`player`, `sequence`). O efeito do dia é a soma por
    (empresa, cargo, `competence_day`): ele reinicia sozinho a cada dia, sem tarefa de limpeza.
    """

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="support_works")
    player = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="support_works")
    position = models.ForeignKey(Position, on_delete=models.PROTECT, related_name="support_works")
    kind = models.CharField(max_length=16, choices=_choices(PositionKind))      # engineer | lawyer
    sequence = models.IntegerField()                                # o MESMO nº do salário desta ação (WorkWage)
    competence_day = models.IntegerField()
    at = models.BigIntegerField()
    level = models.DecimalField(max_digits=14, decimal_places=6)
    specialization = models.DecimalField(max_digits=14, decimal_places=6)
    contribution = models.DecimalField(max_digits=18, decimal_places=6)
    explained = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["player", "sequence"], name="supportwork_unique_player_sequence"),
            models.CheckConstraint(condition=Q(contribution__gte=0), name="supportwork_contribution_gte_0"),
        ]
        indexes = [models.Index(fields=["company", "kind", "competence_day"], name="supportwork_company_day")]


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


class ProductionLine(models.Model):
    """
    O que a empresa produz AGORA (02 §5.1: um produto por vez, escolhido só pelo Dono). `setup_until` = fim do setup da última
    troca (empresa fora de operação, 02 §5.3); `cooldown_until` = quando poderá trocar de novo; `carry` = fração de unidade
    produzida que ainda não virou unidade inteira de estoque (a produção por trabalho é fracionária, o estoque é inteiro).
    """

    company = models.OneToOneField(Company, on_delete=models.PROTECT, related_name="line")
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    selected_at = models.BigIntegerField(null=True, blank=True)
    setup_until = models.BigIntegerField(null=True, blank=True)
    cooldown_until = models.BigIntegerField(null=True, blank=True)
    carry = models.DecimalField(max_digits=14, decimal_places=6, default=0)
    changes = models.IntegerField(default=0)                       # nº de seleções (a 1ª é a escolha inicial)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(carry__gte=0, carry__lt=1), name="line_carry_fraction"),
            models.CheckConstraint(condition=Q(product__isnull=False) | Q(changes=0), name="line_changes_need_product"),
        ]


class ProductionChange(_Immutable):
    """Cada escolha/troca de produto (02 §5.3): o que mudou, o custo cobrado e os prazos de setup e cooldown."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="production_changes")
    sequence = models.IntegerField()
    from_product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    to_product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    at = models.BigIntegerField()
    cost = models.BigIntegerField(default=0)                       # centavos
    setup_until = models.BigIntegerField(null=True, blank=True)    # None na escolha inicial
    cooldown_until = models.BigIntegerField(null=True, blank=True)
    actor = models.BigIntegerField()
    explained = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["company", "sequence"], name="productionchange_unique_sequence")]


class StockItem(models.Model):
    """
    Estoque empresarial agregado (05 §17): `quantity` unidades de `product`. Só existe com quantidade > 0. `quality` = média por
    unidade da qualidade das unidades em estoque (02 §8); NULL = não conhecida (nunca zero, 02: NULL ≠ 0).
    """

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="stock")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="company_stock")
    quantity = models.BigIntegerField()
    quality = models.DecimalField(max_digits=32, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["company_id", "product_id"]
        constraints = [
            models.UniqueConstraint(fields=["company", "product"], name="stockitem_unique_company_product"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="stockitem_quantity_positive"),
        ]


class StockMovement(_Immutable):
    """Trilha IMUTÁVEL do estoque (05 §19): `StockItem.quantity` é cache; a verdade auditável é a soma dos movimentos."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="stock_movements")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    delta = models.BigIntegerField()
    quantity_after = models.BigIntegerField()
    quality_after = models.DecimalField(max_digits=32, decimal_places=6, null=True, blank=True)
    operation = models.CharField(max_length=20, choices=_choices(StockOperation))
    key = models.CharField(max_length=160, unique=True)
    reference_kind = models.CharField(max_length=40)
    reference_id = models.CharField(max_length=120)
    origin = models.CharField(max_length=60)
    destination = models.CharField(max_length=60)
    actor = models.BigIntegerField(null=True, blank=True)          # jogador cujo trabalho/ação gerou o movimento
    at = models.BigIntegerField()
    explained = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(condition=~Q(delta=0), name="stockmovement_delta_nonzero")]
