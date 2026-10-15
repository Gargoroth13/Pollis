from django.db import models
from django.db.models import Q

from geography.constants import RESOURCE_NAMES

from .constants import Category, Channel, NutritionLevel, QolEffect, Sector


def _choices(enum_cls):
    return [(m.value, m.name) for m in enum_cls]


class Product(models.Model):
    """
    Produto do catálogo central (design/22). Estoque de empresa e inventário de jogador REFERENCIAM este modelo, sem
    copiá-lo (05 §17).

    `key` é a IDENTIDADE PERMANENTE: estável e independente do nome (decisão do GD, 2026-10-11). O `name` é apresentação e
    pode mudar; a `key` não pode (o `save` recusa). Vários campos são anuláveis de propósito: NULL = NÃO ESPECIFICADO pelo
    design, que é diferente de zero.
    """

    key = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    sector = models.CharField(max_length=32, choices=_choices(Sector))
    # Estrela mínima da empresa (02 §14). NULL = não especificada (Matrizes) ou não se aplica (milícia, compra do governo).
    min_stars = models.PositiveSmallIntegerField(null=True, blank=True)
    # Matéria-prima que é recurso espacial da Geografia (08 §15): valor de geography.constants.Resource.
    resource = models.CharField(max_length=32, null=True, blank=True, unique=True,
                                choices=[(n, n) for n in sorted(RESOURCE_NAMES)])
    # Classificação (GD 2026-10-14, Q6): UMA categoria principal; tags em campos separados. "Usável em receita" é DERIVADO.
    # Vazio = ainda não classificado (a validação do catálogo o recusa como CATEGORY_MISSING).
    category = models.CharField(max_length=16, choices=_choices(Category), blank=True, default="")
    is_consumable = models.BooleanField(default=False)
    is_permanent = models.BooleanField(default=False)
    is_military = models.BooleanField(default=False)
    # Canais comerciais DECLARADOS (Q8): lista de valores de constants.Channel. Nenhum canal é inferido.
    commercial_channels = models.JSONField(default=list, blank=True)
    # Valores provisórios [PROV] (provisional.py): preço-base de REFERÊNCIA (não é preço de mercado) e rendimento da Matriz.
    base_price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    raw_yield = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    # Rastreabilidade com o design: onde está no 22 e como o nome aparece lá (antes da normalização).
    source_section = models.CharField(max_length=120, blank=True, default="")
    source_names = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(min_stars__isnull=True) | Q(min_stars__gte=1, min_stars__lte=5),
                                   name="product_min_stars_1_to_5"),
            models.CheckConstraint(condition=Q(base_price__isnull=True) | Q(base_price__gte=0),
                                   name="product_base_price_non_negative_or_unspecified"),
            models.CheckConstraint(condition=Q(raw_yield__isnull=True) | Q(raw_yield__gt=0),
                                   name="product_raw_yield_positive_or_unspecified"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk is not None:
            old = type(self).objects.filter(pk=self.pk).values_list("key", flat=True).first()
            if old is not None and old != self.key:
                raise ValueError(f"A chave do produto é permanente ({old!r} -> {self.key!r}); mude só o nome.")
        super().save(*args, **kwargs)


class Recipe(models.Model):
    """Receita de um produto (uma por produto, como no 22). Matéria-prima e compra do governo não têm receita."""

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="recipe")
    # Unidades produzidas por execução da receita. NULL = não especificado pelo design (≠ 0).
    yield_quantity = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(yield_quantity__isnull=True) | Q(yield_quantity__gt=0),
                                   name="recipe_yield_positive_or_unspecified"),
        ]

    def __str__(self):
        return f"Receita({self.product.key})"


class RecipeInput(models.Model):
    """Insumo da receita, na ordem em que o 22 lista. `quantity` NULL = não especificada (≠ 0)."""

    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="inputs")
    ingredient = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="used_in")
    position = models.PositiveSmallIntegerField()
    quantity = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        ordering = ["recipe_id", "position"]
        constraints = [
            models.UniqueConstraint(fields=["recipe", "ingredient"], name="recipeinput_unique_ingredient"),
            models.UniqueConstraint(fields=["recipe", "position"], name="recipeinput_unique_position"),
            models.CheckConstraint(condition=Q(quantity__isnull=True) | Q(quantity__gt=0),
                                   name="recipeinput_quantity_positive_or_unspecified"),
        ]


class FoodProfile(models.Model):
    """
    Perfil de alimento (22 §2.3, colunas Nutrição e Efeito de QoL). Os níveis são QUALITATIVOS; os números não existem no
    22 e ficam NULL (não especificado, ≠ 0). A intensidade é uma magnitude (>= 0): o sentido vem de `qol_effect`.
    """

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="food")
    nutrition_level = models.CharField(max_length=16, choices=_choices(NutritionLevel))
    qol_effect = models.CharField(max_length=16, choices=_choices(QolEffect))
    nutrition_amount = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    qol_intensity = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(nutrition_amount__isnull=True) | Q(nutrition_amount__gte=0),
                                   name="food_nutrition_non_negative_or_unspecified"),
            models.CheckConstraint(condition=Q(qol_intensity__isnull=True) | Q(qol_intensity__gte=0),
                                   name="food_qol_intensity_non_negative_or_unspecified"),
        ]
