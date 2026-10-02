import enum


class Action(str, enum.Enum):
    """Ações com custo fixo de Energia (04 §2.2). Tratamento depende do sistema de dinheiro: ver CHANGELOG."""
    WORK = "work"
    STUDY = "study"
    LEISURE = "leisure"


ACTION_NAMES = frozenset(a.value for a in Action)
