from django.conf import settings
from django.db import models
from django.utils import timezone


class WorldClock(models.Model):
    """
    Estado do tempo do mundo. Singleton (pk = 1).

    O tempo de jogo é derivado de uma âncora:
        jogo(agora) = anchor_game + (agora_real - anchor_real) * velocidade
    Mudar a velocidade re-ancora no instante atual, então o tempo de jogo
    nunca pula nem volta.
    """

    anchor_real = models.DateTimeField()
    anchor_game = models.BigIntegerField(default=0)
    real_seconds_per_game_day = models.PositiveIntegerField(
        help_text="Segundos reais que duram 1 dia de jogo."
    )
    # Todos os ticks com instante <= este valor já foram processados no escopo "world".
    world_processed_until = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = "relógio do mundo"
        verbose_name_plural = "relógio do mundo"

    def __str__(self):
        return f"WorldClock(1 dia de jogo = {self.real_seconds_per_game_day}s)"

    @classmethod
    def load(cls, *, for_update=False) -> "WorldClock":
        """Retorna o singleton, criando-o na primeira chamada."""
        qs = cls.objects.select_for_update() if for_update else cls.objects
        obj = qs.filter(pk=1).first()
        if obj is None:
            obj, _ = cls.objects.get_or_create(
                pk=1,
                defaults={
                    "anchor_real": timezone.now(),
                    "anchor_game": 0,
                    "real_seconds_per_game_day": settings.POLIS_REAL_SECONDS_PER_GAME_DAY,
                },
            )
            if for_update:
                obj = cls.objects.select_for_update().get(pk=1)
        return obj

    def game_time_at(self, real_now) -> int:
        """Tempo de jogo (segundos) no instante real `real_now`. Só inteiros."""
        d = real_now - self.anchor_real
        elapsed_us = (d.days * 86_400 + d.seconds) * 1_000_000 + d.microseconds
        # elapsed_us * 86400 / (rspd * 1e6), em divisão inteira
        gained = (elapsed_us * 86_400) // (self.real_seconds_per_game_day * 1_000_000)
        return self.anchor_game + max(gained, 0)
