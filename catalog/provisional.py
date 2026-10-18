"""
Tabela AUDITÁVEL dos valores provisórios `[PROV]` do catálogo.

Decisão do Game Director (2026-10-14, Q3): usar valores iniciais `[PROV]`, calibráveis durante o Bot Test, sem pedir
aprovação de cada número de balanceamento, desde que (a) registrados numa tabela auditável, (b) com a fonte de verdade
identificada e (c) calibráveis sem redesenhar a arquitetura.

  - ESTE módulo é a fonte de verdade dos números do catálogo. Calibrar é mudar um valor aqui e rodar `sync_catalog`.
  - `provisional_table()` devolve TODA linha provisória (escopo, parâmetro, valor, regra e fonte); o comando
    `list_provisional` a exporta; os testes conferem que cada número em `definitions` vem desta tabela.
  - Estes valores são PROVISÓRIOS: não são regra de design. A estrutura (categorias, canais, receitas) vem do `22`.
  - Estrutura e número não se confundem: o que o `22` declara (níveis qualitativos, estrelas dos produtos industriais,
    insumos) NÃO é sobrescrito aqui.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from .constants import NutritionLevel, QolEffect

D = Decimal

SOURCE_Q3 = "GD 2026-10-14 Q3"
SOURCE_Q4 = "GD 2026-10-14 Q4"
SOURCE_Q5 = "GD 2026-10-14 Q5"
STATUS = "PROV"

# --- receitas (Q3: uma unidade de cada ingrediente declarado produz uma unidade do produto final) -----------------
RECIPE_INPUT_QUANTITY = D(1)
RECIPE_YIELD = D(1)

# --- Matriz (Q3: estrelas e rendimentos de Matriz) ------------------------------------------------------------------
MATRIZ_MIN_STARS = 1               # uniforme: o 22 não diferencia; a calibração poderá diferenciar por terreno/produto
MATRIZ_YIELD = D(1)                # unidades por execução de produção da Matriz

# --- Exército (Q4: estrela mínima 2★ [PROV], produzido por empresas Industriais) --------------------------------------
ARMY_MIN_STARS = 2

# --- alimentos (Q3, Q5): escala de Nutrição 0-100 (04 §15); QoL na mesma unidade de QoL (neutro = 1,00; base = 0,50) ----
NUTRITION_BY_LEVEL: Mapping[NutritionLevel, Decimal] = {
    NutritionLevel.NONE: D(0),
    NutritionLevel.ALMOST_NONE: D(5),
    NutritionLevel.LOW: D(15),
    NutritionLevel.MEDIUM: D(30),
    NutritionLevel.HIGH: D(50),
}
# Magnitude (>= 0) do efeito temporário de QoL; o sentido vem do tipo do efeito (debuff = negativo).
QOL_INTENSITY_BY_EFFECT: Mapping[QolEffect, Decimal] = {
    QolEffect.NO_EFFECT: D(0),
    QolEffect.SMALL_BUFF: D("0.05"),
    QolEffect.MEDIUM_BUFF: D("0.10"),
    QolEffect.DEBUFF: D("0.05"),
}
# Pão (Q5): consumível; o 22 não dá os níveis, então o perfil inteiro é provisório.
BREAD_NUTRITION_LEVEL = NutritionLevel.MEDIUM
BREAD_QOL_EFFECT = QolEffect.NO_EFFECT

# --- preço-base (Q3): valor de REFERÊNCIA do item, não preço de mercado (17 §20) -------------------------------------
RAW_BASE_PRICE = D("10.00")           # matéria-prima
VALUE_ADDED_PER_STAR = D("5.00")      # valor agregado por execução de receita, por estrela mínima (sem estrela = 1)
PRICE_QUANTUM = D("0.01")             # centavos


@dataclass(frozen=True)
class ProvisionalRow:
    scope: str          # "catalog" (regra geral) ou a chave do produto
    parameter: str
    value: str
    rule: str
    source: str
    status: str = STATUS


def nutrition_amount(level: NutritionLevel) -> Decimal:
    return NUTRITION_BY_LEVEL[level]


def qol_intensity(effect: QolEffect) -> Decimal:
    return QOL_INTENSITY_BY_EFFECT[effect]


def compute_base_prices(recipes: Mapping[str, Tuple[Tuple[Tuple[str, Decimal], ...], Decimal, Optional[int]]],
                        raw_keys: Iterable[str]) -> Dict[str, Decimal]:
    """
    Preço-base de referência, determinístico: matéria-prima = RAW_BASE_PRICE; produto feito =
    (soma de preço-base do insumo × quantidade) / rendimento + VALUE_ADDED_PER_STAR × estrelas (produto sem estrela conta 1).
    `recipes[key] = (((insumo, quantidade), ...), rendimento, estrelas)`. Assume grafo sem ciclo (a validação o garante).
    """
    prices: Dict[str, Decimal] = {k: RAW_BASE_PRICE for k in raw_keys}

    def price(key: str) -> Decimal:
        if key not in prices:
            inputs, yield_q, stars = recipes[key]
            cost = sum((price(i) * q for i, q in inputs), D(0)) / yield_q
            prices[key] = (cost + VALUE_ADDED_PER_STAR * (stars or 1)).quantize(PRICE_QUANTUM)
        return prices[key]

    for k in recipes:
        price(k)
    return prices


def general_rows() -> List[ProvisionalRow]:
    rows = [
        ProvisionalRow("catalog", "recipe_input_quantity", str(RECIPE_INPUT_QUANTITY),
                       "uma unidade de cada ingrediente declarado", SOURCE_Q3),
        ProvisionalRow("catalog", "recipe_yield", str(RECIPE_YIELD),
                       "uma unidade do produto final por execução", SOURCE_Q3),
        ProvisionalRow("catalog", "matriz_min_stars", str(MATRIZ_MIN_STARS),
                       "uniforme para toda matéria-prima (o 22 não diferencia)", SOURCE_Q3),
        ProvisionalRow("catalog", "matriz_yield", str(MATRIZ_YIELD),
                       "unidades por execução de produção da Matriz", SOURCE_Q3),
        ProvisionalRow("catalog", "army_min_stars", str(ARMY_MIN_STARS),
                       "estrela mínima dos produtos militares do Exército (Industrial)", SOURCE_Q4),
        ProvisionalRow("catalog", "raw_base_price", str(RAW_BASE_PRICE), "preço-base de referência da matéria-prima",
                       SOURCE_Q3),
        ProvisionalRow("catalog", "value_added_per_star", str(VALUE_ADDED_PER_STAR),
                       "valor agregado por execução e por estrela mínima (produto sem estrela conta 1)", SOURCE_Q3),
        ProvisionalRow("catalog", "bread_profile", f"{BREAD_NUTRITION_LEVEL.value}/{BREAD_QOL_EFFECT.value}",
                       "perfil de consumo do Pão (o 22 não declarava)", SOURCE_Q5),
    ]
    rows += [ProvisionalRow("catalog", f"nutrition_amount[{lv.value}]", str(v),
                            "ganho de Nutrição por unidade consumida (escala 0-100) pelo nível qualitativo do 22", SOURCE_Q3)
             for lv, v in NUTRITION_BY_LEVEL.items()]
    rows += [ProvisionalRow("catalog", f"qol_intensity[{ef.value}]", str(v),
                            "magnitude do efeito temporário de QoL (debuff é negativo)", SOURCE_Q3)
             for ef, v in QOL_INTENSITY_BY_EFFECT.items()]
    return rows
