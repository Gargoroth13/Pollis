"""Vocabulário do Histórico do Mundo (design/12): categorias do feed (12.1) e prioridades internas (12.13)."""
from __future__ import annotations

from enum import Enum, IntEnum

SERVER_NAME = "Nova Polis"


class Category(str, Enum):
    POLITICS = "politics"
    ECONOMY = "economy"
    CONFLICT = "conflict"
    SOCIETY = "society"
    MILESTONE = "milestone"


CATEGORY_LABELS = {
    Category.POLITICS: "Política",
    Category.ECONOMY: "Economia",
    Category.CONFLICT: "Conflito",
    Category.SOCIETY: "Sociedade",
    Category.MILESTONE: "Marco",
}


class Priority(IntEnum):
    """Ordem de 12.13 (1 = mais importante). Só desempata acontecimentos simultâneos; nunca é mostrada ao jogador."""
    GOVERNMENT_CHANGE = 1
    CONFLICT = 2
    ELECTION = 3
    BANKRUPTCY = 4
    MAJOR_ECONOMIC = 5
    MILESTONE = 6
    MINOR_ECONOMIC = 7


class Status:
    """Resultado de `publish`."""
    PUBLISHED = "published"
    DUPLICATE = "duplicate"              # a mesma chave de idempotência já foi publicada: nada é duplicado
    SUPPRESSED = "suppressed"            # intervalo mínimo entre notícias do mesmo indicador (12.12)
    NOT_NEWSWORTHY = "not_newsworthy"    # a regra de relevância do próprio 12 recusa (ex.: falência abaixo de 5★, 12.5)


class Office(str, Enum):
    PRESIDENT = "president"
    GOVERNOR = "governor"
    MAYOR = "mayor"
    CHAMBER = "chamber"


class RefKind:
    COMPANY = "company"
    PRODUCT = "product"
    LAW = "law"
    OFFICE = "office"
    ACTION = "action"
