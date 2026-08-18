from django.conf import settings
from django.db import models


class RegistroDeTrabalho(models.Model):
    """
    Histórico simples de cada vez que alguém trabalha. No MVP existe só
    o trabalho genérico (sem empresa/cargo formal); quando profissões
    existirem, esse registro ganha um campo apontando pro emprego formal.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="registros_de_trabalho"
    )
    # Nullable de propósito: assim, adicionar esse campo não exige um valor
    # default forçado pra registros antigos que já existiam antes dele.
    categoria = models.ForeignKey(
        "skills.CategoriaDeHabilidade",
        on_delete=models.PROTECT,
        related_name="registros_de_trabalho",
        null=True,
        blank=True,
    )
    energia_gasta = models.PositiveSmallIntegerField()
    dinheiro_ganho = models.DecimalField(max_digits=10, decimal_places=2)
    xp_ganho = models.PositiveSmallIntegerField(default=0)
    quando = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de trabalho"
        verbose_name_plural = "Registros de trabalho"
        ordering = ["-quando"]

    def __str__(self):
        return f"{self.usuario.username} trabalhou em {self.quando:%d/%m/%Y %H:%M}"
