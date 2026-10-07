from django.db import models
from django.db.models import F, Q


class PlayerLocation(models.Model):
    """
    Lote onde o jogador está (04 §24: o jogador "possui localização inicial física no mundo"). TODO jogador tem um.

    Durante uma viagem o lote continua sendo o de ORIGEM: o design não define posição intermediária e o 04 §20 só diz que
    o jogador não pode executar ações que dependam de presença física enquanto viaja. A chegada atualiza este lote.
    """

    player = models.OneToOneField("players.Player", on_delete=models.CASCADE, related_name="location")
    lot = models.ForeignKey("geography.Lot", on_delete=models.PROTECT, related_name="+")


class Journey(models.Model):
    """
    Uma viagem entre dois lotes (04 §20). No máximo UMA ativa por jogador; as concluídas ficam como histórico.

    NÃO guarda a distância nem o tempo-base: 04 §21 — "a distância deve ser fornecida pela Geografia e não armazenada
    como atributo independente". O que se guarda é o que a viagem É: origem, destino e os instantes (tempo de jogo, 04 §20).
    `arrives_at` é fixado na partida (mudar o parâmetro depois não altera uma viagem em curso).
    """

    player = models.ForeignKey("players.Player", on_delete=models.CASCADE, related_name="journeys")
    origin = models.ForeignKey("geography.Lot", on_delete=models.PROTECT, related_name="+")
    destination = models.ForeignKey("geography.Lot", on_delete=models.PROTECT, related_name="+")
    departed_at = models.BigIntegerField()
    arrives_at = models.BigIntegerField()
    completed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player"], condition=Q(completed=False), name="journey_one_active_per_player"),
            models.CheckConstraint(condition=Q(arrives_at__gt=F("departed_at")), name="journey_arrives_after_departure"),
            models.CheckConstraint(condition=~Q(origin=F("destination")), name="journey_origin_differs_from_destination"),
        ]
        indexes = [models.Index(fields=["player", "completed"])]
