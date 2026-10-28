from decimal import Decimal

from django.test import TestCase

from budget import authority, plans, transfers
from budget.audit import audit_budget
from budget.constants import Level
from budget.govs import account_of, ensure_accounts
from geography.models import City, State
from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import Nature
from ledger.money import competence_day_of
from ledger.tests.base import fund_account, install_test_role
from players.tests.base import T0, PlayerTestCase

D = Decimal
DAY = 86400


class BudgetBase(PlayerTestCase):
    """Mundo pequeno (1 Estado, 2 Municípios), contas de governo abertas no instante T0, ocupantes de cargo FALSOS (a P1.11 registra os reais)."""

    audit_at_end = True

    def setUp(self):
        super().setUp()
        install_test_role(self)
        self.addCleanup(ledger.clear_tax_resolvers)
        self.holders = {}
        authority.register_office_provider("test", lambda level, ident: self.holders.get((level, ident)))
        self.addCleanup(authority.unregister_office_provider, "test")
        self.state = State.objects.order_by("pk").first()
        self.city_a, self.city_b = list(City.objects.filter(state=self.state).order_by("pk")[:2])
        self.president, self.governor, self.mayor, self.other = (self.new_player(n) for n in ("pres", "gov", "mayor", "other"))
        self.holders[(Level.UNION, 0)] = self.president.pk
        self.holders[(Level.STATE, self.state.pk)] = self.governor.pk
        self.holders[(Level.MUNICIPALITY, self.city_a.pk)] = self.mayor.pk
        ensure_accounts()
        self.addCleanup(self._audit)

    def _audit(self):
        if self.audit_at_end:
            for report in (audit_ledger(), audit_budget()):
                self.assertTrue(report.ok, report.findings)

    # --- atalhos ----------------------------------------------------------------------------------------------------
    def acct(self, level, ident=0):
        return account_of(level, ident)

    def union(self):
        return self.acct(Level.UNION, 0)

    def st(self):
        return self.acct(Level.STATE, self.state.pk)

    def mun(self, city=None):
        return self.acct(Level.MUNICIPALITY, (city or self.city_a).pk)

    def bal(self, account):
        return ledger.balance_of(account.pk)

    def fund(self, account, amount):
        return fund_account(account, amount)

    def gov(self, level, ident=0):
        return {"level": level.value, "id": ident}

    def to_state(self, amount, **extra):
        return {"from": self.gov(Level.UNION), "to": self.gov(Level.STATE, self.state.pk), "amount": amount, **extra}

    def to_city(self, amount, city=None, **extra):
        return {"from": self.gov(Level.STATE, self.state.pk), "to": self.gov(Level.MUNICIPALITY, (city or self.city_a).pk), "amount": amount, **extra}

    def day_of_now(self):
        return competence_day_of(self.clk.now())

    def go_days(self, n):
        self.clk.set(self.clk.now() + n * DAY)

    _n = 0

    def earn(self, account, amount, nature=Nature.DONATION, day_offset=None, category="", payer=None):
        """Entra receita numa conta de governo: dinheiro EXISTENTE de um jogador (dotação ao jogador antes, pela única fonte de emissão)."""
        BudgetBase._n += 1
        payer = payer or self.other
        pa = ledger.player_account(payer.pk)
        if ledger.balance_of(pa.pk) < amount:
            fund_account(pa, amount - ledger.balance_of(pa.pk))
        res = ledger.transfer(pa.pk, account.pk, amount, nature, key=f"earn{BudgetBase._n}", reference_kind="test", reference_id=str(BudgetBase._n),
                              at=self.clk.now(), category=category)
        assert res.ok, res
        return res

    def spend(self, account, amount, nature=Nature.PUBLIC_WORKS_PAYMENT, category="infrastructure"):
        BudgetBase._n += 1
        pa = ledger.player_account(self.other.pk)
        res = ledger.transfer(account.pk, pa.pk, amount, nature, key=f"spend{BudgetBase._n}", reference_kind="test", reference_id=str(BudgetBase._n),
                              at=self.clk.now(), category=category)
        assert res.ok, res
        return res
