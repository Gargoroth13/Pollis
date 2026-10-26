from decimal import Decimal

from companies import construction
from companies import services as company_services
from companies.tests.test_construction import ConstructionBase
from core import ticks
from geography.models import Lot
from ledger import services as ledger
from ledger.constants import AccountKind
from properties import services
from properties.audit import audit_properties
from properties.models import Auction, LotTitle, TitleEvent

D = Decimal


class PropertiesBase(ConstructionBase):
    """Construtora `build` (Dono boss, pedreiro third), jogadores com dinheiro e o mundo pequeno com lotes de todas as categorias."""

    audit_properties_at_end = True

    def setUp(self):
        super().setUp()
        self.addCleanup(self._audit_properties)
        self.assertTrue(company_services.fund_company(self.boss.pk, self.build, 5_000_000).ok)

    def _audit_properties(self):
        if self.audit_properties_at_end:
            report = audit_properties()
            self.assertTrue(report.ok, report.findings)

    # --- cenários -------------------------------------------------------------------------------------------------------
    def lot(self, category="residential", n=0):
        return list(Lot.objects.filter(category=category).order_by("pk"))[n]

    def player_ref(self, player):
        return {"kind": "player", "id": player.pk}

    def company_ref(self, company):
        return {"kind": "company", "id": company}

    def auction(self, lot=None, min_bid=1_000, duration=3_600):
        lot = lot or self.lot()
        res = services.open_auction(lot.pk, min_bid, duration_seconds=duration)
        self.assertTrue(res.ok, res)
        return res.detail["auction"]

    def bid(self, player, auction, amount, party=None):
        return services.bid(player.pk, auction, party or self.player_ref(player), amount)

    def pass_time(self, seconds):
        self.clk.set(self.clk.now() + seconds)

    def sold_to(self, player, lot=None, price=5_000, party=None, duration=3_600):
        """Leiloa `lot` e o `player` (ou a `party` que ele representa) arremata pelo `price`."""
        auction = self.auction(lot, min_bid=price, duration=duration)
        res = self.bid(player, auction, price, party)
        self.assertTrue(res.ok, res)
        self.pass_time(duration + 1)
        closed = services.close_auction(auction)
        self.assertEqual(closed.detail["status"], "sold", closed)
        return auction

    def money_of(self, kind, entity):
        return ledger.balance_of(services._account(services.OwnerKind(kind), entity))

    def municipality(self, lot):
        return ledger.balance_of(ledger.get_or_create_account(AccountKind.MUNICIPALITY, lot.neighborhood.city_id).pk)

    def tick_world(self):
        return ticks.advance_world()
