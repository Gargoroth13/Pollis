"""
Vocabulário do catálogo de Produtos e Receitas (design/22).

Nada aqui é regra de balanceamento: são os NOMES das categorias que o `22` declara. Valores numéricos NÃO existem neste
módulo: os valores `[PROV]` (decisão do Game Director, 2026-10-14, Q3) vivem em `provisional.py`, numa tabela auditável. Um
valor que nem o `22` nem a tabela provisória fornecem fica "não especificado" (`None`), distinto de zero.
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
    # Produtos militares do Exército: produzidos por empresas Industriais (receitas provisórias, GD 2026-10-14, Q4) e
    # fornecidos ao Exército por contrato federal. O sub-tipo Industrial responsável NÃO está definido (GAP).
    MILITARY_PROCUREMENT = "military_procurement"


RAW_SECTORS = frozenset({Sector.AGRO, Sector.EXTRACTIVE, Sector.MINING})
COMPANY_SECTORS = frozenset({Sector.INDUSTRIAL_PRODUCTION, Sector.INDUSTRIAL_FOOD, Sector.INDUSTRIAL_CONSUMER,
                             Sector.INDUSTRIAL_TECHNOLOGY, Sector.MILITARY_PROCUREMENT})
# Setores cujos produtos TÊM receita no catálogo.
RECIPE_SECTORS = COMPANY_SECTORS | {Sector.MILITIA}
# Setores em que "estrela mínima" não se aplica (22: "Não existe" para milícia).
NO_STAR_SECTORS = frozenset({Sector.MILITIA})
MILITARY_SECTORS = frozenset({Sector.MILITIA, Sector.MILITARY_PROCUREMENT})
# Produtor dos produtos militares do Exército (GD 2026-10-15): empresas Industriais, sub-tipo Produção. O setor
# MILITARY_PROCUREMENT descreve o PRODUTO (fornecido ao Exército por contrato federal); quem o PRODUZ é esta empresa.
ARMY_PRODUCER_SECTOR = Sector.INDUSTRIAL_PRODUCTION

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


class Category(str, enum.Enum):
    """Categoria PRINCIPAL do produto, uma só por produto (GD 2026-10-14, Q6). Características que se sobrepõem
    (consumível, permanente, militar, uso em receita) ficam em campos/tags separados, não nesta categoria."""
    FOOD = "food"              # Alimento
    MATERIAL = "material"      # Material (matéria-prima e insumo intermediário)
    EQUIPMENT = "equipment"    # Equipamento
    DURABLE = "durable"        # Durável
    MILITARY = "military"      # Militar


class Channel(str, enum.Enum):
    """Canal comercial DECLARADO no catálogo (GD 2026-10-14, Q8). Nenhum canal é inferido do nome nem dos ingredientes."""
    RETAIL_SALE = "retail_sale"                # Varejo vende o bem final aos jogadores
    INTER_COMPANY = "inter_company"            # circula entre empresas (matéria-prima, intermediário, bem final p/ revenda)
    ARMY_PROCUREMENT = "army_procurement"      # fornecimento ao Exército por contrato com o governo federal (19.11, Fluxo B)
    SPECIAL_REQUISITION = "special_requisition"  # compra anônima da milícia por Requisição Especial (19.11, Fluxo A)


class UseKind(str, enum.Enum):
    """Usos declarados no catálogo. Insumo e consumo são DERIVADOS (receitas e perfil de alimento); os canais comerciais são
    DECLARADOS no produto. Não há tabela paralela de permissões."""
    RECIPE_INPUT = "recipe_input"            # é insumo da receita de outro produto
    PLAYER_CONSUMPTION = "player_consumption"  # consumido pelo jogador como alimento (04 §15)
    COMMERCIAL_CHANNEL = "commercial_channel"  # canal comercial declarado (Q8)
    MILITARY_ACTION = "military_action"      # recurso de ações militares (19): produtos com a tag militar
