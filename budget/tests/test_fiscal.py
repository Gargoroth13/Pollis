"""Situação fiscal e teto de déficit (09 §9-§11, §33, §34; 24 §24.16): classificação, janela, borda exata, histórico < 30 dias, estorno."""
from decimal import Decimal as D

from budget import fiscal, periods, transfers
from budget.constants import Level
from geography.models import City, State
from ledger import services as ledger

from .base import BudgetBase


class ClassificationTests(BudgetBase):
    def flows(self, account, back=0):
        today = self.day_of_now()
        return fiscal.flows(account.pk, today - back, today)

    def test_what_enters_is_revenue_and_what_leaves_is_expense_by_category(self):
        m = self.mun()
        self.earn(m, 5_000)
        self.spend(m, 1_200, category="education")
        self.spend(m, 300, category="education")
        self.spend(m, 400, category="health")
        f = self.flows(m)
        self.assertEqual((f.revenue, f.expense), (5_000, 1_900))
        self.assertEqual(f.expense_by_category, {"education": 1_500, "health": 400})
        self.assertEqual(f.revenue_by_nature, {"donation": 5_000})

    def test_scenario_grant_is_not_revenue_but_is_listed_as_excluded(self):
        m = self.mun()
        self.fund(m, 10_000)
        f = self.flows(m)
        self.assertEqual(f.revenue, 0)
        self.assertEqual(f.excluded_revenue, {"scenario_grant": 10_000})

    def test_transfer_received_is_revenue_for_the_receiver_and_not_expense_for_the_sender(self):
        self.fund(self.union(), 100_000)
        self.fund(self.st(), 1)
        self.assertTrue(transfers.transfer_budget(self.president.pk, self.to_state(40_000)).ok)
        fs, fu = self.flows(self.st()), self.flows(self.union())
        self.assertEqual(fs.revenue, 40_000)
        self.assertEqual((fu.expense, fu.excluded_expense), (0, {"gov_transfer": 40_000}))

    def test_reversal_cancels_the_classification_of_the_original(self):
        m = self.mun()
        self.earn(m, 5_000)
        res = self.spend(m, 2_000, category="health")
        from ledger.models import Entry
        seq = Entry.objects.filter(from_account_id=m.pk, nature="public_works_payment").order_by("-seq").first().seq
        self.assertTrue(ledger.reverse(seq, "erro", key="rev1", at=self.clk.now()).ok)
        f = self.flows(m)
        self.assertEqual((f.revenue, f.expense), (5_000, 0))
        self.assertEqual(f.expense_by_category, {})

    def test_the_fiscal_view_reports_balance_committed_pending_and_none_for_debt(self):
        m = self.mun()
        self.earn(m, 9_000)
        self.assertTrue(ledger.hold(m.pk, 2_000, key="h1", reference_kind="test", reference_id="1", at=self.clk.now()).ok)
        v = fiscal.fiscal_view(Level.MUNICIPALITY, self.city_a.pk, self.clk.now())
        self.assertEqual((v["position"]["balance"], v["position"]["committed"], v["position"]["available"]), (9_000, 2_000, 7_000))
        self.assertEqual(v["commitments"][0]["amount"], 2_000)
        self.assertIsNone(v["public_debt"])
        self.assertEqual(v["period"]["revenue"], 9_000)
        self.assertEqual(v["rolling_30_days"]["revenue"], 9_000)

    def test_the_public_log_lists_entries_with_balances_before_and_after(self):
        m = self.mun()
        self.earn(m, 3_000)
        self.spend(m, 1_000)
        log = fiscal.ledger_log(Level.MUNICIPALITY, self.city_a.pk)
        self.assertEqual([(r["direction"], r["amount"], r["balance_after"]) for r in log], [("out", 1_000, 2_000), ("in", 3_000, 3_000)])


class PeriodTests(BudgetBase):
    def test_periods_have_30_days_counted_from_the_game_epoch(self):
        first, last = periods.bounds_of(5)
        self.assertEqual(last - first + 1, 30)
        self.assertEqual(periods.period_of(first), 5)
        self.assertEqual(periods.period_of(last), 5)
        self.assertEqual(periods.period_of(last + 1), 6)
        self.assertEqual(periods.bounds_of(0)[0], periods.EPOCH_DAY)


class DeficitCeilingTests(BudgetBase):
    """24 §24.16: R_ref = R×360/n; Δ_anual = (E−R)×360/n; Δ_proj = Δ_anual + C_360 ≤ teto% × R_ref."""

    def at_history(self, days):
        """Leva o relógio ao dia em que a conta tem exatamente `days` dias de histórico (a abertura e hoje contam)."""
        self.go_days(days - 1)

    def test_exact_equality_is_allowed_and_one_centavo_more_is_not(self):
        m = self.mun()
        self.earn(m, 3_000)                    # dia 0
        self.at_history(30)                    # n = 30, R = 3000, E = 0 → R_ref 36000, Δ_anual −36000, limite 3600
        today = self.day_of_now()
        ok = fiscal.deficit_check(Level.MUNICIPALITY, self.city_a.pk, [(today, 39_600)], self.clk.now())
        self.assertTrue(ok.blocking)
        self.assertTrue(ok.allowed, ok.data)
        self.assertEqual(ok.data["headroom"], "0")
        bad = fiscal.deficit_check(Level.MUNICIPALITY, self.city_a.pk, [(today, 39_601)], self.clk.now())
        self.assertFalse(bad.allowed)
        self.assertEqual(bad.data["restricted_by"], "deficit_ceiling")

    def test_with_less_than_30_days_of_history_the_ceiling_does_not_block(self):
        m = self.mun()
        self.earn(m, 3_000)
        self.at_history(29)
        today = self.day_of_now()
        chk = fiscal.deficit_check(Level.MUNICIPALITY, self.city_a.pk, [(today, 10 ** 12)], self.clk.now())
        self.assertFalse(chk.blocking)
        self.assertTrue(chk.allowed)
        self.assertFalse(chk.data["within_ceiling"])         # o fato é informado mesmo sem bloquear
        self.assertEqual(chk.data["window_days"], 29)

    def test_the_window_is_at_most_360_days_and_older_entries_drop_out(self):
        m = self.mun()
        self.earn(m, 3_600)
        self.go_days(400)
        chk = fiscal.deficit_check(Level.MUNICIPALITY, self.city_a.pk, (), self.clk.now())
        self.assertEqual(chk.data["window_days"], 360)
        self.assertEqual(chk.data["revenue_window"], 0)

    def test_the_commitment_horizon_is_today_through_today_plus_359(self):
        today = self.day_of_now()
        self.assertEqual(fiscal.commitment_360([(today - 1, 5), (today, 7), (today + 359, 11), (today + 360, 13)], today), 18)

    def test_a_deficit_is_annualized(self):
        m = self.mun()
        self.earn(m, 1_000)
        self.at_history(30)
        self.spend(m, 400)
        chk = fiscal.deficit_check(Level.MUNICIPALITY, self.city_a.pk, (), self.clk.now())
        self.assertEqual(D(chk.data["deficit_annualized"]), D(-7_200))          # (400 − 1000) × 12
        self.assertEqual(D(chk.data["revenue_reference"]), D(12_000))

    def test_no_revenue_means_any_commitment_is_blocked_once_the_ceiling_is_active(self):
        self.at_history(30)
        today = self.day_of_now()
        chk = fiscal.deficit_check(Level.MUNICIPALITY, self.city_a.pk, [(today, 1)], self.clk.now())
        self.assertTrue(chk.blocking)
        self.assertFalse(chk.allowed)

    def test_the_result_is_structured_and_explained(self):
        m = self.mun()
        self.earn(m, 3_000)
        self.at_history(30)
        chk = fiscal.deficit_check(Level.MUNICIPALITY, self.city_a.pk, [(self.day_of_now(), 100)], self.clk.now()).to_dict()
        self.assertEqual(set(chk), {"allowed", "blocking", "data", "explained"})
        steps = {st["key"]: st for st in chk["explained"]["steps"]}
        self.assertEqual(steps["deficit_annualized"]["kind"], "base")
        self.assertEqual(steps["new_commitment_360"]["amount"], "100")
        self.assertEqual(steps["deficit_ceiling"]["kind"], "cap")
        self.assertEqual(D(steps["deficit_ceiling"]["amount"]), D(3_600))

    def test_the_ceiling_percentage_is_a_parameter(self):
        m = self.mun()
        self.earn(m, 3_000)
        self.at_history(30)
        today = self.day_of_now()
        chk = fiscal.deficit_check(Level.MUNICIPALITY, self.city_a.pk, [(today, 39_600 + 3_600)], self.clk.now(), ceiling_pct=D("20"))
        self.assertTrue(chk.allowed)

    def test_opening_all_accounts_at_once_is_idempotent_and_fixes_the_account_age(self):
        from budget.govs import ensure_accounts
        from ledger.models import Account
        n = ensure_accounts()
        self.assertEqual(n, 1 + State.objects.count() + City.objects.count())
        ages = sorted(Account.objects.filter(kind__in=["union", "state", "municipality"]).values_list("pk", "created_at"))
        self.assertEqual(len(ages), n)
        self.go_days(3)
        self.assertEqual(ensure_accounts(), n)
        self.assertEqual(sorted(Account.objects.filter(kind__in=["union", "state", "municipality"]).values_list("pk", "created_at")), ages)
