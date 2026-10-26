from decimal import Decimal

from companies import construction
from companies import services as company_services
from companies.tests.test_construction import ConstructionBase
from core import ticks
from geography.models import Lot
from ledger import services as ledger
from ledger.constants import AccountKind
from geography.constants import Occupation
from ledger.money import competence_day_of
from market import rollup
from players import qol
from players.tests.base import T0
from properties import housing, params, rent, services
from properties.audit import audit_properties
from properties.models import Auction, Building, LotTitle, TitleEvent, Unit

D = Decimal


class PropertiesBase(ConstructionBase):
    """Construtora `build` (Dono boss, pedreiro third), jogadores com dinheiro e o mundo pequeno com lotes de todas as categorias."""

    audit_properties_at_end = True

    def setUp(self):
        super().setUp()
        self.addCleanup(self._audit_properties)
        self.assertTrue(company_services.fund_company(self.boss.pk, self.build, 5_000_000).ok)

    def ensure_qol_provider(self):
        """Os testes de jogador limpam os provedores de QoL ao fim de cada teste: aqui o do imóvel volta."""
        qol._providers.pop(housing.PROVIDER_NAME, None)
        qol.register_qol_base_provider(housing.PROVIDER_NAME, housing.qol_bonus)

    # --- tempo (dias de jogo) -------------------------------------------------------------------------------------------
    @property
    def day0(self):
        return competence_day_of(T0)

    def day_time(self, offset, seconds=300):
        return rollup.day_bounds(self.day0 + offset)[0] + seconds

    def go_day(self, offset):
        """Leva o relógio à virada do dia `offset` depois do de T0 e roda os ticks do mundo (aluguéis, leilões)."""
        self.clk.set(self.day_time(offset))
        return ticks.advance_world()

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

    # --- imóveis ----------------------------------------------------------------------------------------------------------
    _built = 0

    def built(self, player=None, company=None, kind="high_density_simple"):
        """Um imóvel pronto e as suas unidades, de `player` ou da `company` (o Dono compra o terreno no leilão e o imóvel nasce nele)."""
        self._built += 1
        lot = self.lot(n=-self._built)
        if company is not None:
            self.sold_to(self.boss, lot, price=1_000 + self._built, party=self.company_ref(company))
        else:
            self.sold_to(player, lot, price=1_000 + self._built)
        k = params.BUILDING_TYPES[kind]
        b = Building.objects.create(lot=lot, kind=k.key, units=k.units, qol_bonus=k.qol_bonus, completed_at=self.clk.now())
        housing.create_units(b)
        type(lot).objects.filter(pk=lot.pk).update(occupation=Occupation.OCCUPIED.value)
        return b

    def unit(self, building, index=1):
        return Unit.objects.get(building=building, index=index)

    def rent_listing(self, unit, owner, actor, amount=10_000, frequency="daily", **extra):
        return rent.list_rent(actor.pk, {"unit": unit.pk, "owner": owner, "amount": amount, "frequency": frequency, **extra})

    def rent_it(self, listing, tenant, starts=1, ends=3):
        return rent.rent_unit(tenant.pk, {"listing": listing, "tenant": self.player_ref(tenant), "starts_on": self.day0 + starts,
                                          "ends_on": self.day0 + ends})
