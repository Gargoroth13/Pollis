"""
Exportação AUDITÁVEL do catálogo: tabela de valores provisórios `[PROV]` (GD 2026-10-14, Q3) e tabela de classificação
(categoria principal, tags e canais declarados, Q6/Q8). As tabelas do `design/22` (§3 e §4) são GERADAS daqui, e um teste
confere que o documento e o código dizem o mesmo; calibrar é mudar `provisional.py` e regenerar (`list_provisional`).
"""
from __future__ import annotations

from typing import List, Sequence

from . import provisional as prov
from .constants import Category, Channel
from .definitions import PRODUCTS, ProductDef
from .provisional import ProvisionalRow

CATEGORY_LABEL = {Category.FOOD: "Alimento", Category.MATERIAL: "Material", Category.EQUIPMENT: "Equipamento",
                  Category.DURABLE: "Durável", Category.MILITARY: "Militar"}
CHANNEL_LABEL = {Channel.RETAIL_SALE: "varejo", Channel.INTER_COMPANY: "entre empresas",
                 Channel.ARMY_PROCUREMENT: "fornecimento ao Exército", Channel.SPECIAL_REQUISITION: "requisição especial"}
SEPARATOR = ", "


def tags_of(p: ProductDef) -> List[str]:
    tags = []
    if p.is_consumable:
        tags.append("consumível")
    if p.is_permanent:
        tags.append("permanente")
    if p.is_military:
        tags.append("militar")
    return tags


def classification_rows(products: Sequence[ProductDef] = PRODUCTS):
    """(chave, nome, categoria, tags, canais), tudo em texto, na ordem do catálogo."""
    return [(p.key, p.name, CATEGORY_LABEL[p.category], SEPARATOR.join(tags_of(p)) or "—",
             SEPARATOR.join(CHANNEL_LABEL[c] for c in p.channels) or "—") for p in products]


def provisional_table(products: Sequence[ProductDef] = PRODUCTS) -> List[ProvisionalRow]:
    """TODA linha `[PROV]`: as regras gerais e, por produto, cada número provisório que o produto carrega."""
    rows = list(prov.general_rows())
    for p in products:
        if p.inputs is None:
            rows.append(ProvisionalRow(p.key, "matriz", f"{p.min_stars}★ / rendimento {p.raw_yield}",
                                       "estrela mínima e rendimento da matéria-prima", prov.SOURCE_Q3))
        else:
            recipe = " + ".join(f"{i.quantity}×{i.key}" for i in p.inputs)
            rows.append(ProvisionalRow(p.key, "receita", f"{recipe} → {p.yield_quantity}",
                                       "quantidade por insumo e rendimento", prov.SOURCE_Q3))
            if p.category is Category.MILITARY and p.min_stars is not None:
                rows.append(ProvisionalRow(p.key, "min_stars", f"{p.min_stars}★",
                                           "estrela mínima do produto militar do Exército", prov.SOURCE_Q4))
        if p.food is not None:
            source = prov.SOURCE_Q5 if p.key == "bread" else prov.SOURCE_Q3
            rows.append(ProvisionalRow(p.key, "consumo",
                                       f"nutrição {p.food.nutrition_amount} / QoL {p.food.qol_effect.value} "
                                       f"{p.food.qol_intensity}",
                                       "números do perfil de consumo (níveis qualitativos vêm do 22)"
                                       if p.key != "bread" else "perfil inteiro provisório (o 22 não declarava)", source))
        rows.append(ProvisionalRow(p.key, "base_price", str(p.base_price),
                                   "preço-base de referência (não é preço de mercado)", prov.SOURCE_Q3))
    return rows


def _md(header: Sequence[str], rows: Sequence[Sequence[str]]) -> List[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def markdown_classification(products: Sequence[ProductDef] = PRODUCTS) -> List[str]:
    return _md(("Chave", "Produto", "Categoria", "Tags", "Canais comerciais"), classification_rows(products))


def markdown_general_provisional() -> List[str]:
    return _md(("Parâmetro", "Valor", "Regra", "Fonte", "Status"),
               [(r.parameter, r.value, r.rule, r.source, r.status) for r in prov.general_rows()])


def markdown_base_prices(products: Sequence[ProductDef] = PRODUCTS) -> List[str]:
    return _md(("Chave", "Produto", "Preço-base [PROV]"), [(p.key, p.name, str(p.base_price)) for p in products])
