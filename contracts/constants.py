"""Enumerações do motor de contratos (design/18). Listas fechadas: nada de texto livre onde o design define categorias."""
import enum


class ContractType(str, enum.Enum):
    """18.2: tipos do Bot Test. Só os tipos com handler registrado podem ser propostos (o aluguel chega com P1.07, o governamental com P1.09)."""
    SUPPLY = "supply"
    LOAN = "loan"
    RENT = "rent"
    GOVERNMENT = "government"
    MILITARY = "military"                      # 18.14 (P1.17)


class Status(str, enum.Enum):
    """18.3: ativo, inadimplente, encerrado ou quebrado + dois estados TÉCNICOS da proposta (antes do aceite das duas partes)."""
    PROPOSED = "proposed"                      # técnico: aguardando o aceite da outra parte
    CANCELLED = "cancelled"                    # técnico: proposta recusada ou retirada (nunca entrou em vigor)
    ACTIVE = "active"
    DEFAULTED = "defaulted"                    # inadimplente
    CLOSED = "closed"                          # encerrado normalmente (18.9)
    BROKEN = "broken"                          # quebrado: quebra voluntária ou por inadimplência (18.7)


ENDED_STATUSES = frozenset({Status.CANCELLED, Status.CLOSED, Status.BROKEN})
RUNNING_STATUSES = frozenset({Status.ACTIVE, Status.DEFAULTED})


class Frequency(str, enum.Enum):
    """18.3: única, diária, semanal, mensal (mês de calendário do jogo, como o `MONTHLY` do relógio)."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class PartyKind(str, enum.Enum):
    PLAYER = "player"
    COMPANY = "company"
    # governo/milícia entram com P1.09/P1.17 pelos handlers dos seus tipos


class Side(str, enum.Enum):
    A = "a"
    B = "b"


class EventKind(str, enum.Enum):
    """18.11: criação, aceite de cada parte, pagamentos, entregas, falhas, multas, encerramento, quebra antecipada."""
    CREATED = "created"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    WITHDRAWN = "withdrawn"
    ACTIVATED = "activated"
    DISBURSED = "disbursed"                    # empréstimo: principal entregue ao tomador
    EXECUTED = "executed"                      # ocorrência cumprida (entrega + pagamento, ou parcela paga)
    FAILED = "failed"                          # ocorrência não cumprida (qual obrigação, quem, quanto ficou pendente)
    DEFAULT_ENTERED = "default_entered"
    DEFAULT_CURED = "default_cured"
    OBLIGATION_SETTLED = "obligation_settled"  # dívida gerada por falha quitada depois
    PENALTY_APPLIED = "penalty_applied"
    BREAK_REQUESTED = "break_requested"
    REMAINING_CANCELLED = "remaining_cancelled"
    CLOSED = "closed"
    BROKEN = "broken"


class ExecutionStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class Responsible(str, enum.Enum):
    A = "a"
    B = "b"
    SYSTEM = "system"                          # falha que nenhuma parte causou (registro técnico recusado)


# Linguagem de referência no registro monetário e no estoque.
REFERENCE_KIND = "contract"
KEY_PREFIX = "contract:"

MAX_OCCURRENCES = 1000                         # [PROV] limite técnico do número de ocorrências de um contrato
