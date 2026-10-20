from catalog.loader import sync_catalog
from companies import services
from core.models import WorldClock
from companies.audit import audit_companies
from companies.constants import CompanyType
from ledger import services as ledger
from ledger.audit import ledger_metrics
from ledger.models import Account
from ledger.tests.base import LedgerHelpers, fund_account  # noqa: F401
from players.tests.base import T0, PlayerTestCase

REAL = 100          # centavos por real


class CompanyTestCase(LedgerHelpers, PlayerTestCase):
    """Mundo pequeno + relógio manual + jogadores com dinheiro; ao fim de TODO teste, o ledger e as empresas estão íntegros."""

    audit_companies_at_end = True

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_catalog()                  # produtos e receitas do 22 (a produção consulta o catálogo)

    def setUp(self):
        super().setUp()
        self.ledger_setup()
        WorldClock.load()
        WorldClock.objects.filter(pk=1).update(anchor_game=T0, world_processed_until=T0)   # o mundo "começa" em T0
        self.addCleanup(self._audit_companies)                  # decide ao FIM se audita (o teste pode adulterar de propósito)
        self.other = self.new_player("p2")
        for p in (self.player, self.other):
            self.fund(p, 500_000)

    def _audit_companies(self):
        if not self.audit_companies_at_end:
            return
        report = audit_companies()
        self.assertTrue(report.ok, report.findings)

    def fund(self, player, reais):
        fund_account(ledger.player_account(player.pk), reais * REAL)

    def money(self, player):
        return ledger.balance_of(ledger.player_account(player.pk).pk)

    def union(self):
        return ledger.balance_of(ledger.union_account().pk)

    def found(self, player=None, type=CompanyType.RETAIL.value, name="Loja", salary=0):
        res = services.found_company((player or self.player).pk, type, name, salary)
        self.assertTrue(res.ok, res)
        return res.detail["company"]

    def assertRefused(self, res, code, **detail):
        self.assertEqual((res.ok, res.code), (False, code), (res.code, res.detail))
        for k, v in detail.items():
            self.assertEqual(res.detail.get(k), v, (k, res.detail))

    def world(self):
        from companies.models import CapitalContribution, Company, Position
        return (Company.objects.count(), Position.objects.count(), CapitalContribution.objects.count(),
                ledger_metrics()["in_circulation"], {a.pk: a.balance for a in Account.objects.all()})
