"""Fundação (02 §16-17): custo por tipo, cargo Dono automático, conta da empresa, sem dinheiro novo, recusas sem efeito."""
from companies import params, services
from companies.constants import FOUNDING_COST_CENTS, FOUNDING_COST_REAIS, CompanyType, PositionKind
from companies.models import Company, Position
from ledger import services as ledger
from ledger.constants import AccountKind, Nature
from ledger.models import Account, Entry

from .base import REAL, CompanyTestCase


class CostTableTests(CompanyTestCase):
    def test_the_costs_are_exactly_the_ones_defined_in_the_design(self):
        self.assertEqual({t.value: v for t, v in FOUNDING_COST_REAIS.items()},
                         {"retail": 15_000, "services": 25_000, "matrix": 40_000, "construction": 60_000,
                          "industrial": 80_000, "financial": 100_000})
        self.assertEqual(set(FOUNDING_COST_CENTS), set(CompanyType))
        self.assertEqual(FOUNDING_COST_CENTS[CompanyType.RETAIL], 15_000 * REAL)

    def test_the_cost_is_explained(self):
        cost = services.founding_cost("industrial")
        self.assertEqual((cost.value, cost.step("founding_cost").amount), (8_000_000, 8_000_000))
        self.assertIsNone(services.founding_cost("bank"))


class FoundingTests(CompanyTestCase):
    def test_founding_charges_the_cost_to_the_union_and_creates_company_owner_position_and_account(self):
        before, union = self.money(self.player), self.union()
        res = services.found_company(self.player.pk, "matrix", "  Fazenda Boa  ", 120_000)
        self.assertTrue(res.ok, res)
        cost = 40_000 * REAL
        self.assertEqual((self.money(self.player), self.union()), (before - cost, union + cost))     # dinheiro movido, nunca criado
        company = Company.objects.get(pk=res.detail["company"])
        self.assertEqual((company.name, company.type, company.founder_id, company.stars, company.founding_cost),
                         ("Fazenda Boa", "matrix", self.player.pk, params.INITIAL_STARS, cost))
        owner = Position.objects.get(company=company)
        self.assertEqual((owner.kind, owner.holder_id, owner.salary), (PositionKind.OWNER.value, self.player.pk, 120_000))
        account = Account.objects.get(kind=AccountKind.COMPANY.value, owner_id=company.pk)
        self.assertEqual((ledger.balance_of(account.pk), res.detail["account"]), (0, account.pk))     # nasce sem caixa
        entry = Entry.objects.get(transaction__key=company.founding_key)
        self.assertEqual((entry.nature, entry.amount, entry.to_account_id), (Nature.COMPANY_FOUNDING.value, cost, ledger.union_account().pk))
        self.assertEqual(res.detail["cost_explained"].value, cost)

    def test_every_type_can_be_founded_at_its_own_cost(self):
        self.fund(self.player, 1_000_000)
        for t in CompanyType:
            before = self.money(self.player)
            self.found(type=t.value, name=t.value)
            self.assertEqual(before - self.money(self.player), FOUNDING_COST_CENTS[t], t)

    def test_the_owner_may_have_a_zero_salary_and_a_founder_may_found_several_companies(self):
        a = self.found(name="A", salary=0)
        b = self.found(name="B", salary=10)
        self.assertNotEqual(a, b)
        self.assertEqual(Company.objects.filter(founder=self.player).count(), 2)
        self.assertEqual(sorted(Company.objects.values_list("founding_sequence", flat=True)), [1, 2])

    def test_each_company_has_its_own_account(self):
        a, b = self.found(name="A"), self.found(name="B")
        self.assertNotEqual(services.company_account(a).pk, services.company_account(b).pk)
        with self.assertRaises(ValueError):
            services.company_account(10 ** 9)

    def test_refusals_change_nothing(self):
        poor = self.new_player("poor")
        self.fund(poor, 14_999)
        world = self.world()
        for player, args, code in [
            (self.player, ("bank", "X", 0), "INVALID_COMPANY_TYPE"),
            (self.player, (5, "X", 0), "INVALID_PARAMS"),
            (self.player, ("retail", "", 0), "INVALID_NAME"),
            (self.player, ("retail", "   ", 0), "INVALID_NAME"),
            (self.player, ("retail", "x" * 81, 0), "INVALID_NAME"),
            (self.player, ("retail", 7, 0), "INVALID_NAME"),
            (self.player, ("retail", "X", -1), "INVALID_SALARY"),
            (self.player, ("retail", "X", True), "INVALID_SALARY"),
            (self.player, ("retail", "X", "10"), "INVALID_SALARY"),
            (self.player, ("retail", "X", 10 ** 13), "INVALID_SALARY"),
            (poor, ("retail", "X", 0), "INSUFFICIENT_FUNDS"),
        ]:
            self.assertRefused(services.found_company(player.pk, *args), code)
        self.assertRefused(services.found_company(10 ** 9, "retail", "X", 0), "PLAYER_NOT_FOUND")
        self.assertEqual(self.world(), world)

    def test_the_exact_cost_is_enough_and_one_centavo_less_is_not(self):
        exact = self.new_player("exact")
        fund = 15_000 * REAL
        from ledger.tests.base import fund_account
        fund_account(ledger.player_account(exact.pk), fund - 1)
        self.assertRefused(services.found_company(exact.pk, "retail", "X", 0), "INSUFFICIENT_FUNDS", shortfall=1)
        fund_account(ledger.player_account(exact.pk), 1)
        self.assertTrue(services.found_company(exact.pk, "retail", "X", 0).ok)
        self.assertEqual(self.money(exact), 0)

    def test_the_company_does_not_count_as_a_job_and_the_founder_keeps_working_as_before(self):
        from players import registry
        energy = self.state().energy
        self.found()
        self.assertEqual(self.state().energy, energy)                                      # fundar não custa Energia
        self.assertTrue(registry.execute_action(self.player.pk, "leisure").ok)             # nem bloqueia as ações normais
