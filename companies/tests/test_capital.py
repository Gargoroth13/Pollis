"""Aporte de capital: transferência de dinheiro existente do Dono para a conta da empresa; sem retirada; recusas sem efeito."""
from companies import services
from companies.models import CapitalContribution, CompaniesImmutableError
from ledger import services as ledger
from ledger.constants import Nature
from ledger.models import Entry

from .base import REAL, CompanyTestCase


class CapitalTests(CompanyTestCase):
    def test_the_owner_moves_existing_money_into_the_company_account(self):
        company = self.found()
        account = services.company_account(company)
        before = self.money(self.player)
        res = services.fund_company(self.player.pk, company, 1_000 * REAL)
        self.assertTrue(res.ok, res)
        self.assertEqual((self.money(self.player), ledger.balance_of(account.pk), res.detail["company_balance"]),
                         (before - 1_000 * REAL, 1_000 * REAL, 1_000 * REAL))
        entry = Entry.objects.get(transaction__key=CapitalContribution.objects.get().ledger_key)
        self.assertEqual((entry.nature, entry.category), (Nature.DONATION.value, "company_capital"))

    def test_contributions_accumulate_with_a_stable_sequence_and_conserve_money(self):
        from ledger.audit import ledger_metrics
        company = self.found()
        circulating = ledger_metrics()["in_circulation"]
        for n in range(1, 4):
            self.assertTrue(services.fund_company(self.player.pk, company, n * REAL).ok)
        self.assertEqual(list(CapitalContribution.objects.values_list("sequence", "amount")), [(1, 100), (2, 200), (3, 300)])
        self.assertEqual(ledger.balance_of(services.company_account(company).pk), 600)
        self.assertEqual(ledger_metrics()["in_circulation"], circulating)

    def test_only_the_owner_can_fund_and_nobody_can_withdraw(self):
        company = self.found()
        self.assertRefused(services.fund_company(self.other.pk, company, REAL), "NOT_OWNER")
        self.assertFalse(hasattr(services, "withdraw_company") or hasattr(services, "distribute_profit"))   # sem retirada (Q9)

    def test_refusals_change_nothing(self):
        company = self.found()
        world = self.world()
        for args, code in [((company, 0), "INVALID_AMOUNT"), ((company, -5), "INVALID_AMOUNT"), ((company, True), "INVALID_AMOUNT"),
                           ((company, "5"), "INVALID_AMOUNT"), ((company, 10 ** 30), "INVALID_AMOUNT"),
                           (("x", 5), "INVALID_PARAMS"), ((10 ** 30, 5), "INVALID_PARAMS"),
                           ((10 ** 9, 5), "COMPANY_NOT_FOUND"), ((company, 10 ** 12), "INSUFFICIENT_FUNDS")]:
            self.assertRefused(services.fund_company(self.player.pk, *args), code)
        self.assertRefused(services.fund_company(10 ** 9, company, 5), "PLAYER_NOT_FOUND")
        self.assertEqual(self.world(), world)

    def test_contributions_are_immutable(self):
        company = self.found()
        services.fund_company(self.player.pk, company, REAL)
        k = CapitalContribution.objects.get()
        k.amount = 1
        with self.assertRaises(CompaniesImmutableError):
            k.save()
        with self.assertRaises(CompaniesImmutableError):
            k.delete()
