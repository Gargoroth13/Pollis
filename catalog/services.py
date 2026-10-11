"""
Consultas e verificações sobre o catálogo gravado. TUDO é derivado das receitas e do perfil de alimento: não existe lista
paralela de "quem compra o quê" (02 §4, §20).

Regras de honestidade (decisão do Game Director, 2026-10-11):
  - valor NÃO ESPECIFICADO é `None`, nunca zero; nenhuma função converte `None` em 0;
  - uso NÃO declarado não concede permissão: `uses_of` devolve só o que o catálogo declara, e o que não está nele não
    existe para fins de compra/venda;
  - quem precisa de um número que o design ainda não deu RECUSA com `UNSPECIFIED_DESIGN_VALUE` (e diz quais faltam), em
    vez de seguir em silêncio. Recusas são códigos (ActionResult), como no resto do projeto.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import FrozenSet, List, Optional, Tuple

from players.services import ActionResult

from .constants import NO_STAR_SECTORS, NutritionLevel, QolEffect, Sector, UseKind
from .models import Product


@dataclass(frozen=True)
class InputView:
    key: str
    name: str
    quantity: Optional[Decimal]          # None = não especificado


@dataclass(frozen=True)
class RecipeView:
    product_key: str
    inputs: Tuple[InputView, ...]
    yield_quantity: Optional[Decimal]    # None = não especificado

    @property
    def fully_specified(self) -> bool:
        return self.yield_quantity is not None and all(i.quantity is not None for i in self.inputs)


@dataclass(frozen=True)
class ProductUse:
    kind: UseKind
    target_key: Optional[str] = None       # RECIPE_INPUT: o produto cuja receita consome este
    quantity: Optional[Decimal] = None     # RECIPE_INPUT: quantidade por receita (None = não especificada)


@dataclass(frozen=True)
class FoodView:
    nutrition_level: NutritionLevel
    qol_effect: QolEffect
    nutrition_amount: Optional[Decimal]
    qol_intensity: Optional[Decimal]


def get_product(key: str) -> Optional[Product]:
    return Product.objects.filter(key=key).first()


def products_in_sector(sector: Sector) -> List[Product]:
    return list(Product.objects.filter(sector=sector.value).order_by("id"))


def product_for_resource(resource) -> Optional[Product]:
    """Matéria-prima do catálogo que corresponde a um recurso espacial da Geografia (08 §15). Aceita o enum ou o valor."""
    value = getattr(resource, "value", resource)
    return Product.objects.filter(resource=value).first()


def recipe_of(key: str) -> Optional[RecipeView]:
    p = Product.objects.filter(key=key).select_related("recipe").first()
    recipe = getattr(p, "recipe", None) if p is not None else None
    if recipe is None:
        return None
    inputs = tuple(InputView(i.ingredient.key, i.ingredient.name, i.quantity)
                   for i in recipe.inputs.select_related("ingredient").order_by("position"))
    return RecipeView(key, inputs, recipe.yield_quantity)


def food_of(key: str) -> Optional[FoodView]:
    p = Product.objects.filter(key=key).select_related("food").first()
    food = getattr(p, "food", None) if p is not None else None
    if food is None:
        return None
    return FoodView(NutritionLevel(food.nutrition_level), QolEffect(food.qol_effect), food.nutrition_amount,
                    food.qol_intensity)


def uses_of(key: str) -> List[ProductUse]:
    """
    Usos DECLARADOS do produto, derivados: insumo de receitas (ordenado pela chave do produto-alvo) e consumo como alimento.
    Lista vazia = nenhum uso declarado = NENHUMA permissão de compra/venda por inferência.
    """
    from .models import RecipeInput
    uses = [ProductUse(UseKind.RECIPE_INPUT, ri.recipe.product.key, ri.quantity)
            for ri in RecipeInput.objects.filter(ingredient__key=key).select_related("recipe__product")]
    uses.sort(key=lambda u: u.target_key)
    if food_of(key) is not None:
        uses.append(ProductUse(UseKind.PLAYER_CONSUMPTION))
    return uses


def has_declared_use(key: str) -> bool:
    return bool(uses_of(key))


def consumers_of(key: str) -> List[str]:
    """Chaves dos produtos cuja receita consome este (a base de 02 §4: quem tem uso válido para o produto)."""
    return [u.target_key for u in uses_of(key) if u.kind == UseKind.RECIPE_INPUT]


def raw_materials_of(key: str) -> FrozenSet[str]:
    """Matérias-primas (transitivas) que sustentam o produto (uma matéria-prima devolve a si mesma). SÓ estrutura: sem
    quantidades (o 22 não as dá)."""
    seen, raw, stack = set(), set(), [key]
    while stack:
        k = stack.pop()
        if k in seen:
            continue
        seen.add(k)
        recipe = recipe_of(k)
        if recipe is None:
            raw.add(k)
        else:
            stack.extend(i.key for i in recipe.inputs)
    return frozenset(raw)


def check_production_ready(key: str) -> ActionResult:
    """
    O catálogo tem tudo que a PRODUÇÃO precisa para este produto? Recusa com código se não:
      UNKNOWN_PRODUCT; NOT_PRODUCIBLE (compra do governo, sem receita); UNSPECIFIED_DESIGN_VALUE (detalhe: `missing`).
    Hoje nenhum produto passa: quantidades, rendimento e estrelas das Matrizes não existem no 22. É o comportamento
    correto (P1.04 não pode produzir com dado indefinido) e muda sozinho quando o design especificar os valores.
    """
    p = Product.objects.filter(key=key).select_related("recipe").first()
    if p is None:
        return ActionResult(False, "UNKNOWN_PRODUCT", {"key": key})
    if p.sector == Sector.MILITARY_PROCUREMENT.value:
        return ActionResult(False, "NOT_PRODUCIBLE", {"key": key})
    missing: List[str] = []
    sector = Sector(p.sector)
    if p.min_stars is None and sector not in NO_STAR_SECTORS:
        missing.append("min_stars")
    recipe = recipe_of(key)
    if recipe is not None:
        if recipe.yield_quantity is None:
            missing.append("yield_quantity")
        missing.extend(f"quantity:{i.key}" for i in recipe.inputs if i.quantity is None)
    if missing:
        return ActionResult(False, "UNSPECIFIED_DESIGN_VALUE", {"key": key, "missing": missing})
    return ActionResult(True, "OK", {"key": key})


def check_consumption_ready(key: str) -> ActionResult:
    """O catálogo tem tudo que o CONSUMO como alimento precisa (04 §15)? NOT_FOOD ou UNSPECIFIED_DESIGN_VALUE se não."""
    if Product.objects.filter(key=key).first() is None:
        return ActionResult(False, "UNKNOWN_PRODUCT", {"key": key})
    food = food_of(key)
    if food is None:
        return ActionResult(False, "NOT_FOOD", {"key": key})
    missing = [n for n, v in (("nutrition_amount", food.nutrition_amount), ("qol_intensity", food.qol_intensity))
               if v is None]
    if missing:
        return ActionResult(False, "UNSPECIFIED_DESIGN_VALUE", {"key": key, "missing": missing})
    return ActionResult(True, "OK", {"key": key})
