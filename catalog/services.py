"""
Consultas e verificações sobre o catálogo gravado. TUDO é derivado das receitas e do perfil de alimento: não existe lista
paralela de "quem compra o quê" (02 §4, §20).

Regras de honestidade (decisão do Game Director, 2026-10-11; atualizada em 2026-10-14):
  - valor NÃO ESPECIFICADO é `None`, nunca zero; nenhuma função converte `None` em 0. Valores `[PROV]` (provisional.py)
    são valores especificados, mas provisórios: continuam auditáveis na tabela provisória;
  - uso NÃO declarado não concede permissão: `uses_of` devolve só o que o catálogo declara (receitas, perfil de alimento e
    canais comerciais declarados), e o que não está nele não existe para fins de compra/venda;
  - quem precisa de um número que o design ainda não deu RECUSA com `UNSPECIFIED_DESIGN_VALUE` (e diz quais faltam), em
    vez de seguir em silêncio. Recusas são códigos (ActionResult), como no resto do projeto.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import FrozenSet, List, Optional, Tuple

from players.services import ActionResult

from .constants import (ARMY_PRODUCER_SECTOR, NO_STAR_SECTORS, RAW_SECTORS, Category, Channel, NutritionLevel, QolEffect, Sector,
                        UseKind)
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
    channel: Optional[Channel] = None      # COMMERCIAL_CHANNEL: o canal declarado


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


def category_of(key: str) -> Optional[Category]:
    """Categoria principal DECLARADA do produto (None se o produto não existe ou não foi classificado)."""
    value = Product.objects.filter(key=key).values_list("category", flat=True).first()
    return Category(value) if value else None


def channels_of(key: str) -> Tuple[Channel, ...]:
    """Canais comerciais DECLARADOS no catálogo. Vazio = nenhum canal declarado = nenhuma permissão por inferência."""
    value = Product.objects.filter(key=key).values_list("commercial_channels", flat=True).first()
    return tuple(Channel(c) for c in (value or ()))


def has_channel(key: str, channel: Channel) -> bool:
    return channel in channels_of(key)


def base_price_of(key: str) -> Optional[Decimal]:
    """Preço-base de REFERÊNCIA (`[PROV]`, não é preço de mercado; 17 §20). None = não especificado."""
    return Product.objects.filter(key=key).values_list("base_price", flat=True).first()


def uses_of(key: str) -> List[ProductUse]:
    """
    Usos DECLARADOS do produto: insumo de receitas (derivado, ordenado pela chave do produto-alvo), consumo como alimento
    (derivado) e canais comerciais declarados. Lista vazia = nenhum uso declarado = NENHUMA permissão por inferência.
    """
    from .models import RecipeInput
    uses = [ProductUse(UseKind.RECIPE_INPUT, ri.recipe.product.key, ri.quantity)
            for ri in RecipeInput.objects.filter(ingredient__key=key).select_related("recipe__product")]
    uses.sort(key=lambda u: u.target_key)
    if food_of(key) is not None:
        uses.append(ProductUse(UseKind.PLAYER_CONSUMPTION))
    uses.extend(ProductUse(UseKind.COMMERCIAL_CHANNEL, channel=c) for c in channels_of(key))
    if Product.objects.filter(key=key, is_military=True).exists():
        uses.append(ProductUse(UseKind.MILITARY_ACTION))
    return uses


def producer_sector_of(key: str) -> Optional[Sector]:
    """
    Setor da EMPRESA que produz o produto (GD 2026-10-15): matéria-prima e produtos industriais → o próprio setor;
    produtos militares do Exército → Industrial / Produção (`ARMY_PRODUCER_SECTOR`); milícia → None (quem produz é a
    milícia, não uma empresa); produto desconhecido → None.
    """
    value = Product.objects.filter(key=key).values_list("sector", flat=True).first()
    if value is None:
        return None
    sector = Sector(value)
    if sector == Sector.MILITARY_PROCUREMENT:
        return ARMY_PRODUCER_SECTOR
    return None if sector == Sector.MILITIA else sector


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
      UNKNOWN_PRODUCT; UNSPECIFIED_DESIGN_VALUE (detalhe: `missing`).
    Desde a P0.02 os valores `[PROV]` (provisional.py) completam receitas, estrelas e rendimento: todo produto do catálogo
    passa. A recusa continua valendo para qualquer valor que volte a ficar não especificado. (Os produtos militares do
    Exército deixaram de ser "não produzíveis": são produzidos por empresas Industriais, GD 2026-10-14, Q4.)
    """
    p = Product.objects.filter(key=key).select_related("recipe").first()
    if p is None:
        return ActionResult(False, "UNKNOWN_PRODUCT", {"key": key})
    missing: List[str] = []
    sector = Sector(p.sector)
    if p.min_stars is None and sector not in NO_STAR_SECTORS:
        missing.append("min_stars")
    if sector in RAW_SECTORS and p.raw_yield is None:
        missing.append("raw_yield")
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
