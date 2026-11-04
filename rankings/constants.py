"""
Catálogo das 15 categorias do design/14 (14.3 ao vivo: 11; 14.4 históricas: 4) e o ESTADO de cada uma nesta entrega.

A numeração segue a ordem do próprio documento: ao vivo 1–11 (14.3.1–14.3.11) e históricas 12–15 (14.4.1–14.4.4).
Nenhuma categoria é removida: as que ainda não têm fonte de dados aparecem com o estado e a dependência EXPLÍCITOS, e nunca
com valores inventados (14.2: "o ranking deve sempre utilizar dados que já existam no jogo").
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


class Group(str, enum.Enum):
    LIVE = "live"
    HISTORICAL = "historical"


class Status(str, enum.Enum):
    ACTIVE = "active"                    # fonte existe na main e o ranking funciona
    PENDING_SOURCE = "pending_source"    # a fonte pertence a outro sistema ainda não integrado (ver `depends_on`)
    PENDING_DESIGN = "pending_design"    # decisão técnica/design em aberto (ver `depends_on`)
    OUT_OF_SCOPE = "out_of_scope"        # fora do Bot Test por decisão do design/GD


class Cat(str, enum.Enum):
    # ao vivo (14.3)
    NET_WORTH = "net_worth"                      # 1  14.3.1
    BIGGEST_COMPANY = "biggest_company"          # 2  14.3.2
    PRODUCTION = "production"                    # 3  14.3.3
    QOL = "qol"                                  # 4  14.3.4
    POLITICAL_INFLUENCE = "political_influence"  # 5  14.3.5
    BIGGEST_EMPLOYER = "biggest_employer"        # 6  14.3.6
    TAXPAYER = "taxpayer"                        # 7  14.3.7
    BEST_SCHOOL = "best_school"                  # 8  14.3.8
    BIGGEST_ORGANIZATION = "biggest_organization"  # 9  14.3.9
    OLDEST_ACCOUNT = "oldest_account"            # 10 14.3.10
    ACTIVE_TIME = "active_time"                  # 11 14.3.11
    # históricas (14.4)
    NET_WORTH_RECORD = "net_worth_record"        # 12 14.4.1
    COMPANY_RECORD = "company_record"            # 13 14.4.2
    ACTIVE_TIME_RECORD = "active_time_record"    # 14 14.4.3
    PRESIDENT_VOTE_RECORD = "president_vote_record"  # 15 14.4.4


ENTITY_PLAYER = "player"
ENTITY_COMPANY = "company"
ENTITY_SCHOOL = "school"
ENTITY_ORGANIZATION = "organization"
ENTITY_TYPES = (ENTITY_PLAYER, ENTITY_COMPANY, ENTITY_SCHOOL, ENTITY_ORGANIZATION)


@dataclass(frozen=True)
class CategorySpec:
    key: Cat
    number: int
    group: Group
    label: str
    design_ref: str
    status: Status
    unit: str = ""                       # "centavos", "segundos", "percentual"...; vazio quando o valor é ordinal/múltiplo
    window_days: Optional[int] = None
    source: str = ""                     # de onde o dado vem (auditoria, 14.9)
    depends_on: str = ""                 # para estados pendentes: o que falta e quem entrega


_S = CategorySpec
_L, _H = Group.LIVE, Group.HISTORICAL

CATEGORIES: Tuple[CategorySpec, ...] = (
    _S(Cat.NET_WORTH, 1, _L, "Maior patrimônio líquido", "14.3.1", Status.ACTIVE, "centavos",
       source="ledger.Account.balance (saldo bruto, inclui o reservado) + créditos a receber − obrigações a pagar (ledger.Obligation abertas)"),
    _S(Cat.BIGGEST_COMPANY, 2, _L, "Maior empresa", "14.3.2", Status.PENDING_SOURCE,
       depends_on="estrelas e funcionários da empresa: P1.04a/b (PRs #15/#16), ainda não integrados à main"),
    _S(Cat.PRODUCTION, 3, _L, "Maior produção (14 dias)", "14.3.3", Status.PENDING_SOURCE, window_days=14,
       depends_on="registro de produção efetiva por produto: P1.04c (PR #17), ainda não integrado à main"),
    _S(Cat.QOL, 4, _L, "Melhor QoL pessoal", "14.3.4", Status.PENDING_DESIGN,
       depends_on="snapshot comparável de QoL (referência de tempo comum): proposta em design/14a, aguardando o Game Director"),
    _S(Cat.POLITICAL_INFLUENCE, 5, _L, "Maior influência política", "14.3.5", Status.OUT_OF_SCOPE,
       depends_on="fora do Bot Test até existir métrica objetiva documentada (14.3.5, 14.10)"),
    _S(Cat.BIGGEST_EMPLOYER, 6, _L, "Maior empregador", "14.3.6", Status.PENDING_SOURCE,
       depends_on="vínculos de emprego e propriedade das empresas: P1.04a/b (PRs #15/#16), ainda não integrados à main"),
    _S(Cat.TAXPAYER, 7, _L, "Maior contribuinte (30 dias)", "14.3.7", Status.ACTIVE, "centavos", window_days=30,
       source="ledger.Entry de natureza tax_* (não estornado), pela conta pagadora (jogador ou empresa), dias de competência fechados"),
    _S(Cat.BEST_SCHOOL, 8, _L, "Melhor escola/universidade", "14.3.8", Status.PENDING_SOURCE,
       depends_on="qualidade da escola: P1.06a (PR #21), ainda não integrado à main"),
    _S(Cat.BIGGEST_ORGANIZATION, 9, _L, "Maior organização", "14.3.9", Status.PENDING_SOURCE,
       depends_on="membros de milícia: P1.17 (Militar), ainda não implementado"),
    _S(Cat.OLDEST_ACCOUNT, 10, _L, "Conta mais antiga", "14.3.10", Status.ACTIVE, "segundos",
       source="players.Player.created_at_game"),
    _S(Cat.ACTIVE_TIME, 11, _L, "Maior tempo ativo (sequência atual)", "14.3.11", Status.ACTIVE, "segundos",
       source="rankings.ActivityStreak: sequência corrente ainda ativa (< 72 h desde a última ação válida do Action Registry)"),
    _S(Cat.NET_WORTH_RECORD, 12, _H, "Maior patrimônio líquido já alcançado", "14.4.1", Status.ACTIVE, "centavos",
       source="rankings.RankingHistorico (atualizado em ações do jogador e na varredura diária)"),
    _S(Cat.COMPANY_RECORD, 13, _H, "Maior empresa já alcançada", "14.4.2", Status.PENDING_SOURCE,
       depends_on="estrelas e pico de funcionários: P1.04a/b (PRs #15/#16), ainda não integrados à main"),
    _S(Cat.ACTIVE_TIME_RECORD, 14, _H, "Maior tempo ativo já alcançado", "14.4.3", Status.ACTIVE, "segundos",
       source="rankings.RankingHistorico (atualizado a cada ação que estende a maior sequência)"),
    _S(Cat.PRESIDENT_VOTE_RECORD, 15, _H, "Presidente com maior percentual de votos", "14.4.4", Status.PENDING_SOURCE, "percentual",
       depends_on="resultado de eleição presidencial: P1.11 (Política). A interface de registro existe; nenhum chamador ainda"),
)

BY_KEY: Dict[Cat, CategorySpec] = {c.key: c for c in CATEGORIES}
LIVE = tuple(c for c in CATEGORIES if c.group == Group.LIVE)
HISTORICAL = tuple(c for c in CATEGORIES if c.group == Group.HISTORICAL)


def spec(key) -> CategorySpec:
    """Categoria pelo identificador; desconhecida → ValueError (nunca um ranking vazio enganoso)."""
    try:
        return BY_KEY[Cat(key)]
    except ValueError:
        raise ValueError(f"categoria inexistente: {key!r}") from None
