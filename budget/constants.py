"""Constantes do Orçamento Público (design/09). Listas FECHADAS: item novo exige decisão do GD (CLAUDE.md §12)."""
import enum


class Level(str, enum.Enum):
    """Níveis de governo (09 §2): Federal → Estados → Municípios."""
    UNION = "union"
    STATE = "state"
    MUNICIPALITY = "municipality"


class Area(str, enum.Enum):
    """Áreas de governo (09 §5, §12). `military` é só federal (09 45.8); 'Segurança/Defesa local' não tem mecânica no primeiro Bot Test (45.2)."""
    EDUCATION = "education"
    HEALTH = "health"
    INFRASTRUCTURE = "infrastructure"
    ADMINISTRATION = "administration"
    SOCIAL_PROGRAMS = "social_programs"
    MILITARY = "military"


# Áreas que o Prefeito distribui no orçamento municipal (09 §5). Militar é federal; não aparece no orçamento municipal.
MUNICIPAL_AREAS = (Area.EDUCATION, Area.HEALTH, Area.INFRASTRUCTURE, Area.ADMINISTRATION, Area.SOCIAL_PROGRAMS)
# Pisos legais (11 §11.2.1): só Educação, Saúde e Infraestrutura, só no orçamento municipal.
FLOOR_AREAS = (Area.EDUCATION, Area.HEALTH, Area.INFRASTRUCTURE)


class DecisionKind(str, enum.Enum):
    """Decisões políticas registradas e públicas (09 §27: "devem ser registradas e publicamente visíveis")."""
    TRANSFER = "transfer"
    PLAN_CONFIRMED = "plan_confirmed"


class PlanStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
