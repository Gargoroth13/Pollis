"""
Validação PURA do catálogo (não toca o banco): serve tanto às definições transcritas do `22` quanto ao catálogo lido do
banco (`integrity.check_integrity`), com os mesmos códigos.

Duas classes de achado (decisão do Game Director, 2026-10-11):
  ERRO de integridade   referência quebrada, chave duplicada, ciclo, inconsistência estrutural real. Impede carregar.
  PENDÊNCIA de design   dado ainda não especificado / uso não declarado. NUNCA impede a carga e NUNCA vira permissão.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

from geography.constants import RESOURCE_KIND, RESOURCE_NAMES, Resource, ResourceKind

from .constants import (COMPANY_SECTORS, MAX_STARS, MIN_STARS, MILITARY_SECTORS, NO_STAR_SECTORS, RAW_SECTORS,
                        RECIPE_SECTORS, Category, Channel, Sector)
from .definitions import KNOWN_GAPS, Gap, ProductDef


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str     # chave do produto (ou "catalog" para achados globais)
    detail: str = ""


@dataclass
class CatalogReport:
    errors: List[Finding] = field(default_factory=list)
    pending: List[Finding] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Só ERROS reprovam. Pendência de design não reprova o catálogo."""
        return not self.errors

    @property
    def codes(self) -> List[str]:
        return sorted({f.code for f in self.errors})

    @property
    def pending_codes(self) -> List[str]:
        return sorted({f.code for f in self.pending})

    def error(self, code: str, subject: str, detail: str = "") -> None:
        self.errors.append(Finding(code, subject, detail))

    def warn(self, code: str, subject: str, detail: str = "") -> None:
        self.pending.append(Finding(code, subject, detail))

    def subjects(self, code: str) -> List[str]:
        return sorted(f.subject for f in self.errors + self.pending if f.code == code)


def _is_positive(v) -> bool:
    return isinstance(v, Decimal) and v > 0


def _is_non_negative(v) -> bool:
    return isinstance(v, Decimal) and v >= 0


def find_cycles(products: Sequence[ProductDef]) -> List[Tuple[str, ...]]:
    """Ciclos no grafo insumo → produto (iterativo; cada ciclo é devolvido uma vez, na ordem em que foi percorrido)."""
    graph = {p.key: [i.key for i in (p.inputs or ())] for p in products}
    cycles, state = [], {}
    for start in graph:
        if start in state:
            continue
        stack = [(start, iter(graph[start]))]
        path = [start]
        state[start] = 1
        while stack:
            node, it = stack[-1]
            for nxt in it:
                if nxt not in graph:
                    continue                      # referência quebrada: outro código
                if state.get(nxt) == 1:
                    cycles.append(tuple(path[path.index(nxt):] + [nxt]))
                elif nxt not in state:
                    state[nxt] = 1
                    path.append(nxt)
                    stack.append((nxt, iter(graph[nxt])))
                    break
            else:
                state[node] = 2
                path.pop()
                stack.pop()
    return cycles


def _validate_classification(r: "CatalogReport", p: ProductDef, by_key: Dict[str, ProductDef]) -> None:
    """Categoria única, tags coerentes e canais declarados coerentes com a estrutura (GD 2026-10-14, Q6 e Q8)."""
    if p.category is None:
        r.error("CATEGORY_MISSING", p.key)
        return
    if not isinstance(p.category, Category):
        r.error("CATEGORY_INVALID", p.key, repr(p.category))
        return
    if (p.category is Category.MILITARY) != (p.sector in MILITARY_SECTORS):
        r.error("CATEGORY_SECTOR_MISMATCH", p.key, f"{p.category.value} x {p.sector.value}")
    if p.is_military != (p.category is Category.MILITARY):
        r.error("MILITARY_TAG_MISMATCH", p.key)
    if p.food is not None and (p.category is not Category.FOOD or not p.is_consumable):
        r.error("FOOD_NOT_CLASSIFIED_AS_FOOD", p.key)
    if p.category is Category.FOOD and p.food is None:
        r.error("FOOD_WITHOUT_PROFILE", p.key)
    if p.is_consumable and p.is_permanent:
        r.error("CONSUMABLE_AND_PERMANENT", p.key)
    if len(set(p.channels)) != len(p.channels) or not all(isinstance(c, Channel) for c in p.channels):
        r.error("CHANNEL_INVALID", p.key, repr(p.channels))
        return
    if Channel.RETAIL_SALE in p.channels and p.category not in (Category.FOOD, Category.EQUIPMENT, Category.DURABLE):
        r.error("RETAIL_CHANNEL_NOT_FINAL_GOOD", p.key, p.category.value)
    if Channel.INTER_COMPANY in p.channels and p.category is Category.MILITARY:
        r.error("MILITARY_IN_INTER_COMPANY_TRADE", p.key)
    if Channel.ARMY_PROCUREMENT in p.channels and p.sector != Sector.MILITARY_PROCUREMENT:
        r.error("ARMY_CHANNEL_NOT_ARMY_PRODUCT", p.key)
    if p.sector == Sector.MILITARY_PROCUREMENT and Channel.RETAIL_SALE in p.channels:
        r.error("ARMY_PRODUCT_IN_RETAIL", p.key)
    if Channel.SPECIAL_REQUISITION in p.channels:
        feeds_militia = any(q.sector == Sector.MILITIA and any(i.key == p.key for i in (q.inputs or ()))
                            for q in by_key.values())
        if not feeds_militia:
            r.error("REQUISITION_NOT_A_MILITIA_INPUT", p.key)


def validate(products: Sequence[ProductDef], gaps: Sequence[Gap] = KNOWN_GAPS) -> CatalogReport:
    r = CatalogReport()
    keys = Counter(p.key for p in products)
    by_key: Dict[str, ProductDef] = {}
    for p in products:
        by_key.setdefault(p.key, p)
    for k, n in keys.items():
        if n > 1:
            r.error("DUPLICATE_KEY", k, f"{n} produtos com a mesma chave")
    resources = Counter(p.resource for p in products if p.resource is not None)
    for res, n in resources.items():
        if n > 1:
            r.error("DUPLICATE_RESOURCE_LINK", res, f"{n} produtos ligados ao mesmo recurso")

    consumed_by: Dict[str, List[str]] = {k: [] for k in by_key}
    for p in products:
        # --- referências e estrutura da receita ---------------------------------------------------------------
        if p.sector in RAW_SECTORS:
            if p.inputs is not None:
                r.error("RAW_WITH_RECIPE", p.key)
        elif p.sector in RECIPE_SECTORS and not p.inputs:
            r.error("PRODUCED_WITHOUT_RECIPE", p.key)
        seen = Counter(i.key for i in (p.inputs or ()))
        for ing, n in seen.items():
            if n > 1:
                r.error("DUPLICATE_INPUT", p.key, ing)
            if ing not in by_key:
                r.error("INGREDIENT_NOT_FOUND", p.key, ing)
            else:
                consumed_by[ing].append(p.key)
        # --- valores: não especificado (None) é válido; zero/negativo/float NÃO são ----------------------------
        for i in (p.inputs or ()):
            if i.quantity is not None and not _is_positive(i.quantity):
                r.error("INVALID_QUANTITY", p.key, f"{i.key}={i.quantity!r}")
        if p.yield_quantity is not None and not _is_positive(p.yield_quantity):
            r.error("INVALID_YIELD", p.key, repr(p.yield_quantity))
        if p.raw_yield is not None and (not _is_positive(p.raw_yield) or p.sector not in RAW_SECTORS):
            r.error("INVALID_RAW_YIELD", p.key, repr(p.raw_yield))
        if p.base_price is not None and not _is_non_negative(p.base_price):
            r.error("INVALID_BASE_PRICE", p.key, repr(p.base_price))
        _validate_classification(r, p, by_key)
        if p.min_stars is not None:
            if not isinstance(p.min_stars, int) or not MIN_STARS <= p.min_stars <= MAX_STARS:
                r.error("INVALID_STARS", p.key, repr(p.min_stars))
            elif p.sector in NO_STAR_SECTORS:
                r.error("STARS_NOT_APPLICABLE", p.key, f"setor {p.sector.value} não tem estrela")
        if p.food is not None:
            for name, v in (("nutrition_amount", p.food.nutrition_amount), ("qol_intensity", p.food.qol_intensity)):
                if v is not None and not _is_non_negative(v):
                    r.error("INVALID_FOOD_VALUE", p.key, f"{name}={v!r}")
        # --- ligação com a Geografia (08 §12-§15) --------------------------------------------------------------
        if p.resource is not None:
            if p.sector not in RAW_SECTORS:
                r.error("RESOURCE_ON_NON_RAW", p.key)
            if p.resource not in RESOURCE_NAMES:
                r.error("RESOURCE_UNKNOWN", p.key, p.resource)
            else:
                expected = {ResourceKind.EXTRACTIVE: Sector.EXTRACTIVE, ResourceKind.MINERAL: Sector.MINING}[
                    RESOURCE_KIND[Resource(p.resource)]]
                if p.sector != expected:
                    r.error("RESOURCE_SECTOR_MISMATCH", p.key, f"{p.sector.value} != {expected.value}")
    present = {p.resource for p in products if p.resource}
    for res in sorted(RESOURCE_NAMES - present):
        r.error("RESOURCE_WITHOUT_PRODUCT", res, "recurso da Geografia sem matéria-prima no catálogo")
    for cyc in find_cycles(products):
        r.error("RECIPE_CYCLE", cyc[0], " -> ".join(cyc))

    # --- pendências de design (nunca impedem a carga, nunca concedem permissão) ------------------------------------
    for p in products:
        has_use = bool(consumed_by.get(p.key)) or p.food is not None or bool(p.channels) or p.is_military
        if not has_use:
            r.warn("RAW_MATERIAL_WITHOUT_USE" if p.sector in RAW_SECTORS else "PRODUCT_WITHOUT_DECLARED_USE", p.key)
        if p.inputs and any(i.quantity is None for i in p.inputs):
            r.warn("RECIPE_QUANTITIES_UNSPECIFIED", p.key)
        if p.inputs and p.yield_quantity is None:
            r.warn("RECIPE_YIELD_UNSPECIFIED", p.key)
        if p.min_stars is None and (p.sector in RAW_SECTORS or p.sector in COMPANY_SECTORS):
            r.warn("MIN_STARS_UNSPECIFIED", p.key)
        if p.sector in RAW_SECTORS and p.raw_yield is None:
            r.warn("RAW_YIELD_UNSPECIFIED", p.key)
        if p.base_price is None:
            r.warn("BASE_PRICE_UNSPECIFIED", p.key)
        if p.food is not None and p.food.nutrition_amount is None:
            r.warn("FOOD_NUTRITION_UNSPECIFIED", p.key)
        if p.food is not None and p.food.qol_intensity is None:
            r.warn("FOOD_QOL_INTENSITY_UNSPECIFIED", p.key)
    for g in gaps:
        r.warn(g.code, "catalog", g.description)

    r.stats = {"products": len(products), "raw": sum(p.sector in RAW_SECTORS for p in products),
               "recipes": sum(p.inputs is not None for p in products), "foods": sum(p.food is not None for p in products),
               "errors": len(r.errors), "pending": len(r.pending)}
    return r
