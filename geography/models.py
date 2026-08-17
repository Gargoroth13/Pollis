from django.db import models


class Estado(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    sigla = models.CharField(max_length=2, unique=True)

    class Meta:
        verbose_name = "Estado"
        verbose_name_plural = "Estados"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Cidade(models.Model):
    nome = models.CharField(max_length=100)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT, related_name="cidades")

    class Meta:
        verbose_name = "Cidade"
        verbose_name_plural = "Cidades"
        unique_together = ("nome", "estado")
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.estado.sigla})"


class Bairro(models.Model):
    """
    Cada bairro tem uma faixa de renda predominante (usada para sortear
    onde um jogador novo nasce) e um score de qualidade de vida (QoL)
    que futuramente vai gerar buffs/debuffs pros moradores.
    """

    class FaixaRenda(models.TextChoices):
        BAIXA = "baixa", "Baixa renda"
        MEDIA = "media", "Média renda"
        ALTA = "alta", "Alta renda"

    nome = models.CharField(max_length=100)
    cidade = models.ForeignKey(Cidade, on_delete=models.PROTECT, related_name="bairros")

    # Coordenadas dentro da grade da cidade. (0,0) é reservado pro bairro da prefeitura.
    grid_x = models.IntegerField()
    grid_y = models.IntegerField()

    faixa_renda = models.CharField(max_length=10, choices=FaixaRenda.choices)

    # Score de 0 a 100. Começa num valor base ligado à faixa de renda,
    # mas vai ser recalculado depois com base em infraestrutura real
    # (escolas, hospitais, segurança etc), que ainda não existem no MVP.
    qualidade_vida = models.PositiveSmallIntegerField(default=50)

    e_bairro_da_prefeitura = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Bairro"
        verbose_name_plural = "Bairros"
        unique_together = ("cidade", "grid_x", "grid_y")
        ordering = ["cidade", "grid_y", "grid_x"]

    def __str__(self):
        return f"{self.nome} ({self.grid_x},{self.grid_y}) - {self.cidade}"
