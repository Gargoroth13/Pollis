"""
Maior contribuinte: atribuição do imposto (decisão do GD, 2026-11-03). Imposto retido sobre remuneração é do JOGADOR
BENEFICIÁRIO; a empresa/governo que só recolhe e remete não recebe o crédito. Os demais impostos ficam com a conta pagadora.
A distinção é por natureza + transação/referência do lançamento, nunca uma troca global de `from_account`.
"""
from decimal import Decimal

from ledger import obligations, remuneration, services as ledger
from ledger.constants import Nature, Policy
from ledger.models import Entry, Obligation
from rankings import live, taxes

from .base import DAY, HOUR, T0, RankingsTestCase

D = Decimal


class TaxAttributionTests(RankingsTestCase):
    def setUp(self):
        super().setUp()
        remuneration.register_limits_provider(lambda pid, nature, at: (10_000_000, 10_000_000, None))
        remuneration.register_political_due_provider(lambda pid, day: 0)
        self.clk.advance(days=40)
        self.now = self.clk.now()
        self.employer = self.company(1)
        self.fund(self.employer, 1_000_000)
        self.n = 0

    def wage(self, player=None, due=10_000, rate="0.1", day=-2, nature=Nature.WAGE, payer=None, policy=Policy.PENDING):
        self.n += 1
        at = self.now + day * DAY
        res = remuneration.submit_remuneration(
            key=f"r{self.n}", player_id=(player or self.player).pk, payer_id=(payer or self.employer).pk, nature=nature, due=due,
            earned_at=at, policy=policy, reference_kind="work", reference_id=self.n, tax_rate=D(rate))
        self.assertTrue(res.ok, res)
        out = remuneration.liquidate_remuneration(batch=f"b{self.n}", at=at, keys=[f"r{self.n}"])
        self.assertTrue(out.ok, out)
        return out

    def totals(self):
        w = live.taxpayer_window(self.now)
        return taxes.taxpayer_totals(w["first_day"], w["last_day"])

    def test_income_tax_withheld_on_wage_belongs_to_the_beneficiary_not_the_employer(self):
        self.wage(due=10_000, rate="0.1")
        totals, unresolved = self.totals()
        self.assertEqual(totals, {("player", self.player.pk): 1_000})       # NÃO ("company", 1)
        self.assertEqual(unresolved, 0)
        e = Entry.objects.get(nature="tax_income")
        self.assertEqual((e.from_account.kind, e.from_account.owner_id), ("company", 1))       # o ledger lança pela empresa
        rows = live.taxpayer_rows()
        self.assertEqual([(r["entity_type"], r["entity_id"], r["value"]) for r in rows], [("player", self.player.pk, 1_000)])

    def test_other_taxes_stay_with_the_paying_account(self):
        buyer = self.company(5)
        self.fund(buyer, 100_000)
        for nature, key in ((Nature.TAX_SALES, "s"), (Nature.TAX_PROPERTY, "p")):
            res = ledger.post_taxed_payment(buyer.pk, self.company(9).pk, 10_000, nature=Nature.SALE, tax_rate=D("0.1"),
                                            tax_nature=nature, key=key, reference_kind="t", reference_id=key, at=self.now - 2 * DAY)
            self.assertTrue(res.ok, res)
        totals, _ = self.totals()
        self.assertEqual(totals, {("company", 5): 2_000})

    def test_tax_income_that_is_not_remuneration_stays_with_the_payer(self):
        """`tax_income` sem perna de remuneração na transação (e sem referência de remuneração) fica com quem pagou."""
        payer = self.acct()
        self.fund(payer, 50_000)
        res = ledger.post_taxed_payment(payer.pk, self.company(9).pk, 10_000, nature=Nature.SALE, tax_rate=D("0.1"),
                                        tax_nature=Nature.TAX_INCOME, key="ti", reference_kind="t", reference_id="1",
                                        at=self.now - 2 * DAY)
        self.assertTrue(res.ok, res)
        totals, unresolved = self.totals()
        self.assertEqual((totals, unresolved), ({("player", self.player.pk): 1_000}, 1))
        # com a conta pagadora de OUTRO jogador/empresa o crédito segue o pagador
        buyer = self.company(5)
        self.fund(buyer, 50_000)
        ledger.post_taxed_payment(buyer.pk, self.company(9).pk, 10_000, nature=Nature.SALE, tax_rate=D("0.2"),
                                  tax_nature=Nature.TAX_INCOME, key="ti2", reference_kind="t", reference_id="2", at=self.now - 2 * DAY)
        self.assertEqual(self.totals()[0][("company", 5)], 2_000)

    def test_all_remuneration_natures_credit_the_beneficiary(self):
        for nature in (Nature.WAGE, Nature.OWNER_SALARY, Nature.MILITARY_PAY):
            self.wage(due=1_000, rate="0.5", nature=nature)
        self.assertEqual(self.totals()[0], {("player", self.player.pk): 1_500})

    def test_two_beneficiaries_and_two_employers_are_separated(self):
        p2 = self.make_player("p2")
        other_employer = self.company(2)
        self.fund(other_employer, 1_000_000)
        self.wage(self.player, 10_000, "0.1")
        self.wage(p2, 20_000, "0.1", payer=other_employer)
        self.assertEqual(self.totals()[0], {("player", self.player.pk): 1_000, ("player", p2.pk): 2_000})

    def test_government_payer_self_compensation_creates_no_entry_and_no_credit(self):
        gov = ledger.union_account()
        self.fund(gov, 1_000_000)
        self.wage(due=10_000, rate="0.1", payer=gov)               # imposto à União pago pela própria União: sem lançamento
        self.assertFalse(Entry.objects.filter(nature="tax_income").exists())
        self.assertEqual(self.totals()[0], {})

    def test_obligation_settlement_credits_the_creditor_beneficiary(self):
        poor = self.company(3)                                      # sem caixa: a remuneração vira obrigação
        self.wage(due=10_000, rate="0.1", payer=poor)
        ob = Obligation.objects.get()
        self.assertEqual(self.totals()[0], {})                      # nada foi pago ainda: sem imposto
        self.fund(poor, 6_000)
        res = obligations.settle_obligations(poor.pk, batch_key="s1", at=self.now - DAY)       # paga parcialmente
        self.assertTrue(res.ok, res)
        ob.refresh_from_db()
        self.assertTrue(0 < ob.tax_paid)
        totals, unresolved = self.totals()
        self.assertEqual((totals, unresolved), ({("player", self.player.pk): ob.tax_paid}, 0))
        self.assertNotIn(("company", 3), totals)

    def test_hundred_percent_rate_has_no_net_leg_and_resolves_by_remuneration_reference(self):
        self.wage(due=5_000, rate="1")
        e = Entry.objects.get(nature="tax_income")
        self.assertFalse(Entry.objects.filter(transaction=e.transaction).exclude(pk=e.pk).exists())       # só a perna de imposto
        totals, unresolved = self.totals()
        self.assertEqual((totals, unresolved), ({("player", self.player.pk): 5_000}, 0))

    def test_hundred_percent_settlement_resolves_by_obligation_reference(self):
        poor = self.company(3)
        self.wage(due=5_000, rate="1", payer=poor)
        self.fund(poor, 5_000)
        self.assertTrue(obligations.settle_obligations(poor.pk, batch_key="s1", at=self.now - DAY).ok)
        e = Entry.objects.get(nature="tax_income")
        self.assertTrue(e.transaction.key.startswith("settle:"))
        totals, unresolved = self.totals()
        self.assertEqual((totals, unresolved), ({("player", self.player.pk): 5_000}, 0))

    def test_reversed_income_tax_is_not_counted(self):
        self.wage(due=10_000, rate="0.1")
        seq = Entry.objects.get(nature="tax_income").seq
        self.assertEqual(self.totals()[0], {("player", self.player.pk): 1_000})
        self.assertTrue(ledger.reverse(seq, "erro", key="rev", at=self.now - DAY).ok)
        self.assertEqual(self.totals()[0], {})

    def test_window_still_applies_to_attributed_tax(self):
        self.wage(due=10_000, rate="0.1", day=-31)                 # fora
        self.wage(due=20_000, rate="0.1", day=-30)                 # dentro
        self.wage(due=40_000, rate="0.1", day=0)                   # hoje: ainda não fechado
        self.assertEqual(self.totals()[0], {("player", self.player.pk): 2_000})

    def test_beneficiary_and_direct_payer_add_up_on_the_same_player(self):
        buyer = self.acct()
        self.fund(buyer, 50_000)
        ledger.post_taxed_payment(buyer.pk, self.company(9).pk, 10_000, nature=Nature.SALE, tax_rate=D("0.1"),
                                  key="s", reference_kind="t", reference_id="1", at=self.now - 2 * DAY)
        self.wage(due=10_000, rate="0.1")
        self.assertEqual(self.totals()[0], {("player", self.player.pk): 2_000})
