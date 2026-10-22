"""Transparência de custos da Empresa (design/17 §17.14-17.16): variação por categoria e principal contribuição observada."""
from decimal import Decimal

from companies import services
from ledger.models import Entry
from market import costs
from market.constants import NO_DATA, OK
from market.models import CompanyCostDay

from .base import MarketBase

D = Decimal


class CostReportTests(MarketBase):
    def buy_wheat(self, cents, day):
        self.sell("wheat", 1, cents, buyer=("company", self.firm), seller=("player", self.third.pk), day=day)

    def work_on(self, day):
        """Trabalhar num dia futuro: antes, o jogador é sincronizado (os dias sem comer não são o assunto destes testes)."""
        self.go(day)
        self.state(self.worker)
        self.hook()

    def report(self, day=15):
        self.go(day)
        return costs.company_cost_report(self.firm, self.clk.now())

    def test_a_company_with_no_costs_in_both_periods_has_no_data(self):
        r = self.report(3)
        self.assertEqual((r["status"], r["total"], r["components"], r["main_contribution"]), (NO_DATA, None, [], None))

    def test_variation_by_category_and_the_main_observed_contribution(self):
        self.buy_wheat(10_000, day=3)                       # 7 dias anteriores (dias 1..7 do período de 15)
        self.work_on(3)                                     # um Trabalhar no dia 3: R$ 20 de salário (período anterior)
        self.buy_wheat(12_100, day=10)                      # últimos 7 dias (8..14): Trigo +21%
        self.work_on(10)
        self.hook()                                         # dois Trabalhar no dia 10: salário dobra
        r = self.report()
        self.assertEqual(r["status"], OK)
        by = {c["category"]: c for c in r["components"]}
        self.assertEqual((by["input:wheat"]["previous_7d_cents"], by["input:wheat"]["last_7d_cents"]), (10_000, 12_100))
        self.assertEqual(by["input:wheat"]["variation_pct"].quantize(D("0.01")), D("21.00"))
        self.assertEqual(by["input:wheat"]["product"], "wheat")
        wages = sum(Entry.objects.filter(nature="wage", at__lt=self.at(7)).values_list("amount", flat=True))
        self.assertEqual((by["salaries"]["previous_7d_cents"], by["salaries"]["last_7d_cents"]), (wages, 2 * wages))
        self.assertEqual(by["salaries"]["variation_pct"], 100)
        total_prev = sum(c["previous_7d_cents"] for c in r["components"])
        total_last = sum(c["last_7d_cents"] for c in r["components"])
        self.assertEqual((r["total"]["previous_7d_cents"], r["total"]["last_7d_cents"]), (total_prev, total_last))
        self.assertGreater(r["total"]["delta_cents"], 0)
        main = r["main_contribution"]
        self.assertEqual((main["category"], main["delta_cents"]), ("input:wheat", 2_100))      # maior diferença em R$, não maior %
        self.assertIn("aumento", main["text"])
        self.assertNotIn("causou", main["text"])                                               # nunca afirma causalidade exata
        self.assertEqual(r["periods"]["last_7d"]["last_day"], self.day0 + 14)                  # o dia corrente (15) fica de fora

    def test_the_main_contribution_follows_the_direction_of_the_total_and_a_new_category_has_no_percentage(self):
        self.buy_wheat(20_000, day=3)
        self.buy_wheat(5_000, day=10)
        r = self.report()
        self.assertEqual(r["main_contribution"]["category"], "input:wheat")
        self.assertIn("queda", r["main_contribution"]["text"])
        self.assertEqual(r["total"]["delta_cents"], -15_000)
        self.assertEqual(r["total"]["variation_pct"].quantize(D("0.01")), D("-75.00"))

    def test_a_category_that_only_exists_in_the_last_period_has_no_percentage_and_one_that_stops_is_minus_100(self):
        self.buy_wheat(1_000, day=3)
        self.sell("flour", 1, 800, buyer=("company", self.firm), seller=("player", self.third.pk), day=10)
        r = self.report()
        by = {c["category"]: c for c in r["components"]}
        self.assertIsNone(by["input:flour"]["variation_pct"])
        self.assertEqual(by["input:flour"]["delta_cents"], 800)
        self.assertEqual(by["input:wheat"]["variation_pct"], -100)

    def test_no_change_in_the_total_has_no_main_contribution(self):
        self.buy_wheat(1_000, day=3)
        self.buy_wheat(1_000, day=10)
        r = self.report()
        self.assertEqual((r["total"]["delta_cents"], r["main_contribution"]), (0, None))

    def test_only_the_companys_own_costs_count(self):
        other = self.found(self.third, "industrial", "Outra", 2_000)
        self.assertTrue(services.fund_company(self.third.pk, other, 100_000).ok)
        self.sell("wheat", 1, 9_999, buyer=("company", other), seller=("player", self.boss.pk), day=3)
        self.buy_wheat(1_000, day=3)
        r = self.report()
        self.assertEqual({c["category"] for c in r["components"]}, {"input:wheat"})
        self.assertEqual(r["total"]["last_7d_cents"] + r["total"]["previous_7d_cents"], 1_000)

    def test_a_reversed_tax_stops_being_a_cost_and_the_reversal_itself_is_not_one(self):
        from core import ticks
        from ledger import services as ledger
        self.go(1, 0, 5)
        ticks.advance_world()                                                       # folha do Dono do dia 1: líquido + IR
        tax = Entry.objects.get(nature="tax_income", from_account__owner_id=self.firm)
        self.assertTrue(ledger.reverse(tax.pk, "teste", key="rev:tax").ok)
        r = self.report(4)
        by = {c["category"]: c for c in r["components"]}
        self.assertEqual(set(by), {"salaries"})                                     # o imposto estornado saiu; o estorno não vira custo
        self.assertEqual(by["salaries"]["last_7d_cents"] + by["salaries"]["previous_7d_cents"], 1_900)

    def test_the_report_aggregates_are_read_from_the_stored_days_not_the_raw_history(self):
        self.buy_wheat(10_000, day=3)
        self.report()
        CompanyCostDay.objects.filter(company_id=self.firm, category="input:wheat").delete()      # o relatório lê o agregado fechado
        self.audit_market_at_end = False
        self.assertEqual(costs.company_cost_report(self.firm, self.clk.now())["status"], NO_DATA)
