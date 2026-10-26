"""
Parâmetros dos Imóveis. O `10` (FINAL — BOT TEST) fixa a estrutura e alguns valores iniciais; o que ele deixa em aberto entra como
`[PROV]` numa tabela auditável (nenhum valor inventado fora daqui).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, FrozenSet, List

from companies.params import ProvisionalRow
from geography.constants import Category


@dataclass(frozen=True)
class BuildingType:
    key: str
    name: str
    units: int
    qol_bonus: Decimal
    min_stars: int                             # Construtora mínima (10 §6; o mesmo valor está em `companies.params.CONSTRUCTION_PROJECTS`)


# 10 §6: "Esses valores são parâmetros iniciais para Bot Test." "~20 unidades" → 20 (aproximação do próprio design).
BUILDING_TYPES: Dict[str, BuildingType] = {b.key: b for b in (
    BuildingType("low_density_simple", "Baixa densidade simples", 1, Decimal("0"), 1),
    BuildingType("low_density_luxury", "Baixa densidade luxo", 1, Decimal("0.3"), 3),
    BuildingType("high_density_simple", "Alta densidade simples", 20, Decimal("0.1"), 2),
    BuildingType("high_density_luxury", "Alta densidade luxo", 20, Decimal("0.4"), 4),
)}

# 10 §4.2/§4.3: duração, janela e extensão são "parâmetros do sistema, ajustáveis durante o Bot Test" e o design não dá o número. [PROV]
# (tempo de JOGO em segundos; 1 dia de jogo = 10 min reais no ambiente acelerado do Bot Test, 21 §Relógio)
AUCTION_DURATION_SECONDS = 24 * 3600                       # [PROV] 1 dia de jogo
EXTENSION_WINDOW_SECONDS = 10 * 60                         # [PROV] lance nos últimos 10 min de jogo estende
EXTENSION_SECONDS = 10 * 60                                # [PROV] a extensão soma 10 min ao encerramento
MIN_BID_INCREMENT_CENTS = 1                                # [PROV] "os participantes podem aumentar o valor": qualquer aumento

# 10 §2: "todos os lotes disponíveis para desenvolvimento" são do governo e vão a leilão. Quais categorias: [PROV] — as de uso privado
# (residencial, comercial, industrial) e rural (terreno da Matriz); institucional é de uso público e especial não tem regra no design.
AUCTIONABLE_CATEGORIES: FrozenSet[Category] = frozenset({Category.RESIDENTIAL, Category.COMMERCIAL, Category.INDUSTRIAL, Category.RURAL})

SOURCE = "10 FINAL; valores [PROV]"


def provisional_table() -> List[ProvisionalRow]:
    return [
        ProvisionalRow("properties", "auction_duration_seconds", str(AUCTION_DURATION_SECONDS),
                       "duração do leilão (10 §4.2 'parâmetro do sistema'; o número não existe no design)", SOURCE),
        ProvisionalRow("properties", "extension_window_seconds", str(EXTENSION_WINDOW_SECONDS),
                       "janela do fim em que um lance estende o leilão (10 §4.3)", SOURCE),
        ProvisionalRow("properties", "extension_seconds", str(EXTENSION_SECONDS), "tempo somado ao encerramento (10 §4.3)", SOURCE),
        ProvisionalRow("properties", "min_bid_increment_cents", str(MIN_BID_INCREMENT_CENTS),
                       "aumento mínimo sobre o lance atual (10 §4.1: 'podem aumentar o valor')", SOURCE),
        ProvisionalRow("properties", "auctionable_categories", ",".join(sorted(c.value for c in AUCTIONABLE_CATEGORIES)),
                       "categorias de lote que o governo leiloa (10 §2 'disponíveis para desenvolvimento')", SOURCE),
        *(ProvisionalRow("properties", f"building.{b.key}", f"units={b.units};qol={b.qol_bonus};min_stars={b.min_stars}",
                         "imóvel residencial (10 §6; 'parâmetros iniciais para Bot Test'; ~20 → 20)", "10 §6", status="GD")
          for b in BUILDING_TYPES.values()),
    ]
