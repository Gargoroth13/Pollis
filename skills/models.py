from django.db import models

from .constants import SKILL_NAMES


class PlayerSkill(models.Model):
    """
    Nível de UMA das 3 skills de um jogador (01 §1). Um registro por (jogador, skill).

    SEM TETO: a progressão é infinita (01 §1.10). A coluna é larga de propósito (26 dígitos inteiros)
    e nenhuma regra faz clamp superior. O nível é fracionário porque os ganhos são fracionários.
    """

    player = models.ForeignKey("players.Player", on_delete=models.CASCADE, related_name="skills")
    skill = models.CharField(max_length=16)
    level = models.DecimalField(max_digits=32, decimal_places=6, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player", "skill"], name="playerskill_unique"),
            models.CheckConstraint(condition=models.Q(level__gte=0), name="playerskill_level_gte_0"),
            models.CheckConstraint(condition=models.Q(skill__in=sorted(SKILL_NAMES)), name="playerskill_one_of_three"),
        ]


class Specialization(models.Model):
    """
    Especialização por atividade/produto (02 §13): distinta das skills.

    `key` é opaco (atividade ou produto: o catálogo pertence a outros sistemas).
    `historic_max` sustenta o piso de 50% (02 §13). `last_used_day` é o dia de calendário do jogo
    (ordinal na time zone do jogo) do último trabalho nessa área e alimenta a decadência diária.
    """

    player = models.ForeignKey("players.Player", on_delete=models.CASCADE, related_name="specializations")
    key = models.CharField(max_length=64)
    value = models.DecimalField(max_digits=32, decimal_places=6, default=0)
    historic_max = models.DecimalField(max_digits=32, decimal_places=6, default=0)
    last_used_day = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player", "key"], name="specialization_unique"),
            models.CheckConstraint(condition=models.Q(value__gte=0), name="specialization_value_gte_0"),
            models.CheckConstraint(condition=models.Q(historic_max__gte=models.F("value")), name="specialization_max_gte_value"),
        ]
