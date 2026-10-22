"""Vocabulário das Escolas (design/03)."""
import enum

MATERIALS_PRODUCT = "school_supplies"      # Materiais escolares (22): o que determina a Qualidade Base (03 §8)
MAX_MATERIALS_PER_MOVEMENT = 10 ** 9
MAX_NAME = 80
MIN_STARS, MAX_STARS = 1, 5


class SchoolKind(str, enum.Enum):
    PUBLIC = "public"          # orçamento do governo (03 §5)
    PRIVATE = "private"        # controlada por um jogador (03 §6)


class MaterialOperation(str, enum.Enum):
    PURCHASE = "purchase"      # entra: compra de materiais (P1.05b liga o pagamento)
    DECAY = "decay"            # sai: decaimento diário (03 §9)


class EnrollmentEnd(str, enum.Enum):
    TRANSFER = "transfer"      # trocou de escola no mesmo bairro (03 §2)
