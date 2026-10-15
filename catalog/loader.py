"""
Carga do catálogo: definições (`definitions.PRODUCTS`, transcritas do 22) -> banco. IDEMPOTENTE e ATÔMICA.

  - rodar duas vezes não muda nada na segunda;
  - definições com ERRO de integridade não são carregadas (nada é gravado); PENDÊNCIA de design não impede a carga;
  - nunca apaga um Produto (inventário e estoque vão referenciá-lo): o que sobrar no banco sem definição aparece como erro
    em `integrity.check_integrity` (PRODUCT_NOT_IN_DEFINITIONS);
  - a `key` é permanente: a carga localiza o produto por ela e só atualiza o resto (nome, setor, receita...).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Sequence

from django.db import transaction

from .constants import Category, Channel, NutritionLevel, QolEffect, Sector
from .definitions import PRODUCTS, FoodDef, InputDef, ProductDef
from .models import FoodProfile, Product, Recipe, RecipeInput
from .validation import CatalogReport, validate


class CatalogDefinitionError(Exception):
    """As definições têm erro de integridade: o catálogo NÃO foi carregado."""

    def __init__(self, report: CatalogReport):
        self.report = report
        super().__init__(f"definições inválidas: {report.codes}")


@dataclass(frozen=True)
class SyncResult:
    created: int
    updated: int
    unchanged: int
    report: CatalogReport


def _dec(v) -> Optional[Decimal]:
    return None if v is None else Decimal(v)


def load_from_db() -> Dict[str, ProductDef]:
    """O catálogo gravado, na MESMA forma das definições (para validar e comparar sem listas paralelas)."""
    out: Dict[str, ProductDef] = {}
    products = (Product.objects.select_related("recipe", "food").prefetch_related("recipe__inputs__ingredient")
                .order_by("id"))
    for p in products:
        recipe = getattr(p, "recipe", None)
        food = getattr(p, "food", None)
        inputs = None
        if recipe is not None:
            inputs = tuple(InputDef(i.ingredient.key, _dec(i.quantity))
                           for i in sorted(recipe.inputs.all(), key=lambda i: i.position))
        out[p.key] = ProductDef(
            key=p.key, name=p.name, sector=Sector(p.sector), min_stars=p.min_stars, resource=p.resource, inputs=inputs,
            yield_quantity=_dec(recipe.yield_quantity) if recipe is not None else None,
            food=None if food is None else FoodDef(NutritionLevel(food.nutrition_level), QolEffect(food.qol_effect),
                                                   _dec(food.nutrition_amount), _dec(food.qol_intensity)),
            source_section=p.source_section, source_names=tuple(p.source_names),
            category=Category(p.category) if p.category else None, is_consumable=p.is_consumable,
            is_permanent=p.is_permanent, is_military=p.is_military,
            channels=tuple(Channel(c) for c in p.commercial_channels),
            base_price=_dec(p.base_price), raw_yield=_dec(p.raw_yield))
    return out


@transaction.atomic
def sync_catalog(products: Sequence[ProductDef] = PRODUCTS) -> SyncResult:
    report = validate(products)
    if not report.ok:
        raise CatalogDefinitionError(report)
    existing = load_from_db()
    created = updated = unchanged = 0
    rows: Dict[str, Product] = {}
    changed = []
    for d in products:
        current = existing.get(d.key)
        if current == d:
            unchanged += 1
            continue
        changed.append(d)
        obj = Product.objects.filter(key=d.key).first()
        fields = dict(name=d.name, sector=d.sector.value, min_stars=d.min_stars, resource=d.resource,
                      source_section=d.source_section, source_names=list(d.source_names),
                      category=d.category.value if d.category else "", is_consumable=d.is_consumable,
                      is_permanent=d.is_permanent, is_military=d.is_military,
                      commercial_channels=[c.value for c in d.channels], base_price=d.base_price,
                      raw_yield=d.raw_yield)
        if obj is None:
            obj = Product.objects.create(key=d.key, **fields)
            created += 1
        else:
            for k, v in fields.items():
                setattr(obj, k, v)
            obj.save()
            updated += 1
    rows = {p.key: p for p in Product.objects.all()}
    for d in changed:               # receitas só depois de todos os produtos existirem (insumos referenciam produtos)
        obj = rows[d.key]
        if d.inputs is None:
            Recipe.objects.filter(product=obj).delete()
        else:
            recipe, _ = Recipe.objects.update_or_create(product=obj, defaults={"yield_quantity": d.yield_quantity})
            recipe.inputs.all().delete()
            RecipeInput.objects.bulk_create(
                RecipeInput(recipe=recipe, ingredient=rows[i.key], position=n, quantity=i.quantity)
                for n, i in enumerate(d.inputs, start=1))
        if d.food is None:
            FoodProfile.objects.filter(product=obj).delete()
        else:
            FoodProfile.objects.update_or_create(product=obj, defaults=dict(
                nutrition_level=d.food.nutrition_level.value, qol_effect=d.food.qol_effect.value,
                nutrition_amount=d.food.nutrition_amount, qol_intensity=d.food.qol_intensity))
    return SyncResult(created, updated, unchanged, report)
