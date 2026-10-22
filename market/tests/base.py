from companies.tests.test_production import ProductionBase
from core.models import WorldClock
from ledger import services as ledger
from ledger.constants import Nature
from ledger.money import competence_day_of
from market import recording, rollup
from market.audit import audit_market
from market.constants import PartyKind
from players.tests.base import T0


class MarketBase(ProductionBase):
    """Indústria (Farinha), Dono, funcionário, jogadores com dinheiro. Vendas de teste movem dinheiro de verdade antes de registrar."""

    audit_market_at_end = True

    def setUp(self):
        super().setUp()
        self.addCleanup(self._audit_market)
        self.day0 = competence_day_of(T0)
        self._seq = 0
        self.addCleanup(rollup.unregister_supply_provider, "test_supply")

    def _audit_market(self):
        if self.audit_market_at_end:
            report = audit_market()
            self.assertTrue(report.ok, report.findings)

    def at(self, day_offset, hour=12, minute=0):
        return rollup.day_bounds(self.day0 + day_offset)[0] + hour * 3600 + minute * 60

    def go(self, day_offset, hour=12, minute=0):
        self.clk.set(self.at(day_offset, hour, minute))

    def account(self, party):
        return recording.party_account_id(PartyKind(party[0]), party[1])

    def pay(self, qty, price, buyer, seller, key=None):
        self._seq += 1
        key = key or f"mk:{self._seq}"
        res = ledger.transfer(self.account(buyer), self.account(seller), qty * price, Nature.SALE, key=key, reference_kind="test",
                              reference_id=key)
        self.assertTrue(res.ok, res)
        return key

    def sell(self, product, qty, price, *, buyer=None, seller=None, channel="inter_company", day=None, hour=12, minute=0):
        """Move o dinheiro (SALE) e registra no histórico. `day` é o deslocamento em dias a partir do dia do T0."""
        if day is not None:
            self.go(day, hour, minute)
        buyer = buyer or ("player", self.third.pk)
        seller = seller or ("company", self.firm)
        key = self.pay(qty, price, buyer, seller)
        res = recording.record_sale(product_key=product, quantity=qty, unit_price_cents=price, buyer_kind=buyer[0], buyer_id=buyer[1],
                                    seller_kind=seller[0], seller_id=seller[1], channel=channel, ledger_key=key)
        self.assertTrue(res.ok, res)
        return res
