"""Maior contribuinte (14.3.7, 30 dias) e conta mais antiga (14.3.10)."""
from decimal import Decimal

from core.timeline import game_ts
from ledger import services as ledger
from ledger.constants import Nature
from ledger.models import Entry
from ledger.money import competence_day_of
from rankings import live
from rankings.constants import Cat

from .base import DAY, HOUR, T0, RankingsTestCase


class TaxpayerTests(RankingsTestCase):
    def taxed(self, payer, gross, rate="0.1", at=None, key=None, nature=Nature.TAX_SALES):
        self._n += 1
        res = ledger.post_taxed_payment(payer.pk, self.company(900).pk, gross, nature=Nature.SALE, tax_rate=Decimal(rate),
                                        tax_nature=nature, key=key or f"tx{self._n}", reference_kind="t", reference_id=self._n,
                                        at=T0 if at is None else at)
        self.assertTrue(res.ok, res)
        return res

    def setUp(self):
        super().setUp()
        self.clk.advance(days=40)         # hoje é bem depois do início, para a janela caber
        self.now = self.clk.now()

    def day_at(self, offset):
        """Instante (meio-dia) do dia de competência `hoje + offset`."""
        return self.now + offset * DAY

    def test_sums_effectively_paid_tax_in_the_window_for_players_and_companies(self):
        a, b = self.acct(), self.company(7)
        self.fund(a, 100_000)
        self.fund(b, 100_000)
        self.taxed(a, 10_000, at=self.day_at(-5))                    # imposto 1.000
        self.taxed(a, 5_000, at=self.day_at(-2))                     # 500
        self.taxed(b, 30_000, at=self.day_at(-3))                    # 3.000
        rows = live.taxpayer_rows()
        self.assertEqual([(r["entity_type"], r["entity_id"], r["value"], r["rank"]) for r in rows],
                         [("company", 7, 3_000, 1), ("player", self.player.pk, 1_500, 2)])
        self.assertEqual(rows[0]["name"], "company #7")

    def test_window_is_the_30_closed_days_before_today(self):
        a = self.acct()
        self.fund(a, 100_000)
        self.taxed(a, 10_000, at=self.day_at(-31))                   # fora (dia −31)
        self.taxed(a, 20_000, at=self.day_at(-30))                   # dentro (primeiro dia da janela)
        self.taxed(a, 30_000, at=self.day_at(-1))                    # dentro (último dia fechado)
        self.taxed(a, 40_000, at=self.day_at(0))                     # hoje: ainda não fechado
        rows = live.taxpayer_rows()
        self.assertEqual(rows[0]["value"], 2_000 + 3_000)
        w = live.taxpayer_window(self.now)
        self.assertEqual((w["first_day"], w["last_day"]), (competence_day_of(self.now) - 30, competence_day_of(self.now) - 1))

    def test_result_does_not_depend_on_the_time_of_day_the_page_is_opened(self):
        a = self.acct()
        self.fund(a, 100_000)
        self.taxed(a, 10_000, at=self.day_at(-1))
        morning = live.taxpayer_rows(at=game_ts(2026, 11, 14, 0, 1))
        evening = live.taxpayer_rows(at=game_ts(2026, 11, 14, 23, 59))
        self.assertEqual([(r["entity_id"], r["value"]) for r in morning], [(r["entity_id"], r["value"]) for r in evening])

    def test_non_tax_natures_and_reversed_taxes_are_ignored(self):
        a = self.acct()
        self.fund(a, 100_000)
        self.assertTrue(self.pay(a, self.company(1), 5_000, at=self.day_at(-2)).ok)          # venda comum: não é imposto
        res = self.taxed(a, 10_000, at=self.day_at(-2))
        tax_seq = Entry.objects.get(transaction__key=res.detail and f"tx{self._n}", nature="tax_sales").seq
        self.assertEqual(live.taxpayer_rows()[0]["value"], 1_000)
        self.assertTrue(ledger.reverse(tax_seq, "erro", key="rev1", at=self.day_at(-1)).ok)
        self.assertEqual(live.taxpayer_rows(), [])

    def test_income_and_property_taxes_count(self):
        a = self.acct()
        self.fund(a, 100_000)
        self.taxed(a, 10_000, at=self.day_at(-2), nature=Nature.TAX_INCOME)
        self.taxed(a, 10_000, at=self.day_at(-2), nature=Nature.TAX_PROPERTY)
        self.assertEqual(live.taxpayer_rows()[0]["value"], 2_000)

    def test_ties_share_position(self):
        p2 = self.make_player("p2")
        for p in (self.player, p2):
            self.fund(self.acct(p), 100_000)
            self.taxed(self.acct(p), 10_000, at=self.day_at(-2))
        rows = live.taxpayer_rows()
        self.assertEqual([r["rank"] for r in rows], [1, 1])

    def test_empty_when_nobody_paid_tax(self):
        self.assertEqual(live.taxpayer_rows(), [])
        r = live.live_ranking(Cat.TAXPAYER)
        self.assertEqual((r["available"], r["entries"], r["window"]["days"]), (True, [], 30))

    def test_government_and_system_accounts_are_not_ranked(self):
        self.fund(ledger.union_account(), 50_000)
        self.taxed(ledger.union_account(), 10_000, at=self.day_at(-2))     # imposto autocompensado: sem lançamento; e conta não é jogador/empresa
        self.assertEqual(live.taxpayer_rows(), [])


class OldestAccountTests(RankingsTestCase):
    def test_age_is_now_minus_creation_and_needs_no_activity(self):
        old = self.make_player("old", created_at=T0 - 100 * DAY)
        self.clk.advance(days=10)
        rows = live.oldest_account_rows()
        self.assertEqual([(r["name"], r["value"], r["rank"]) for r in rows],
                         [("old", 110 * DAY, 1), ("p1", 10 * DAY, 2)])
        self.assertEqual(rows[0]["detail"], {"created_at": T0 - 100 * DAY, "now": T0 + 10 * DAY})

    def test_same_creation_instant_shares_position_and_limit(self):
        self.make_player("twin", created_at=T0)
        self.make_player("younger", created_at=T0 + HOUR)
        self.clk.advance(days=1)
        rows = live.oldest_account_rows()
        self.assertEqual([(r["name"], r["rank"]) for r in rows], [("p1", 1), ("twin", 1), ("younger", 3)])
        self.assertEqual(len(live.oldest_account_rows(limit=1)), 1)

    def test_payload_display(self):
        self.clk.advance(days=2, hours=3)
        r = live.live_ranking(Cat.OLDEST_ACCOUNT)
        self.assertEqual(r["entries"][0]["display"], "2 d 3 h 0 min")
