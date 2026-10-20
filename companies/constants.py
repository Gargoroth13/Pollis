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
    """
    Cargos (02). O Dono (§16) nasce com a empresa. Os demais são VAGAS abertas pelo Dono no mural (§15):
    `WORKER` funcionário de produção; `ENGINEER`/`LAWYER` cargos de suporte (§9; seus efeitos entram em P1.04d);
    `SALESPERSON` vendedor do Varejo (§11.2; efeito em P1.04e). O que cada cargo FAZ na operação é de etapas seguintes.
    """
    OWNER = "owner"
    WORKER = "worker"
    ENGINEER = "engineer"
    LAWYER = "lawyer"
    SALESPERSON = "salesperson"


class PositionStatus(str, enum.Enum):
    OPEN = "open"            # vaga no mural, sem ocupante
    FILLED = "filled"        # ocupada (o Dono nasce FILLED)
    CLOSED = "closed"        # encerrada: fora do mural; o histórico fica


class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"      # o candidato desistiu
    CANCELLED = "cancelled"      # sem decisão: vaga fechada/preenchida ou candidato contratado em outro lugar


class EventKind(str, enum.Enum):
    """Trilha imutável do mural e do vínculo (auditoria)."""
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    APPLIED = "applied"
    WITHDRAWN = "withdrawn"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    HIRED = "hired"
    RESIGNED = "resigned"
    DISMISSED = "dismissed"


MAX_NAME_LENGTH = 80
MAX_SALARY_CENTS = 10 ** 12          # só barra valor absurdo; o teto real do salário é S/T do registro monetário (24 §24.12)
MAX_REQUIREMENT_LEVEL = 10 ** 6      # só barra valor absurdo; os níveis reais são de Skills (01 §1.9)
MURAL_PAGE_LIMIT = 200               # técnico: o mural público é paginado (não é regra de jogo)


class StockOperation(str, enum.Enum):
    """Tipo do movimento do estoque empresarial (05 §17, §19). Só existe o que o design documenta."""
    PRODUCTION = "production"                      # entra: o trabalho de um funcionário (02 §6-7)
    PURCHASE = "purchase"                          # entra: compra de outra empresa/mercado (P1.05/P1.08)
    INPUT_CONSUMPTION = "input_consumption"        # sai: insumo da receita consumido pela produção (02 §5, §20)
    SALE = "sale"                                  # sai: venda (Varejo, P1.04e/P1.05)


STOCK_CREDIT_OPERATIONS = frozenset({StockOperation.PRODUCTION, StockOperation.PURCHASE})
STOCK_DEBIT_OPERATIONS = frozenset({StockOperation.INPUT_CONSUMPTION, StockOperation.SALE})
# O que OUTROS sistemas podem pedir por `credit_stock`/`debit_stock` (a produção e o insumo só nascem dentro do Trabalho).
EXTERNAL_STOCK_CREDIT = frozenset({StockOperation.PURCHASE})
EXTERNAL_STOCK_DEBIT = frozenset({StockOperation.SALE})
MAX_STOCK_QUANTITY = 10 ** 12
