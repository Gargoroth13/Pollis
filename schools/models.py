"""
Escolas (design/03): escola (pública/particular), matrícula do aluno, materiais (estoque da escola, com trilha imutável) e a qualidade
de cada dia (retrato dos materiais do ciclo anterior + bônus dos professores).
"""
from django.db import models
from django.db.models import Q

from .constants import MAX_STARS, MIN_STARS, EnrollmentEnd, MaterialOperation, SchoolKind


def _choices(enum_cls):
    return [(m.value, m.name) for m in enum_cls]


class SchoolsImmutableError(Exception):
    code = "SCHOOLS_IMMUTABLE"


class _Immutable(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise SchoolsImmutableError(f"{type(self).__name__} é imutável")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise SchoolsImmutableError(f"{type(self).__name__} é imutável")


class School(models.Model):
    """
    Escola (03 §3). Pública (sem dono: orçamento do governo, P1.09) ou particular (dono = diretor, 03 §6). `materials` é CACHE do
    estoque: a verdade auditável é a soma de `MaterialMovement`. `initial` marca a escola pública de origem do bairro (uma só).
    """

    neighborhood = models.ForeignKey("geography.Neighborhood", on_delete=models.PROTECT, related_name="schools")
    kind = models.CharField(max_length=10, choices=_choices(SchoolKind))
    name = models.CharField(max_length=80)
    stars = models.PositiveSmallIntegerField()
    owner = models.ForeignKey("players.Player", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    initial = models.BooleanField(default=False)
    materials = models.BigIntegerField(default=0)
    created_at = models.BigIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(stars__gte=MIN_STARS, stars__lte=MAX_STARS), name="school_stars_valid"),
            models.CheckConstraint(condition=Q(materials__gte=0), name="school_materials_non_negative"),
            models.CheckConstraint(
                condition=(Q(kind=SchoolKind.PUBLIC.value, owner__isnull=True) | Q(kind=SchoolKind.PRIVATE.value, owner__isnull=False)),
                name="school_owner_matches_kind"),
            models.CheckConstraint(condition=Q(initial=False) | Q(kind=SchoolKind.PUBLIC.value), name="school_initial_is_public"),
            models.UniqueConstraint(fields=["neighborhood"], condition=Q(initial=True), name="school_one_initial_per_neighborhood"),
        ]
        indexes = [models.Index(fields=["neighborhood", "kind"], name="school_neighborhood_kind")]


class Enrollment(models.Model):
    """Matrícula do aluno (03 §2). No máximo UMA ativa por jogador; as encerradas ficam como histórico contínuo."""

    player = models.ForeignKey("players.Player", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="enrollments")
    started_at = models.BigIntegerField()
    ended_at = models.BigIntegerField(null=True, blank=True)
    end_reason = models.CharField(max_length=12, blank=True, default="", choices=[("", "")] + _choices(EnrollmentEnd))

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["player"], condition=Q(ended_at__isnull=True), name="enrollment_one_active_per_player"),
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gte=models.F("started_at")),
                                   name="enrollment_end_after_start"),
            models.CheckConstraint(condition=(Q(ended_at__isnull=True, end_reason="") | (Q(ended_at__isnull=False) & ~Q(end_reason=""))),
                                   name="enrollment_end_reason_iff_ended"),
        ]
        indexes = [models.Index(fields=["school", "ended_at"], name="enrollment_school_active")]


class MaterialMovement(_Immutable):
    """Trilha imutável dos materiais da escola (03 §8-9): entradas por compra e decaimento diário."""

    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="material_movements")
    delta = models.BigIntegerField()
    quantity_after = models.BigIntegerField()
    operation = models.CharField(max_length=10, choices=_choices(MaterialOperation))
    key = models.CharField(max_length=160, unique=True)
    reference_kind = models.CharField(max_length=40)
    reference_id = models.CharField(max_length=120)
    origin = models.CharField(max_length=60)
    at = models.BigIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=~Q(delta=0), name="materialmovement_delta_nonzero"),
            models.CheckConstraint(condition=Q(quantity_after__gte=0), name="materialmovement_after_non_negative"),
        ]
        indexes = [models.Index(fields=["school", "at"], name="materialmovement_school_at")]


class QualityDay(_Immutable):
    """
    Qualidade da escola num dia (03 §7, §12): Qualidade Base (retrato dos materiais do ciclo ANTERIOR) + bônus dos professores do
    dia anterior. Uma linha por escola e dia de competência; imutável.
    """

    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="quality_days")
    day = models.IntegerField()
    materials_snapshot = models.BigIntegerField()
    base_quality = models.DecimalField(max_digits=32, decimal_places=6)
    teacher_bonus = models.DecimalField(max_digits=32, decimal_places=6, default=0)
    quality = models.DecimalField(max_digits=32, decimal_places=6)
    explained = models.JSONField(default=dict, blank=True)
    computed_at = models.BigIntegerField()

    class Meta:
        ordering = ["day", "school_id"]
        constraints = [models.UniqueConstraint(fields=["school", "day"], name="qualityday_unique")]
