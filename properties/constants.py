"""Enumerações dos Imóveis (design/10). Listas fechadas."""
import enum


class OwnerKind(str, enum.Enum):
    """10 §3: jogadores e empresas possuem propriedades privadas; o governo mantém o que é de uso público (e os lotes ainda não leiloados)."""
    GOVERNMENT = "government"
    PLAYER = "player"
    COMPANY = "company"


class TitleReason(str, enum.Enum):
    AUCTION = "auction"                        # 10 §4: lote público arrematado
    SALE = "sale"                              # 10 §8: venda entre proprietários


class AuctionStatus(str, enum.Enum):
    OPEN = "open"
    SOLD = "sold"
    UNSOLD = "unsold"                          # encerrou sem lances
    INVALIDATED = "invalidated"                # arrematação invalidada: o vencedor não pôde pagar (10 §4.4)


class ListingStatus(str, enum.Enum):
    OPEN = "open"
    SOLD = "sold"
    CANCELLED = "cancelled"


class SiteStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"


# Natureza do pagamento do leilão: `AUCTION_PAYMENT` (arrematante → Município do lote; 24 Q2). Venda de imóvel: `SALE` sem imposto (24 §24.7).
