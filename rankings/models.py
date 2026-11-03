from django.db import models
from django.db.models import F, Q

from .constants import ENTITY_TYPES, HISTORICAL


class RankingHistorico(models.Model):
    """
    Recorde atual de UMA categoria histórica (design/14 §14.5): estrutura genérica, sem uma tabela por ranking.
    O recorde anterior é substituído (não há histórico de estados); `metadata` guarda o necessário à auditoria da categoria.
    Substituição só por valor ESTRITAMENTE maior: em empate fica quem chegou primeiro.
    Instantes em tempo de jogo (segundos).
    """

    category = models.CharField(max_length=32, unique=True, choices=[(c.key.value, c.label) for c in HISTORICAL])
    entity_type = models.CharField(max_length=16, choices=[(t, t) for t in ENTITY_TYPES])
    entity_id = models.BigIntegerField()
    value = models.BigIntegerField()                  # unidade da categoria (centavos, segundos, partes por milhão)
    recorded_at = models.BigIntegerField()            # quando o recorde foi ESTABELECIDO (14.4)
    updated_at = models.BigIntegerField()             # quando o registro foi gravado pela última vez (14.9)
    metadata = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(value__gte=0), name="rankinghistorico_value_gte_0"),
            models.CheckConstraint(condition=Q(updated_at__gte=F("recorded_at")), name="rankinghistorico_updated_after_recorded"),
        ]

    def __str__(self):
        return f"RankingHistorico({self.category}: {self.entity_type}#{self.entity_id}={self.value})"


class ActivityStreak(models.Model):
    """
    Sequência de atividade de uma conta (design/14 §14.3.11). Uma linha por jogador.
    A atividade é uma AÇÃO VÁLIDA (execução bem-sucedida pelo Action Registry), não login nem navegação.
    O período de uma sequência é `última ação − primeira ação` da sequência; a sequência continua enquanto o intervalo entre
    duas ações consecutivas for INFERIOR a 72 h. Guarda a sequência corrente e a MELHOR já alcançada pela conta.
    """

    player = models.OneToOneField("players.Player", on_delete=models.CASCADE, related_name="activity_streak")
    current_start = models.BigIntegerField()
    last_action_at = models.BigIntegerField()
    best_start = models.BigIntegerField()
    best_end = models.BigIntegerField()
    best_length = models.BigIntegerField()            # segundos: best_end − best_start

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(last_action_at__gte=F("current_start")), name="activitystreak_current_ordered"),
            models.CheckConstraint(condition=Q(best_end__gte=F("best_start")), name="activitystreak_best_ordered"),
            models.CheckConstraint(condition=Q(best_length=F("best_end") - F("best_start")), name="activitystreak_best_length"),
            models.CheckConstraint(condition=Q(best_length__gte=F("last_action_at") - F("current_start")),
                                   name="activitystreak_best_not_below_current"),
        ]
        indexes = [models.Index(fields=["-best_length", "player"], name="activitystreak_rank_idx")]

    def __str__(self):
        return f"ActivityStreak(player={self.player_id}, best={self.best_length}s)"
