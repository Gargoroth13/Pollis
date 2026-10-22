"""Vocabulário da Transparência de Mercado (design/17)."""
import enum

WINDOW_24H = 24 * 3600
TREND_DAYS = 7                  # 17.8: 7 dias contra os 7 dias anteriores
CHART_DAYS = 30                 # 17.13: gráficos de 30 dias
MAX_QUANTITY = 10 ** 9
MAX_UNIT_PRICE_CENTS = 10 ** 12
NO_DATA = "NO_DATA"             # 17.9: "Sem dados" (nunca zero, nunca o preço-base do catálogo)
OK = "OK"


class Channel(str, enum.Enum):
    """Por onde a venda ocorreu (os sistemas que realizam a transação; 17.2). O histórico guarda o canal para filtros futuros."""
    RETAIL = "retail"                    # Varejo → jogador (02 §11)
    INTER_COMPANY = "inter_company"      # entre empresas
    PLAYER_MARKET = "player_market"      # Mercado de Jogadores (05 §13)
    CONTRACT = "contract"                # contrato de fornecimento (18)


class PartyKind(str, enum.Enum):
    PLAYER = "player"
    COMPANY = "company"


class CostCategory:
    """Categorias de custo da empresa (17.16). Insumos comprados são `input:<produto>`."""
    SALARIES = "salaries"
    TAXES = "taxes"
    INPUT_PREFIX = "input:"
