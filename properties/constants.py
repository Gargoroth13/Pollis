"""Enumerações dos Imóveis (design/10). Listas fechadas."""
import enum


class OwnerKind(str, enum.Enum):
    """10 §3: jogadores e empresas possuem propriedades privadas; o governo mantém o que é de uso público (e os lotes ainda não leiloados)."""
    GOVERNMENT = "government"
    PLAYER = "player"
    COMPANY = "company"


class BuildingFamily(str, enum.Enum):
    """Famílias de imóvel (10 §5-6, §16-17; G5, GD 2026-10-29): residencial (unidades, QoL), comercial (nível 1–5 ≥ estrela da empresa) e industrial (tipo único, sem nível)."""
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"


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


class RentListingStatus(str, enum.Enum):
    OPEN = "open"
    RENTED = "rented"
    CANCELLED = "cancelled"


# Aluguel (10 §9-13): natureza `RENT` do inquilino ao proprietário, via contrato do tipo `rent` do motor de `18`.
RENT_FREQUENCIES = ("daily", "weekly", "monthly")                 # periodicidade (10 §10); "única" não faz sentido para uso contínuo


class UseChangeStatus(str, enum.Enum):
    """Mudança de uso (10 §21; G6, GD 2026-10-29): só as APROVADAS ficam registradas; a recusa é um código explicado (20)."""
    APPROVED = "approved"
