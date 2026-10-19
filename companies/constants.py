"""
Vocabulário das Empresas (design/02). Valores que o design DEFINE (tipos, custo de fundação, cargo Dono) vivem aqui; números de
balanceamento `[PROV]` estão em `params.py`.
"""
import enum

from ledger.money import from_reais


class CompanyType(str, enum.Enum):
    """Tipos de empresa (02 §1). Financeira é uma especialização de Serviços (02 §2.6), mas tem tipo e custo próprios (02 §17)."""
    RETAIL = "retail"                # Varejo
    SERVICES = "services"            # Serviços
    MATRIX = "matrix"                # Matriz
    INDUSTRIAL = "industrial"        # Industrial
    CONSTRUCTION = "construction"    # Construtora
    FINANCIAL = "financial"          # Financeira


# Custo de fundação (02 §17, "valores atualmente definidos"), em reais; o registro monetário trabalha em centavos.
FOUNDING_COST_REAIS = {
    CompanyType.RETAIL: 15_000,
    CompanyType.SERVICES: 25_000,
    CompanyType.MATRIX: 40_000,
    CompanyType.CONSTRUCTION: 60_000,
    CompanyType.INDUSTRIAL: 80_000,
    CompanyType.FINANCIAL: 100_000,
}
FOUNDING_COST_CENTS = {t: from_reais(v) for t, v in FOUNDING_COST_REAIS.items()}


class PositionKind(str, enum.Enum):
    """Cargos. Nesta etapa só existe o Dono (02 §16), criado automaticamente na fundação; os demais entram com o mural (P1.04b)."""
    OWNER = "owner"


MAX_NAME_LENGTH = 80
MAX_SALARY_CENTS = 10 ** 12          # só barra valor absurdo; o teto real do salário é S/T do registro monetário (24 §24.12)
