"""
Vocabulário do registro monetário (design/24, FINAL — BOT TEST).

Nada aqui é balanceamento. Valores `[PROV]` (design/24 §24.4): `MAX_AMOUNT`.
"""
import enum

# Todo valor do registro é um INTEIRO DE CENTAVOS (design/24 §24.4).
CENTAVOS_PER_REAL = 100
MAX_AMOUNT = 10 ** 15            # [PROV] R$ 10 trilhões: limite técnico por lançamento e por saldo (11 §11.1.1)


class AccountKind(str, enum.Enum):
    PLAYER = "player"
    COMPANY = "company"
    UNION = "union"                  # caixa federal (singleton)
    STATE = "state"
    MUNICIPALITY = "municipality"    # Município = City do 08 (R8)
    MILITIA_BANK = "militia_bank"
    RETENTION = "retention"          # custódia (escrow de contrato; arrecadação retida)
    SINK = "sink"                    # sumidouro (singleton): só recebe
    ISSUANCE = "issuance"            # contrapartida técnica da emissão (singleton): única que pode ficar negativa


OPERATIONAL_KINDS = frozenset({AccountKind.PLAYER, AccountKind.COMPANY, AccountKind.UNION, AccountKind.STATE,
                               AccountKind.MUNICIPALITY, AccountKind.MILITIA_BANK})
SINGLETON_KINDS = frozenset({AccountKind.UNION, AccountKind.SINK, AccountKind.ISSUANCE})

# Papéis de dotação (design/24 §24.11) e os tipos de conta que cada um pode receber. Lista FECHADA com o que o §24.11 nomeia
# (jogador/Bot, União, Estados, Municípios, bancos de milícia); papel novo ou outro tipo de conta exige mudar o documento.
GRANT_ROLE_KINDS = {
    "player": frozenset({AccountKind.PLAYER}),
    "union": frozenset({AccountKind.UNION}),
    "state": frozenset({AccountKind.STATE}),
    "municipality": frozenset({AccountKind.MUNICIPALITY}),
    "militia_bank": frozenset({AccountKind.MILITIA_BANK}),
}


class Nature(str, enum.Enum):
    """Natureza FECHADA do lançamento (design/24 §24.8). Nova natureza exige mudar o documento."""
    # remuneração: só por submit/liquidate_remuneration (contadores C_S/C_T)
    WAGE = "wage"
    MILITARY_PAY = "military_pay"
    OWNER_SALARY = "owner_salary"
    POLITICAL_SALARY = "political_salary"
    # impostos
    TAX_SALES = "tax_sales"
    TAX_INCOME = "tax_income"
    TAX_PROPERTY = "tax_property"
    # comércio, governo e contratos
    SALE = "sale"
    SUBSIDY = "subsidy"
    GOV_TRANSFER = "gov_transfer"
    PUBLIC_WORKS_PAYMENT = "public_works_payment"
    RENT = "rent"
    TUITION = "tuition"
    LOAN_PRINCIPAL = "loan_principal"
    LOAN_REPAYMENT = "loan_repayment"
    LOAN_INTEREST = "loan_interest"
    BOND_PURCHASE = "bond_purchase"
    BOND_INTEREST = "bond_interest"
    BOND_REDEMPTION = "bond_redemption"
    PENALTY = "penalty"
    DONATION = "donation"
    REIMBURSEMENT = "reimbursement"
    INDEMNITY = "indemnity"
    # cobranças do sistema
    TRAVEL_FEE = "travel_fee"
    MAIL_FEE = "mail_fee"
    COMPANY_FOUNDING = "company_founding"
    AUCTION_PAYMENT = "auction_payment"
    TREATMENT = "treatment"
    # milícia e campanhas (destino: sumidouro)
    MILITIA_FOUNDING = "militia_founding"
    MILITIA_UPGRADE = "militia_upgrade"
    CAMPAIGN_COST = "campaign_cost"
    # custódia
    RETENTION_IN = "retention_in"
    RETENTION_RELEASE = "retention_release"
    RETENTION_REFUND = "retention_refund"
    # emissão e correção técnica
    SCENARIO_GRANT = "scenario_grant"
    REVERSAL = "reversal"


REMUNERATION_NATURES = frozenset({Nature.WAGE, Nature.MILITARY_PAY, Nature.OWNER_SALARY, Nature.POLITICAL_SALARY})
# 11 §11.1.0: C_S conta trabalho, soldo e salário do Dono; C_T conta TODA remuneração (inclui a política).
COUNTS_IN_C_S = frozenset({Nature.WAGE, Nature.MILITARY_PAY, Nature.OWNER_SALARY})
COUNTS_IN_C_T = REMUNERATION_NATURES
TAX_NATURES = frozenset({Nature.TAX_SALES, Nature.TAX_INCOME, Nature.TAX_PROPERTY})
SINK_NATURES = frozenset({Nature.MILITIA_FOUNDING, Nature.MILITIA_UPGRADE, Nature.CAMPAIGN_COST})
RETENTION_OUT_NATURES = frozenset({Nature.RETENTION_RELEASE, Nature.RETENTION_REFUND, Nature.REVERSAL})
RETENTION_IN_NATURES = frozenset({Nature.RETENTION_IN, Nature.REVERSAL}) | TAX_NATURES


class HoldStatus(str, enum.Enum):
    ACTIVE = "active"
    RELEASED = "released"
    CONSUMED = "consumed"


class ObligationStatus(str, enum.Enum):
    OPEN = "open"
    PAID = "paid"
    CANCELLED = "cancelled"


class Policy(str, enum.Enum):
    """O que fazer quando o pagador não tem caixa para uma remuneração reconhecida (decidido pelo sistema pagador)."""
    PENDING = "pending"     # reconhece e vira obrigação pendente
    REFUSE = "refuse"       # não reconhece nada


class RequestStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    RECOGNIZED = "recognized"
    REFUSED = "refused"
