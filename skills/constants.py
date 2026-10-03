import enum


class Skill(str, enum.Enum):
    """Exatamente 3 skills de jogador (01 §1). As antigas categorias (Indústria, Comércio...) são
    classificações de EMPRESAS, não skills."""
    INTELLIGENCE = "intelligence"
    PHYSICAL = "physical"
    CHARISMA = "charisma"


SKILLS = tuple(Skill)
SKILL_NAMES = frozenset(s.value for s in Skill)

# Apresentação (pt-BR). A regra usa sempre o valor do enum; isto é só para a interface.
LABELS = {Skill.INTELLIGENCE: "Inteligência", Skill.PHYSICAL: "Físico", Skill.CHARISMA: "Carisma"}
