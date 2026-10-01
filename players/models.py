from django.conf import settings
from django.db import models

FOOD = "food"        # categoria "Comida" (04 §4.4, §16)
LEISURE = "leisure"  # categoria "Lazer"  (04 §4.4, §19)


class Player(models.Model):
    """
    Estado base do jogador (design/04). Jogadores reais e bots usam o MESMO modelo
    (design/21: mesma regra de jogo + mesma Action Registry + agentes diferentes).

    Guarda só ESTADO. QoL Base e QoL Atual NÃO são guardadas: são derivadas (players/qol.py),
    o que garante que a penalidade do Burnout e os efeitos temporários terminam sozinhos e que
    "o valor estrutural da QoL Base não é destruído nem reescrito pelo Burnout" (04 §7.3).

    Todos os instantes são TEMPO DE JOGO em segundos (core/timeline.py).
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="player")

    energy = models.DecimalField(max_digits=14, decimal_places=6)
    health = models.DecimalField(max_digits=14, decimal_places=6)
    nutrition = models.DecimalField(max_digits=14, decimal_places=6)
    burnout = models.DecimalField(max_digits=14, decimal_places=6, default=0)

    # Estados com histerese: dependem do passado, por isso são guardados (04 §7.3, §12).
    burnout_active = models.BooleanField(default=False)
    health_critical = models.BooleanField(default=False)
    hospitalized_until = models.BigIntegerField(null=True, blank=True)  # 04 §14: Saúde = 0

    # Última ação de trabalho: a recuperação natural de Burnout só começa 1 h depois (04 §7.2).
    last_work_at = models.BigIntegerField(null=True, blank=True)

    # Ponteiro do processamento lazy por ciclos de 10 min (04 §22): tudo <= isto já foi processado.
    processed_until = models.BigIntegerField()
    created_at_game = models.BigIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(energy__gte=0), name="player_energy_gte_0"),
            models.CheckConstraint(condition=models.Q(health__gte=0), name="player_health_gte_0"),
            models.CheckConstraint(condition=models.Q(nutrition__gte=0), name="player_nutrition_gte_0"),
            models.CheckConstraint(condition=models.Q(burnout__gte=0), name="player_burnout_gte_0"),
        ]

    def __str__(self):
        return f"Player({self.user_id})"

    def is_hospitalized(self, at: int) -> bool:
        return self.hospitalized_until is not None and at < self.hospitalized_until


class QolEffect(models.Model):
    """
    Efeito TEMPORÁRIO sobre a QoL Atual (04 §4.3-4.4).

    No máximo UM efeito por categoria por jogador: aplicar outro da mesma categoria SUBSTITUI o
    anterior, não soma (04 §4.4, §16, §19). Efeitos de categorias diferentes coexistem.
    Ativo em [starts_at, expires_at); a duração é lazy (04 §22), não exige tick.
    `amount` é aditivo e pode ser negativo (04 §18: alimentos com efeito negativo).
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="qol_effects")
    category = models.CharField(max_length=32)
    source = models.CharField(max_length=64, help_text="Origem do efeito (ex.: 'food:chocolate').")
    amount = models.DecimalField(max_digits=10, decimal_places=6)
    starts_at = models.BigIntegerField()
    expires_at = models.BigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player", "category"], name="qoleffect_one_per_category"),
            models.CheckConstraint(condition=models.Q(expires_at__gt=models.F("starts_at")), name="qoleffect_expires_after_start"),
        ]
