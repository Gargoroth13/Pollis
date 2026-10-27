"""
Parâmetros dos Imóveis. O `10` (FINAL — BOT TEST) fixa a estrutura e alguns valores iniciais; o que ele deixa em aberto entra como
`[PROV]` numa tabela auditável (nenhum valor inventado fora daqui).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, FrozenSet, List

from companies.constants import CompanyType
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

# Localização de empresas (10 §29; 08 §8, §9, §12): o uso de lote que cada tipo de empresa exige. Matriz → rural (08 §12), Industrial → industrial
# (08 §9 "devem utilizar esses lotes"), Varejo → comercial (08 §8; 10 §16 "especialmente o Varejo"), Serviços → comercial (08 §8 "varejo e serviços
# utilizarão esses lotes quando sua atividade exigir"; o design não diz QUAIS serviços exigem: [PROV] todos podem). Construtora e Financeira: o design
# não define localização (a Construtora constrói no lote que possui, 10 §28) → não localizáveis nesta etapa. Veja `design/10a` §9, J2.
COMPANY_SITE_USE: Dict[CompanyType, Category] = {
    CompanyType.MATRIX: Category.RURAL,
    CompanyType.INDUSTRIAL: Category.INDUSTRIAL,
    CompanyType.RETAIL: Category.COMMERCIAL,
    CompanyType.SERVICES: Category.COMMERCIAL,
}

# Terreno rural (02 §2.1; 08 §12; design/10a G12). REGRA A PROVISÓRIA (instrução do GD, 2026-10-27), substituível pela opção B (tipo de terreno gerado
# por lote) sem mexer nos consumidores: só `properties.sites.terrain_of` muda.
#   - produto COMUM = matéria-prima de Agropecuária ou Extrativismo SEM recurso espacial (Trigo, Madeira, Pedra...): qualquer lote rural o sustenta;
#   - produto de DEPÓSITO = o que tem recurso espacial (petróleo e os 9 minerais): só o lote que tem o depósito o sustenta.
# `DEPOSIT_LOTS_ALSO_COMMON`: o lote COM depósito também sustenta os produtos comuns? [PROV] True: 08 §12 diz que o lote rural permite as três áreas e
# o depósito apenas define QUAL recurso espacial há (não os escolhe o jogador). Aguarda confirmação do GD (design/10a G12, ponto 3).
TERRAIN_RULE = "G12-A-PROV"
DEPOSIT_LOTS_ALSO_COMMON = True

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
        ProvisionalRow("properties", "terrain.rule", TERRAIN_RULE, "lote rural sem depósito sustenta Agro + Extrativismo não-petróleo (G12, opção A); "
                       "provedor de terreno substituível pela opção B", "02 §2.1; 08 §12; GD 2026-10-27", status="PROV"),
        ProvisionalRow("properties", "terrain.deposit_lots_also_common", str(DEPOSIT_LOTS_ALSO_COMMON),
                       "lote com depósito também sustenta os produtos comuns (08 §12: o lote rural permite as três áreas)", "08 §12", status="PROV"),
        *(ProvisionalRow("properties", f"company_site_use.{t.value}", c.value,
                         "uso de lote exigido para a empresa se localizar (08 §8, §9, §12)" + ("; quais Serviços exigem local é [PROV]" if t is CompanyType.SERVICES else ""),
                         "08 FINAL; 10 §29", status="PROV" if t is CompanyType.SERVICES else "GD")
          for t, c in COMPANY_SITE_USE.items()),
    ]
