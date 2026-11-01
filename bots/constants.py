"""Enumerações do Bot Test (design/21 §21.5-§21.6)."""
from enum import Enum


class Personality(str, Enum):
    """Como o Bot decide (21 §21.5)."""
    CASUAL = "casual"
    OPTIMIZER = "optimizer"          # "Otimizador"
    CONSERVATIVE = "conservative"
    EXPLORER = "explorer"
    CHAOTIC = "chaotic"
    SOCIAL = "social"
    ADVERSARIAL = "adversarial"


class Goal(str, Enum):
    """O que o Bot pretende alcançar (21 §21.5, tabela de 21 §21.6)."""
    WEALTH = "wealth"
    PRESIDENCY = "presidency"
    COMPANIES = "companies"
    CAREER = "career"
    MILITARY = "military"
    EDUCATION = "education"
    PROPERTIES = "properties"
    ORGANIZATIONS = "organizations"
    DISCOVERY = "discovery"


class Specialization(str, Enum):
    """Em que caminho concentra o desenvolvimento (21 §21.5). `NONE` = sem especialização inicial."""
    NONE = "none"
    MINING = "mining"
    EXTRACTIVISM = "extractivism"
    AGRICULTURE = "agriculture"
    INDUSTRY = "industry"
    RETAIL = "retail"
    CONSTRUCTION = "construction"
    MEDICINE = "medicine"
    LAW = "law"


class Archetype(str, Enum):
    """Os 10 arquétipos-base (21 §21.6): combinações iniciais, NÃO caixas rígidas."""
    CASUAL = "casual"
    MAGNATE = "magnate"              # tabela de 21 §21.6 ("Magnata": Otimizador + Riqueza); CLAUDE.md §8 o lista como "Otimizador"
    CONSERVATIVE = "conservative"
    EXPLORER = "explorer"
    CHAOTIC = "chaotic"
    ENTREPRENEUR = "entrepreneur"
    POLITICIAN = "politician"
    SPECIALIST = "specialist"
    SOCIAL = "social"
    ADVERSARIAL = "adversarial"
    CUSTOM = "custom"                # combinação livre de personalidade, objetivo e especialização (21 §21.6, último parágrafo)


ARCHETYPE_DEFAULTS = {
    Archetype.CASUAL: (Personality.CASUAL, Goal.WEALTH),
    Archetype.MAGNATE: (Personality.OPTIMIZER, Goal.WEALTH),
    Archetype.CONSERVATIVE: (Personality.CONSERVATIVE, Goal.WEALTH),
    Archetype.EXPLORER: (Personality.EXPLORER, Goal.DISCOVERY),
    Archetype.CHAOTIC: (Personality.CHAOTIC, Goal.WEALTH),
    Archetype.ENTREPRENEUR: (Personality.OPTIMIZER, Goal.COMPANIES),
    Archetype.POLITICIAN: (Personality.OPTIMIZER, Goal.PRESIDENCY),
    Archetype.SPECIALIST: (Personality.CONSERVATIVE, Goal.CAREER),
    Archetype.SOCIAL: (Personality.SOCIAL, Goal.ORGANIZATIONS),
    Archetype.ADVERSARIAL: (Personality.ADVERSARIAL, Goal.WEALTH),
}


class BotStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"       # admin: não é avaliado (21 §21.60)
    RETIRED = "retired"     # admin: removido da população; a conta e o histórico permanecem


class RunStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"


class WakeReason(str, Enum):
    CREATED = "created"
    PLANNED = "planned"
    ACTION_DONE = "action_done"
    SITUATION_CHANGED = "situation_changed"
    OPPORTUNITY = "opportunity"
    POLITICAL_WINDOW = "political_window"
    EMPLOYMENT_CHANGED = "employment_changed"
    ADMIN = "admin"
