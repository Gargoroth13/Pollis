"""Maior patrimônio líquido (14.3.1) e seu recorde (14.4.1): só o que o ledger reconhece, menos obrigações abertas."""
from decimal import Decimal

from core import ticks
from core.models import WorldClock
from core.timeline import TickKind
from ledger import hooks as ledger_hooks, obligations, services as ledger
from ledger.constants import Nature
from ledger.models import Account, Entry, Obligation
from rankings import live, records, wiring
from rankings.constants import Cat
from rankings.models import RankingHistorico

from .base import DAY, HOUR, T0, RankingsTestCase


class NetWorthTests(RankingsTestCase):
    def owe(self, debtor, creditor, amount, key):
        res = obligations.open_obligation(debtor.pk, creditor.pk, amount, Nature.WAGE, key=key, reference_kind="t", reference_id=key)
        self.assertTrue(res.ok, res)
        return Obligation.objects.get(pk=res.detail["obligation_id"])

    def test_net_worth_is_balance_plus_receivables_minus_payables_with_breakdown(self):
        a = self.acct()
        self.fund(a, 10_000)
        self.owe(a, self.company(1), 3_000, "o1")                 # a pagar
        self.owe(self.company(2), a, 1_200, "o2")                 # a receber
        nw = live.net_worth_of(self.player.pk)
        self.assertEqual((nw["value"], nw["balance"], nw["receivables"], nw["obligations_open"]), (8_200, 10_000, 1_200, 3_000))
        steps = {s["key"]: s for s in nw["explained"]["steps"]}
        self.assertEqual([(k, steps[k]["amount"]) for k in ("balance", "receivables", "open_obligations")],
                         [("balance", "10000"), ("receivables", "1200"), ("open_obligations", "-3000")])
        self.assertEqual(nw["explained"]["value"], "8200")

    def test_components_separate_receivables_from_payables_and_record_that_the_value_is_nominal(self):
        """Decisão do GD (2026-11-04): detalhamento separado; valor nominal, sem garantia de recuperação."""
        a = self.acct()
        self.fund(a, 10_000)
        self.owe(a, self.company(1), 3_000, "o1")
        self.owe(self.company(2), a, 1_200, "o2")
        c = live.net_worth_of(self.player.pk)["components"]
        self.assertEqual((c["balance"], c["receivables"], c["obligations_payable"]), (10_000, 1_200, 3_000))
        rules = {r["key"]: r["applies"] for r in c["rules"]}
        self.assertEqual(rules, {"receivables_nominal_value": True, "paid_and_cancelled_obligations_excluded": True})
        row = live.net_worth_rows()[0]["detail"]["components"]                 # o mesmo detalhamento no ranking
        self.assertEqual((row["balance"], row["receivables"], row["obligations_payable"]), (10_000, 1_200, 3_000))

    def test_nominal_value_rule_applies_only_when_there_are_receivables(self):
        self.fund(self.acct(), 500)
        c = live.net_worth_of(self.player.pk)["components"]
        self.assertEqual(c["receivables"], 0)
        self.assertFalse({r["key"]: r["applies"] for r in c["rules"]}["receivables_nominal_value"])

    def test_page_shows_receivables_and_payables_on_separate_lines_with_the_nominal_note(self):
        a = self.acct()
        self.fund(a, 10_000)
        self.owe(a, self.company(1), 3_000, "o1")
        self.owe(self.company(2), a, 1_200, "o2")
        html = self.client.get("/rankings/").content.decode()
        self.assertIn("Créditos a receber: R$ 12,00", html)
        self.assertIn("Obrigações a pagar: R$ 30,00", html)
        self.assertIn("Saldo: R$ 100,00", html)
        self.assertIn("valor nominal", html)
        self.assertIn("não representam garantia de recuperação", html)

    def test_partially_paid_obligation_counts_only_the_remainder(self):
        a = self.acct()
        self.fund(a, 10_000)
        ob = self.owe(a, self.company(1), 3_000, "o1")
        Obligation.objects.filter(pk=ob.pk).update(amount_paid=1_000)
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 8_000)

    def test_settled_and_cancelled_obligations_do_not_count(self):
        a = self.acct()
        self.fund(a, 5_000)
        ob = self.owe(a, self.company(1), 3_000, "o1")
        Obligation.objects.filter(pk=ob.pk).update(status="paid", amount_paid=3_000)
        ob2 = self.owe(a, self.company(1), 500, "o2")
        Obligation.objects.filter(pk=ob2.pk).update(status="cancelled")
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 5_000)

    def test_receivables_count_only_the_remainder_of_open_obligations(self):
        """Decisão do GD (2026-11-03): créditos a receber entram; pago e cancelado não."""
        a = self.acct()
        self.fund(a, 1_000)
        ob = self.owe(self.company(1), a, 9_000, "o-receivable")
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 10_000)
        Obligation.objects.filter(pk=ob.pk).update(amount_paid=4_000)         # parcial: restam 5.000
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 6_000)
        Obligation.objects.filter(pk=ob.pk).update(status="paid", amount_paid=9_000)
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 1_000)
        ob2 = self.owe(self.company(1), a, 700, "o-cancelled")
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 1_700)
        Obligation.objects.filter(pk=ob2.pk).update(status="cancelled")
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 1_000)

    def test_receivable_and_payable_between_two_players_are_counted_on_each_side(self):
        p2 = self.make_player("p2")
        self.fund(self.acct(), 1_000)
        self.fund(self.acct(p2), 1_000)
        self.owe(self.acct(p2), self.acct(), 400, "o")                # p2 deve 400 a p1
        self.assertEqual((live.net_worth_of(self.player.pk)["value"], live.net_worth_of(p2.pk)["value"]), (1_400, 600))

    def test_reserved_money_still_counts(self):
        a = self.acct()
        self.fund(a, 4_000)
        self.assertTrue(ledger.hold(a.pk, 1_500, key="h1", reference_kind="t", reference_id="1").ok)
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 4_000)

    def test_net_worth_can_be_negative(self):
        a = self.acct()
        self.owe(a, self.company(1), 700, "o1")
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], -700)

    def test_player_without_ledger_account_is_absent_not_zero(self):
        Account.objects.filter(kind="player", owner_id=self.player.pk).delete()     # sem lançamentos: pode sumir
        self.assertIsNone(live.net_worth_of(self.player.pk))
        self.assertEqual(live.net_worth_rows(), [])

    def test_only_players_are_ranked_not_companies(self):
        self.fund(self.company(1), 99_999)
        self.fund(self.acct(), 10)
        rows = live.net_worth_rows()
        self.assertEqual([(r["entity_type"], r["entity_id"]) for r in rows], [("player", self.player.pk)])

    def test_ranking_order_ties_share_position_and_limit(self):
        p2, p3, p4 = (self.make_player(n) for n in ("p2", "p3", "p4"))
        for p, amount in ((self.player, 500), (p2, 900), (p3, 900), (p4, 100)):
            self.fund(self.acct(p), amount)
        rows = live.net_worth_rows()
        self.assertEqual([(r["name"], r["value"], r["rank"]) for r in rows],
                         [("p2", 900, 1), ("p3", 900, 1), ("p1", 500, 3), ("p4", 100, 4)])
        top2 = live.net_worth_rows(limit=2)
        self.assertEqual([(r["name"], r["rank"]) for r in top2], [("p2", 1), ("p3", 1)])

    def test_live_ranking_payload(self):
        self.fund(self.acct(), 12_345)
        r = live.live_ranking(Cat.NET_WORTH)
        self.assertTrue(r["available"])
        self.assertEqual((r["status"], r["unit"], r["entries"][0]["display"]), ("active", "centavos", "R$ 123,45"))
        self.assertEqual(r["entries"][0]["detail"]["steps"][0]["key"], "balance")

    def test_invalid_limit(self):
        for bad in (0, -1, True, "5"):
            with self.assertRaises(ValueError):
                live.net_worth_rows(limit=bad)


class NetWorthRecordTests(RankingsTestCase):
    """Recorde de patrimônio (14.4.1): mantido pelo gancho de fim de operação do ledger (ver test_net_worth_record_ledger)."""

    def rec(self):
        return RankingHistorico.objects.get(category=Cat.NET_WORTH_RECORD.value)

    def test_record_grows_and_persists_after_the_fall(self):
        a = self.acct()
        self.fund(a, 10_000)
        r = self.rec()
        self.assertEqual((r.entity_id, r.value, r.recorded_at), (self.player.pk, 10_000, T0))
        self.assertEqual((r.metadata["balance"], r.metadata["receivables"], r.metadata["obligations_open"]), (10_000, 0, 0))
        self.fund(a, 5_000)
        self.assertEqual(self.rec().value, 15_000)
        self.assertTrue(self.pay(a, self.company(1), 14_000).ok)          # patrimônio cai para 1.000
        self.assertEqual(self.rec().value, 15_000)
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 1_000)
        self.assertEqual(records.check_net_worth_record(self.player.pk).reason, "NOT_GREATER")

    def test_tie_keeps_the_first_holder_and_replaying_is_idempotent(self):
        p2 = self.make_player("p2")
        self.fund(self.acct(), 7_000)
        self.clk.advance(hours=1)
        self.fund(self.acct(p2), 7_000)
        self.assertEqual(self.rec().entity_id, self.player.pk)
        self.assertEqual(records.check_net_worth_record(self.player.pk).reason, "NOT_GREATER")
        self.assertEqual(records.check_net_worth_record(p2.pk).reason, "NOT_GREATER")
        self.assertEqual(RankingHistorico.objects.count(), 1)

    def test_tie_goes_to_whoever_reached_it_earlier_even_if_applied_later(self):
        records.offer_value_record(Cat.NET_WORTH_RECORD, "player", 2, 500, T0 + HOUR)
        out = records.offer_value_record(Cat.NET_WORTH_RECORD, "player", 1, 500, T0)          # chegou antes
        self.assertEqual((out.reason, self.rec().entity_id), ("REPLACED", 1))
        self.assertEqual(records.offer_value_record(Cat.NET_WORTH_RECORD, "player", 3, 500, T0 + 2 * HOUR).reason, "NOT_GREATER")

    def test_zero_or_negative_net_worth_creates_no_record(self):
        self.acct()
        self.assertFalse(records.check_net_worth_record(self.player.pk).changed)
        self.assertFalse(RankingHistorico.objects.exists())

    def test_player_without_account_creates_no_record(self):
        Account.objects.filter(kind="player", owner_id=self.player.pk).delete()
        self.assertFalse(records.check_net_worth_record(self.player.pk).changed)

    def test_sweep_reconciles_when_the_hook_was_absent(self):
        """O gancho mantém o recorde; a varredura só reconcilia o que escapou (ex.: gancho desligado)."""
        ledger_hooks.unregister_operation_hook(wiring.LEDGER_HOOK_NET_WORTH)
        self.addCleanup(wiring.connect)
        p2 = self.make_player("p2")
        self.fund(self.acct(), 3_000)
        self.fund(self.acct(p2), 8_000)
        self.assertFalse(RankingHistorico.objects.exists())
        out = records.sweep_net_worth_record()
        self.assertEqual((out.reason, self.rec().entity_id, self.rec().value), ("CREATED", p2.pk, 8_000))
        self.assertEqual(records.sweep_net_worth_record().reason, "NOT_GREATER")

    def test_sweep_with_nobody_is_a_noop(self):
        self.assertFalse(records.sweep_net_worth_record().changed)

    def test_daily_world_tick_runs_the_sweep_and_hourly_tick_drains_candidates(self):
        self.assertIn(wiring.TICK_SWEEP, [r.name for r in ticks.registry.handlers_for(ticks.WORLD, TickKind.DAILY)])
        self.assertIn(wiring.TICK_RETRY, [r.name for r in ticks.registry.handlers_for(ticks.WORLD, TickKind.HOURLY)])
        ledger_hooks.unregister_operation_hook(wiring.LEDGER_HOOK_NET_WORTH)
        self.addCleanup(wiring.connect)
        self.fund(self.acct(), 2_500)
        WorldClock.load()
        WorldClock.objects.filter(pk=1).update(world_processed_until=T0)
        self.clk.advance(days=2)
        ticks.advance_world()
        self.assertEqual(self.rec().value, 2_500)

    def test_wiring_is_idempotent(self):
        wiring.connect()
        wiring.connect()
        for kind, name in ((TickKind.DAILY, wiring.TICK_SWEEP), (TickKind.HOURLY, wiring.TICK_RETRY)):
            names = [r.name for r in ticks.registry.handlers_for(ticks.WORLD, kind)]
            self.assertEqual(names.count(name), 1)
        self.assertEqual(ledger_hooks.operation_hook_names().count(wiring.LEDGER_HOOK_NET_WORTH), 1)

    def test_rankings_never_create_or_move_money(self):
        self.fund(self.acct(), 1_000)
        before = (Entry.objects.count(), self.total_supply())
        records.check_net_worth_record(self.player.pk)
        records.sweep_net_worth_record()
        live.page_data()
        self.assertEqual((Entry.objects.count(), self.total_supply()), before)
