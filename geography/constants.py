"""
Constantes ESTRUTURAIS de design/08 (FINAL — BOT TEST). Nada aqui é calibração livre.
Os parâmetros de CENÁRIO (quantos estados, escalas, plano de bairros...) ficam em balance.py.
"""
import enum
from decimal import Decimal


class Category(str, enum.Enum):
    """Categorias de uso de lote (08 §5) e, portanto, de zoneamento (08 §16)."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    INSTITUTIONAL = "institutional"
    SPECIAL = "special"
    RURAL = "rural"


CATEGORIES = tuple(Category)
CATEGORY_NAMES = frozenset(c.value for c in Category)
LABELS = {Category.RESIDENTIAL: "Residencial", Category.COMMERCIAL: "Comercial", Category.INDUSTRIAL: "Industrial",
          Category.INSTITUTIONAL: "Institucional", Category.SPECIAL: "Especial", Category.RURAL: "Rural"}

# 08 §6: capacidade base. Rural NÃO está na tabela: "definida pela estrutura territorial".
CAPACITY_BASE = {
    Category.RESIDENTIAL: 50,
    Category.COMMERCIAL: 30,
    Category.INDUSTRIAL: 20,
    Category.INSTITUTIONAL: 5,
    Category.SPECIAL: 10,
}

# 08 §3.1: "A cidade possuirá inicialmente 25 bairros."
NEIGHBORHOODS_PER_CITY = 25


class Occupation(str, enum.Enum):
    """Estado de ocupação do lote (08 §5). As transições pertencem ao sistema de Imóveis (10), não à Geografia."""
    EMPTY = "empty"
    OCCUPIED = "occupied"


class Resource(str, enum.Enum):
    OIL = "oil"
    IRON = "iron"
    COPPER = "copper"
    SILICA = "silica"
    COAL = "coal"
    SALT = "salt"
    LITHIUM = "lithium"
    GOLD = "gold"
    SILVER = "silver"
    DIAMOND = "diamond"


RESOURCES = tuple(Resource)
RESOURCE_NAMES = frozenset(r.value for r in Resource)


class ResourceKind(str, enum.Enum):
    EXTRACTIVE = "extractive"  # Extrativismo
    MINERAL = "mineral"        # Mineração


# 08 §12: "O petróleo pertence exclusivamente à categoria de Extrativismo, e não à Mineração."
RESOURCE_KIND = {r: ResourceKind.MINERAL for r in Resource}
RESOURCE_KIND[Resource.OIL] = ResourceKind.EXTRACTIVE

# 08 §15: "Valores iniciais para Bot Test" (raridade). O petróleo NÃO tem valor no 08: §14 só diz "raro" e
# remete os parâmetros ao sistema de recursos/produtos (22).
RARITY_BASE = {
    Resource.IRON: Decimal("0.20"), Resource.COPPER: Decimal("0.10"), Resource.SILICA: Decimal("0.30"),
    Resource.COAL: Decimal("0.15"), Resource.SALT: Decimal("0.12"), Resource.LITHIUM: Decimal("0.06"),
    Resource.GOLD: Decimal("0.02"), Resource.SILVER: Decimal("0.04"), Resource.DIAMOND: Decimal("0.01"),
}

DISTANCE_METRICS = ("euclidean", "manhattan")
