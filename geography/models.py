from django.db import models

from .constants import CATEGORY_NAMES, RESOURCE_NAMES, Occupation


class State(models.Model):
    """Estado: maior divisão territorial (08 §2). Posição X/Y própria; a distância vem das coordenadas."""

    name = models.CharField(max_length=80, unique=True)
    x = models.DecimalField(max_digits=12, decimal_places=3)
    y = models.DecimalField(max_digits=12, decimal_places=3)
    # Uma capital estadual (08 §2). Nula só durante a geração (a capital é uma das cidades do estado).
    capital = models.ForeignKey("City", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    def __str__(self):
        return self.name


class City(models.Model):
    """Cidade (08 §3): coordenadas X/Y, conjunto de bairros."""

    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="cities")
    index = models.PositiveIntegerField()
    name = models.CharField(max_length=80)
    x = models.DecimalField(max_digits=12, decimal_places=3)
    y = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["state", "index"], name="city_unique_index_in_state")]

    def __str__(self):
        return self.name


class Neighborhood(models.Model):
    """
    Bairro (08 §4): principal unidade para regras locais. `zoning` é o tipo PREDOMINANTE de zoneamento.
    NÃO existe classe social do bairro (08 §4, §23.5): condição econômica emerge dos outros sistemas.
    `index` cresce do centro para a periferia.
    """

    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="neighborhoods")
    index = models.PositiveIntegerField()
    name = models.CharField(max_length=80)
    x = models.DecimalField(max_digits=12, decimal_places=3)
    y = models.DecimalField(max_digits=12, decimal_places=3)
    zoning = models.CharField(max_length=16)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["city", "index"], name="neighborhood_unique_index_in_city"),
            models.CheckConstraint(condition=models.Q(zoning__in=sorted(CATEGORY_NAMES)), name="neighborhood_zoning_valid"),
        ]

    def __str__(self):
        return self.name

    def lot_capacity(self):
        """Capacidade REAL do bairro por categoria: derivada dos lotes (nunca guardada em duplicidade)."""
        counts = dict(self.lots.values_list("category").annotate(n=models.Count("id")).order_by("category"))
        return counts


class Lot(models.Model):
    """
    Lote (08 §5): menor unidade territorial física. Pertence a um único bairro. `category` é a sua categoria de
    uso (e o seu zoneamento-base). A PROPRIEDADE (inicialmente do governo, 10 §2) e o imóvel pertencem ao sistema
    de Imóveis; aqui só existe o estado de ocupação.
    """

    neighborhood = models.ForeignKey(Neighborhood, on_delete=models.CASCADE, related_name="lots")
    index = models.PositiveIntegerField()
    category = models.CharField(max_length=16)
    x = models.DecimalField(max_digits=12, decimal_places=3)
    y = models.DecimalField(max_digits=12, decimal_places=3)
    occupation = models.CharField(max_length=16, default=Occupation.EMPTY.value)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["neighborhood", "index"], name="lot_unique_index_in_neighborhood"),
            models.CheckConstraint(condition=models.Q(category__in=sorted(CATEGORY_NAMES)), name="lot_category_valid"),
            models.CheckConstraint(condition=models.Q(occupation__in=[o.value for o in Occupation]), name="lot_occupation_valid"),
        ]
        indexes = [models.Index(fields=["category"])]


class ResourceDeposit(models.Model):
    """
    Depósito de recurso natural num lote (08 §5, §13). `richness` (0, 1] é o tamanho relativo ao lote mais rico
    daquele recurso; a conversão para quantidades pertence a Produtos/Empresas (22), não à Geografia.
    """

    lot = models.ForeignKey(Lot, on_delete=models.CASCADE, related_name="deposits")
    resource = models.CharField(max_length=16)
    richness = models.DecimalField(max_digits=4, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lot", "resource"], name="deposit_unique_per_lot"),
            models.CheckConstraint(condition=models.Q(resource__in=sorted(RESOURCE_NAMES)), name="deposit_resource_valid"),
            models.CheckConstraint(condition=models.Q(richness__gt=0, richness__lte=1), name="deposit_richness_in_0_1"),
        ]
