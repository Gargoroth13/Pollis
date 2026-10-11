"""
Vocabulário do catálogo de Produtos e Receitas (design/22).

Nada aqui é regra de balanceamento: são os NOMES das categorias que o `22` já declara. Valores numéricos (quantidades,
rendimento, Nutrição, intensidade de QoL) NÃO existem neste módulo: o `22` não os fornece e a decisão do Game Director
(2026-10-11) é não inventá-los. Ficam como "não especificado" (`None`), distinto de zero.
"""
import enum


class Sector(str, enum.Enum):
    """De onde o produto vem (22 §2.2 Matriz; §2.3 Industrial e seus sub-tipos; Milícia; compra do governo)."""
    # Matéria-prima: Matriz por terreno (22 §2.2; 02 §2.1)
    AGRO = "agro"                                    # Agropecuária
    EXTRACTIVE = "extractive"                        # Extrativismo
    MINING = "mining"                                # Mineração
    # Industrial (22 §2.3): sub-tipos
    INDUSTRIAL_PRODUCTION = "industrial_production"  # "Produção"
    INDUSTRIAL_FOOD = "industrial_food"              # "Alimentícia"
    INDUSTRIAL_CONSUMER = "industrial_consumer"      # "Bens de consumo"
    INDUSTRIAL_TECHNOLOGY = "industrial_technology"  # "Tecnológica"
    # Produzido por milícias, com receita mas sem estrela ("Não existe")
    MILITIA = "militia"
    # Produtos militares do Exército: sem receita de produção, comprados pelo governo
    MILITARY_PROCUREMENT = "military_procurement"


RAW_SECTORS = frozenset({Sector.AGRO, Sector.EXTRACTIVE, Sector.MINING})
COMPANY_SECTORS = frozenset({Sector.INDUSTRIAL_PRODUCTION, Sector.INDUSTRIAL_FOOD, Sector.INDUSTRIAL_CONSUMER,
                             Sector.INDUSTRIAL_TECHNOLOGY})
# Setores cujos produtos TÊM receita no catálogo.
RECIPE_SECTORS = COMPANY_SECTORS | {Sector.MILITIA}
# Setores em que "estrela mínima" não se aplica (22: "Não existe" para milícia; compra do governo não é produção).
NO_STAR_SECTORS = frozenset({Sector.MILITIA, Sector.MILITARY_PROCUREMENT})

MIN_STARS, MAX_STARS = 1, 5          # 22 usa 1★ a 5★ (02 §14)


class NutritionLevel(str, enum.Enum):
    """Níveis QUALITATIVOS do `22` (coluna Nutrição). Sem número e sem ordem numérica definidos."""
    NONE = "none"                # "nada"
    ALMOST_NONE = "almost_none"  # "quase nada"
    LOW = "low"                  # "pouca"
    MEDIUM = "medium"            # "média"
    HIGH = "high"                # "bastante"


class QolEffect(str, enum.Enum):
    """Tipo do efeito de QoL (coluna 'Efeito de QoL' do `22`). A INTENSIDADE não é especificada."""
    NO_EFFECT = "no_effect"      # "sem efeito"
    SMALL_BUFF = "small_buff"    # "pequeno buff"
    MEDIUM_BUFF = "medium_buff"  # "buff médio"
    DEBUFF = "debuff"            # "debuff"


class UseKind(str, enum.Enum):
    """Usos que o `22` declara HOJE. São DERIVADOS (receitas e perfil de alimento); não há tabela paralela."""
    RECIPE_INPUT = "recipe_input"            # é insumo da receita de outro produto
    PLAYER_CONSUMPTION = "player_consumption"  # consumido pelo jogador como alimento (04 §15)
