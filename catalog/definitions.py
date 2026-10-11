"""
Dados do catálogo, transcritos do `design/22-Receitas-Produção.md`.

REGRAS DESTA TRANSCRIÇÃO (decisão do Game Director, 2026-10-11):
  - só entra o que o `22` ATUAL declara: nenhum produto, receita, uso, quantidade ou atributo foi inventado;
  - o `22` NÃO é um catálogo completo nem definitivo: as lacunas estão em `KNOWN_GAPS` e no `CHANGELOG_DEV.md`;
  - o identificador (`key`) é estável e independe do nome de apresentação: o nome pode ser renomeado, a `key` não;
  - nomes duplicados/inconsistentes que são claramente a MESMA entidade foram normalizados; as variantes como aparecem
    no `22` ficam em `source_names` (rastreabilidade com o design) e um teste confere esta transcrição contra o arquivo;
  - valores que o `22` não fornece (quantidade de insumo, rendimento, Nutrição numérica, intensidade de QoL, estrela das
    Matrizes) ficam `None` = NÃO ESPECIFICADO, que é diferente de zero.

As chaves das matérias-primas que são recursos espaciais da Geografia (08 §15) são os próprios valores de
`geography.constants.Resource`.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from .constants import NutritionLevel, QolEffect, Sector

S = Sector


@dataclass(frozen=True)
class InputDef:
    key: str
    quantity: Optional[Decimal] = None       # None = não especificado (≠ 0)


@dataclass(frozen=True)
class FoodDef:
    nutrition_level: NutritionLevel
    qol_effect: QolEffect
    nutrition_amount: Optional[Decimal] = None   # None = não especificado (≠ 0)
    qol_intensity: Optional[Decimal] = None      # None = não especificado (≠ 0)


@dataclass(frozen=True)
class ProductDef:
    key: str
    name: str
    sector: Sector
    min_stars: Optional[int] = None              # None = não especificado OU não se aplica (ver NO_STAR_SECTORS)
    resource: Optional[str] = None               # valor de geography.constants.Resource (matéria-prima espacial)
    inputs: Optional[Tuple[InputDef, ...]] = None  # None = SEM receita (matéria-prima ou compra do governo)
    yield_quantity: Optional[Decimal] = None     # None = não especificado (≠ 0)
    food: Optional[FoodDef] = None
    source_section: str = ""
    source_names: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Gap:
    """Lacuna conhecida do catálogo: citada por documentos relacionados e AUSENTE do `22`. Nunca some em silêncio."""
    code: str
    description: str
    referenced_by: Tuple[str, ...]
    blocks: Tuple[str, ...]       # etapas futuras que dependem da resolução


def _raw(key, name, sector, section, *names, resource=None):
    return ProductDef(key=key, name=name, sector=sector, resource=resource, source_section=section,
                      source_names=tuple(names) or (name,))


def _made(key, name, sector, stars, inputs, section, *names, food=None):
    return ProductDef(key=key, name=name, sector=sector, min_stars=stars,
                      inputs=tuple(InputDef(i) for i in inputs), food=food, source_section=section,
                      source_names=tuple(names) or (name,))


_AGRO = "22 §2.2 Matriz / Agropecuária"
_EXT = "22 §2.2 Matriz / Extrativismo"
_MIN = "22 §2.2 Matriz / Mineração"
_PROD = "22 §2.3 Industrial / Produção"
_FOOD = "22 §2.3 Industrial / Alimentícia"
_CONS = "22 §2.3 Industrial / Bens de consumo"
_TECH = "22 §2.3 Industrial / Tecnológica"
_MIL = "22 §2.3 Milícia"
_ARMY = "22 §2.3 Produtos militares do Exército"

_RAW = (
    # Agropecuária
    _raw("wheat", "Trigo", S.AGRO, _AGRO),
    _raw("milk", "Leite", S.AGRO, _AGRO),
    _raw("sugar_cane", "Cana", S.AGRO, _AGRO),
    _raw("coffee_bean", "Grão de café", S.AGRO, _AGRO, "Grão de Café", "Grão de café"),
    _raw("cocoa", "Cacau", S.AGRO, _AGRO),
    _raw("meat", "Carne", S.AGRO, _AGRO),
    _raw("eggs", "Ovos", S.AGRO, _AGRO, "Ovos", "Ovo"),
    _raw("leather", "Couro", S.AGRO, _AGRO),
    _raw("wool", "Lã", S.AGRO, _AGRO),
    _raw("fruit", "Fruta", S.AGRO, _AGRO),
    # Extrativismo (o petróleo é recurso espacial, 08 §12/§14, e exclusivo do Extrativismo)
    _raw("wood", "Madeira", S.EXTRACTIVE, _EXT),
    _raw("resin", "Resina", S.EXTRACTIVE, _EXT),
    _raw("latex", "Látex", S.EXTRACTIVE, _EXT),
    _raw("natural_oil", "Óleo natural", S.EXTRACTIVE, _EXT),
    _raw("herbs", "Ervas", S.EXTRACTIVE, _EXT),
    _raw("sand", "Areia", S.EXTRACTIVE, _EXT),
    _raw("stone", "Pedra", S.EXTRACTIVE, _EXT),
    _raw("chemicals", "Químicos", S.EXTRACTIVE, _EXT, "Químicos", "Químico"),
    _raw("oil", "Petróleo", S.EXTRACTIVE, _EXT, resource="oil"),
    _raw("rubber", "Borracha", S.EXTRACTIVE, _EXT),
    # Mineração (os 9 minerais do 08 §15)
    _raw("iron", "Ferro", S.MINING, _MIN, resource="iron"),
    _raw("copper", "Cobre", S.MINING, _MIN, resource="copper"),
    _raw("silica", "Sílica", S.MINING, _MIN, resource="silica"),
    _raw("coal", "Carvão", S.MINING, _MIN, resource="coal"),
    _raw("salt", "Sal", S.MINING, _MIN, resource="salt"),
    _raw("lithium", "Lítio", S.MINING, _MIN, resource="lithium"),
    _raw("gold", "Ouro", S.MINING, _MIN, resource="gold"),
    _raw("silver", "Prata", S.MINING, _MIN, resource="silver"),
    _raw("diamond", "Diamante", S.MINING, _MIN, resource="diamond"),
)

_N, _Q = NutritionLevel, QolEffect

_MADE = (
    # Industrial / Produção
    _made("cement", "Cimento", S.INDUSTRIAL_PRODUCTION, 1, ("stone", "sand"), _PROD),
    _made("steel", "Aço", S.INDUSTRIAL_PRODUCTION, 2, ("iron", "coal"), _PROD),
    _made("planks", "Tábuas", S.INDUSTRIAL_PRODUCTION, 1, ("wood",), _PROD),
    _made("glass", "Vidro", S.INDUSTRIAL_PRODUCTION, 2, ("sand",), _PROD),
    _made("construction_materials", "Materiais de Construção", S.INDUSTRIAL_PRODUCTION, 3,
          ("cement", "steel", "wood", "glass"), _PROD),
    _made("plastic", "Plástico", S.INDUSTRIAL_PRODUCTION, 2, ("oil",), _PROD),
    _made("fuel", "Combustível", S.INDUSTRIAL_PRODUCTION, 3, ("oil",), _PROD),
    _made("fertilizer", "Fertilizante", S.INDUSTRIAL_PRODUCTION, 2, ("chemicals",), _PROD),
    _made("copper_wire", "Fios de cobre", S.INDUSTRIAL_PRODUCTION, 1, ("copper",), _PROD),
    _made("ppe", "EPIs", S.INDUSTRIAL_PRODUCTION, 3, ("rubber", "plastic", "steel", "clothes", "shoes"), _PROD),
    _made("school_supplies", "Materiais escolares", S.INDUSTRIAL_PRODUCTION, 3,
          ("rubber", "pen", "furniture", "paper"), _PROD),
    _made("hospital_supplies", "Materiais hospitalares", S.INDUSTRIAL_PRODUCTION, 4,
          ("chemicals", "electronic_components", "plastic", "herbs"), _PROD,
          "Materiais hospitalares", "Materiais Hospitalares"),
    # Industrial / Alimentícia
    _made("flour", "Farinha", S.INDUSTRIAL_FOOD, 1, ("wheat",), _FOOD),
    _made("sugar", "Açúcar", S.INDUSTRIAL_FOOD, 1, ("sugar_cane",), _FOOD),
    _made("cheese", "Queijo", S.INDUSTRIAL_FOOD, 1, ("milk",), _FOOD),
    _made("butter", "Manteiga", S.INDUSTRIAL_FOOD, 2, ("milk",), _FOOD),
    _made("ground_coffee", "Café em pó", S.INDUSTRIAL_FOOD, 2, ("coffee_bean",), _FOOD),
    _made("cocoa_butter", "Manteiga de cacau", S.INDUSTRIAL_FOOD, 3, ("cocoa",), _FOOD),
    _made("processed_meat", "Carne processada", S.INDUSTRIAL_FOOD, 2, ("meat",), _FOOD),
    # Industrial / Bens de consumo
    _made("clothes", "Roupas", S.INDUSTRIAL_CONSUMER, 1, ("wool",), _CONS),
    _made("furniture", "Móveis", S.INDUSTRIAL_CONSUMER, 3, ("planks", "steel"), _CONS),
    _made("paper", "Papel", S.INDUSTRIAL_CONSUMER, 2, ("wood", "salt"), _CONS),
    _made("pen", "Caneta", S.INDUSTRIAL_CONSUMER, 1, ("steel", "chemicals"), _CONS),
    _made("shoes", "Calçados", S.INDUSTRIAL_CONSUMER, 1, ("leather",), _CONS, "Calçado", "Calçados"),
    _made("uniform", "Uniforme", S.INDUSTRIAL_CONSUMER, 3, ("clothes", "shoes"), _CONS),
    _made("bread", "Pão", S.INDUSTRIAL_CONSUMER, 1, ("flour",), _CONS),
    _made("chocolate", "Chocolate", S.INDUSTRIAL_CONSUMER, 4, ("cocoa_butter", "sugar", "milk"), _CONS,
          food=FoodDef(_N.LOW, _Q.SMALL_BUFF)),
    _made("pasta", "Macarrão", S.INDUSTRIAL_CONSUMER, 3, ("cheese", "flour", "eggs"), _CONS,
          food=FoodDef(_N.HIGH, _Q.NO_EFFECT)),
    _made("hamburger", "Hambúrguer", S.INDUSTRIAL_CONSUMER, 4, ("cheese", "processed_meat", "bread"), _CONS,
          food=FoodDef(_N.MEDIUM, _Q.SMALL_BUFF)),
    _made("juice", "Suco", S.INDUSTRIAL_CONSUMER, 2, ("fruit", "sugar"), _CONS,
          food=FoodDef(_N.ALMOST_NONE, _Q.SMALL_BUFF)),
    _made("ice_cream", "Sorvete", S.INDUSTRIAL_CONSUMER, 3, ("milk", "sugar", "fruit"), _CONS,
          food=FoodDef(_N.NONE, _Q.MEDIUM_BUFF)),
    _made("sun_dried_meat", "Carne de Sol", S.INDUSTRIAL_CONSUMER, 1, ("meat", "salt"), _CONS,
          food=FoodDef(_N.MEDIUM, _Q.DEBUFF)),
    _made("soda", "Refrigerante", S.INDUSTRIAL_CONSUMER, 2, ("sugar", "juice", "chemicals"), _CONS,
          food=FoodDef(_N.NONE, _Q.MEDIUM_BUFF)),
    _made("car", "Carro", S.INDUSTRIAL_CONSUMER, 5, ("steel", "plastic", "battery", "rubber", "chemicals"), _CONS),
    # Industrial / Tecnológica
    _made("electronic_components", "Componentes eletrônicos", S.INDUSTRIAL_TECHNOLOGY, 1,
          ("copper_wire", "silica", "gold"), _TECH),
    _made("battery", "Bateria", S.INDUSTRIAL_TECHNOLOGY, 2, ("copper", "lithium", "chemicals"), _TECH),
    _made("cellphone", "Celular", S.INDUSTRIAL_TECHNOLOGY, 3, ("electronic_components", "plastic", "battery"), _TECH),
    _made("computer", "Computador", S.INDUSTRIAL_TECHNOLOGY, 4,
          ("electronic_components", "plastic", "steel", "chemicals"), _TECH),
    # Milícia (estrela: "Não existe")
    _made("improvised_weapons", "Armas Improvisadas", S.MILITIA, None, ("steel", "wood", "plastic"), _MIL),
    _made("improvised_armor", "Armaduras Improvisadas", S.MILITIA, None, ("steel", "plastic"), _MIL),
    # O 22 chama o produto da milícia de "Kit Médico" e o do Exército de "Kits médicos": são entidades DISTINTAS
    # (origem diferente). O nome de apresentação ganhou um qualificador para não colidirem.
    _made("militia_medical_kit", "Kit médico (milícia)", S.MILITIA, None, ("wool", "hospital_supplies"), _MIL,
          "Kit Médico"),
)

_PROCURED = (
    ProductDef(key="military_weapons", name="Armas militares", sector=S.MILITARY_PROCUREMENT, source_section=_ARMY,
               source_names=("Armas militares",)),
    ProductDef(key="military_armor", name="Armaduras militares", sector=S.MILITARY_PROCUREMENT, source_section=_ARMY,
               source_names=("Armaduras militares",)),
    ProductDef(key="military_medical_kits", name="Kits médicos militares", sector=S.MILITARY_PROCUREMENT,
               source_section=_ARMY, source_names=("Kits médicos",)),
)

PRODUCTS: Tuple[ProductDef, ...] = _RAW + _MADE + _PROCURED


KNOWN_GAPS: Tuple[Gap, ...] = (
    Gap("GAP_FINISHINGS_UNDEFINED",
        "'Acabamentos' é insumo da receita da Construtora (02 §2.5: Materiais de Construção + Acabamentos → Imóvel), "
        "mas não existe no 22.",
        ("02 §2.5",), ("P1.04", "P1.07")),
    Gap("GAP_OPERATIONAL_MATERIALS_UNDEFINED",
        "Materiais operacionais e 'consumo por funcionário' (02 §10: cada produto operacional tem regra de consumo no "
        "catálogo) não estão no 22: não há lista de produtos operacionais nem consumo.",
        ("02 §10", "02 §20"), ("P1.04",)),
    Gap("GAP_MATRIZ_STARS_UNDEFINED",
        "O 22 dá a estrela mínima dos produtos industriais, mas não a das Matrizes (matérias-primas): a escolha de "
        "produção da Matriz exige 'requisitos de estrelas' (02 §5.2).",
        ("02 §5.2", "02 §14"), ("P1.04",)),
    Gap("GAP_PRODUCTION_QUANTITIES_UNDEFINED",
        "Sem quantidade por insumo, rendimento da receita, nem regra de quantidade produzida por trabalho/funcionário.",
        ("02 §5", "22"), ("P1.04", "P1.05")),
    Gap("GAP_FOOD_VALUES_UNDEFINED",
        "O 22 só dá níveis qualitativos de Nutrição e tipo de efeito de QoL: faltam o ganho de Nutrição e a intensidade "
        "numéricos (04 §15 delega ao catálogo), necessários também para o auto-consumo (04 §16: 'menor ganho').",
        ("04 §15", "04 §16", "05 §6"), ("P1.02",)),
    Gap("GAP_FOOD_PROFILE_BREAD_UNDECLARED",
        "Pão está em 'Bens de consumo' com Nutrição '—' e QoL '—', embora seja ingrediente do Hambúrguer: confirmar se "
        "Pão (e demais alimentos intermediários) é consumível.",
        ("22 §2.3",), ("P1.02",)),
    Gap("GAP_COMMERCIAL_USES_UNDECLARED",
        "Usos e consumidores comerciais ausentes: o 22 só declara uso como insumo de receita e consumo de alimento. "
        "A permissão de compra/venda (02 §4) vem de usos declarados e NÃO é inferida.",
        ("02 §4", "02 §20"), ("P1.04", "P1.05")),
    Gap("GAP_INVENTORY_CATEGORIES_UNDEFINED",
        "O 05 diz que as categorias de inventário vêm do catálogo (05 §3) e lista 'categorias definitivas de itens' e "
        "'itens permanentes e consumíveis' como questões em aberto (05 §22); o 22 só define setor de produção.",
        ("05 §3", "05 §22"), ("P1.02",)),
    Gap("GAP_BASE_PRICE_UNDEFINED",
        "O 17 §20 cita o `preco_base` do catálogo, e o 05 §12 pede 'valor de referência' do item (taxa do correio): o 22 "
        "não tem preço base nem valor de referência.",
        ("17 §20", "05 §12"), ("P1.02", "P1.05")),
    Gap("GAP_VEHICLE_RELATION_UNDEFINED",
        "'Carro' é produto de Bens de consumo (5★), mas veículos foram adiados de propósito (04 §21; 05 §9): não há "
        "relação entre o produto Carro e o veículo ativo/viagem.",
        ("04 §21", "05 §9"), ("sistema de veículos (futuro)",)),
)
