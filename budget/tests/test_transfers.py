"""Repasses entre governos (09 §3-§4, §27, §30, §40): hierarquia, autoridade, fundos, conservação, registro público, Action Registry."""
from unittest import mock

from budget import authority, fiscal, transfers
from budget.audit import audit_budget
from budget.constants import Level
from budget.models import GovernmentDecision
from geography.models import City, State
from ledger import services as ledger
from ledger.audit import ledger_metrics
from ledger.constants import Nature
from ledger.models import Entry
from ledger.obligations import open_obligation
from players import registry
from players.services import ActionResult

from .base import BudgetBase


class TransferTests(BudgetBase):
    def setUp(self):
        super().setUp()
        self.fund(self.union(), 1_000_000)
        self.fund(self.st(), 500_000)

    def codes(self, target, actor=None):
        res = transfers.transfer_budget((actor or self.president).pk, target)
        self.assertFalse(res.ok, res)
        return res.code

    def test_the_president_transfers_to_a_state_and_the_money_only_moves(self):
        supply = ledger_metrics()["in_circulation"]
        res = transfers.transfer_budget(self.president.pk, self.to_state(250_000, reason="obras"))
        self.assertTrue(res.ok, res)
        self.assertEqual((self.bal(self.union()), self.bal(self.st())), (750_000, 750_000))
        self.assertEqual(ledger_metrics()["in_circulation"], supply)
        e = Entry.objects.get(transaction__key=res.detail["ledger_key"])
        self.assertEqual((e.nature, e.category, e.operation, e.amount), ("gov_transfer", "transfer", "repasse", 250_000))
        self.assertEqual(e.transaction.actor, f"player:{self.president.pk}")
        self.assertEqual(e.at, self.clk.now())

    def test_the_governor_transfers_to_a_municipality_of_his_state(self):
        res = transfers.transfer_budget(self.governor.pk, self.to_city(100_000))
        self.assertTrue(res.ok, res)
        self.assertEqual((self.bal(self.st()), self.bal(self.mun())), (400_000, 100_000))

    def test_the_decision_is_recorded_public_and_carries_the_funds_breakdown(self):
        res = transfers.transfer_budget(self.president.pk, self.to_state(1_000, reason="teste"))
        d = GovernmentDecision.objects.get(pk=res.detail["decision"])
        self.assertEqual((d.kind, d.level, d.territory_id, d.actor_id, d.competence_day), ("transfer", "union", 0, self.president.pk, self.day_of_now()))
        self.assertEqual(d.data["reason"], "teste")
        self.assertEqual(d.data["funds"]["spendable"], 1_000_000)
        self.assertEqual(d.ledger_key, res.detail["ledger_key"])

    def test_hierarchy_cannot_be_skipped_or_inverted(self):
        for src, dst in ((Level.UNION, Level.MUNICIPALITY), (Level.STATE, Level.UNION), (Level.MUNICIPALITY, Level.STATE),
                         (Level.UNION, Level.UNION), (Level.STATE, Level.STATE)):
            sid = {Level.UNION: 0, Level.STATE: self.state.pk, Level.MUNICIPALITY: self.city_a.pk}
            target = {"from": self.gov(src, sid[src]), "to": self.gov(dst, sid[dst]), "amount": 10}
            self.assertEqual(self.codes(target), "TRANSFER_NOT_ALLOWED", (src, dst))
        self.assertEqual(Entry.objects.filter(nature="gov_transfer").count(), 0)

    def test_the_municipality_must_belong_to_the_state(self):
        other = State.objects.create(name="Outro", x=1, y=1)
        city = City.objects.create(state=other, index=1, name="Fora", x=1, y=1)
        self.assertEqual(self.codes(self.to_city(10, city=city), self.governor), "MUNICIPALITY_NOT_IN_STATE")

    def test_only_the_office_holder_acts_for_the_government(self):
        self.assertEqual(self.codes(self.to_state(10), self.other), "NOT_OFFICE_HOLDER")
        self.assertEqual(self.codes(self.to_state(10), self.governor), "NOT_OFFICE_HOLDER")
        self.assertEqual(self.codes(self.to_city(10), self.president), "NOT_OFFICE_HOLDER")
        self.assertEqual(self.codes(self.to_city(10), self.mayor), "NOT_OFFICE_HOLDER")
        self.holders.clear()
        self.assertEqual(self.codes(self.to_state(10)), "NO_OFFICE_HOLDER")

    def test_without_any_provider_nobody_has_authority(self):
        authority.clear_office_providers()
        self.addCleanup(authority.register_office_provider, "test", lambda l, i: self.holders.get((l, i)))
        self.assertEqual(self.codes(self.to_state(10)), "NO_OFFICE_HOLDER")

    def test_two_providers_that_disagree_fail_instead_of_choosing(self):
        authority.register_office_provider("rival", lambda l, i: self.other.pk if l is Level.UNION else None)
        self.addCleanup(authority.unregister_office_provider, "rival")
        self.assertEqual(self.codes(self.to_state(10)), "OFFICE_CONFLICT")

    def test_two_providers_that_agree_are_fine(self):
        authority.register_office_provider("same", lambda l, i: self.president.pk if l is Level.UNION else None)
        self.addCleanup(authority.unregister_office_provider, "same")
        self.assertTrue(transfers.transfer_budget(self.president.pk, self.to_state(10)).ok)

    def test_invalid_parameters(self):
        bad = [None, [], {}, {"from": 1}, {**self.to_state(10), "extra": 1}, {**self.to_state(10), "amount": 0}, {**self.to_state(10), "amount": -5},
               {**self.to_state(10), "amount": True}, {**self.to_state(10), "amount": "10"}, {**self.to_state(10), "amount": 1.5},
               {**self.to_state(10), "amount": 2 ** 63}]
        for t in bad:
            res = transfers.transfer_budget(self.president.pk, t)
            self.assertFalse(res.ok, t)
            self.assertIn(res.code, {"INVALID_PARAMS", "INVALID_AMOUNT"}, t)
        self.assertEqual(self.codes({**self.to_state(10), "reason": 5}), "INVALID_REASON")
        self.assertEqual(self.codes({**self.to_state(10), "reason": "x" * 201}), "INVALID_REASON")
        self.assertEqual(self.codes({"from": {"level": "galaxy", "id": 0}, "to": self.gov(Level.STATE, self.state.pk), "amount": 1}), "INVALID_GOVERNMENT")
        self.assertEqual(self.codes({"from": self.gov(Level.UNION, 3), "to": self.gov(Level.STATE, self.state.pk), "amount": 1}), "INVALID_GOVERNMENT")
        self.assertEqual(self.codes({"from": self.gov(Level.UNION), "to": self.gov(Level.STATE, 99999), "amount": 1}), "GOVERNMENT_NOT_FOUND")
        self.assertEqual(transfers.transfer_budget("x", self.to_state(1)).code, "PLAYER_NOT_FOUND")
        self.assertEqual(transfers.transfer_budget(10 ** 9, self.to_state(1)).code, "PLAYER_NOT_FOUND")
        self.assertEqual(Entry.objects.filter(nature="gov_transfer").count(), 0)

    def test_the_boundary_of_available_funds(self):
        self.assertEqual(self.codes(self.to_state(1_000_001)), "INSUFFICIENT_FUNDS")
        self.assertTrue(transfers.transfer_budget(self.president.pk, self.to_state(1_000_000)).ok)
        self.assertEqual(self.bal(self.union()), 0)
        self.assertEqual(self.codes(self.to_state(1)), "INSUFFICIENT_FUNDS")

    def test_committed_budget_is_not_transferable(self):
        self.assertTrue(ledger.hold(self.union().pk, 400_000, key="h", reference_kind="test", reference_id="1", at=self.clk.now()).ok)
        res = transfers.transfer_budget(self.president.pk, self.to_state(600_001))
        self.assertEqual(res.code, "INSUFFICIENT_FUNDS")
        self.assertEqual((res.detail["committed"], res.detail["spendable"], res.detail["shortfall"]), (400_000, 600_000, 1))
        self.assertTrue(transfers.transfer_budget(self.president.pk, self.to_state(600_000)).ok)

    def test_pending_obligations_come_first_K3(self):
        self.assertTrue(open_obligation(self.union().pk, ledger.player_account(self.other.pk).pk, 300_000, Nature.PUBLIC_WORKS_PAYMENT, key="o1",
                                        reference_kind="test", reference_id="1", at=self.clk.now()).ok)
        res = transfers.transfer_budget(self.president.pk, self.to_state(700_001))
        self.assertEqual((res.code, res.detail["pending_obligations"], res.detail["spendable"]), ("INSUFFICIENT_FUNDS", 300_000, 700_000))
        self.assertTrue(transfers.transfer_budget(self.president.pk, self.to_state(700_000)).ok)

    def test_the_pending_rule_is_a_provisional_parameter(self):
        self.assertTrue(open_obligation(self.union().pk, ledger.player_account(self.other.pk).pk, 300_000, Nature.PUBLIC_WORKS_PAYMENT, key="o1",
                                        reference_kind="test", reference_id="1", at=self.clk.now()).ok)
        with mock.patch("budget.params.TRANSFERS_RESPECT_PENDING_OBLIGATIONS", False):
            self.assertTrue(transfers.transfer_budget(self.president.pk, self.to_state(1_000_000)).ok)

    def test_each_transfer_is_its_own_decision_not_an_idempotent_replay(self):
        a = transfers.transfer_budget(self.president.pk, self.to_state(10))
        b = transfers.transfer_budget(self.president.pk, self.to_state(10))
        self.assertTrue(a.ok and b.ok)
        self.assertNotEqual(a.detail["ledger_key"], b.detail["ledger_key"])
        self.assertEqual(GovernmentDecision.objects.count(), 2)
        self.assertEqual(self.bal(self.st()), 500_020)

    def test_a_ledger_refusal_leaves_no_decision_behind(self):
        with mock.patch("budget.transfers.ledger.transfer", return_value=ActionResult(False, "ACCOUNT_CLOSED", {})):
            res = transfers.transfer_budget(self.president.pk, self.to_state(10))
        self.assertEqual(res.code, "ACCOUNT_CLOSED")
        self.assertEqual(GovernmentDecision.objects.count(), 0)
        self.assertEqual(self.bal(self.union()), 1_000_000)

    def test_refused_attempts_leave_no_trace(self):
        self.codes(self.to_state(10), self.other)
        self.assertEqual((GovernmentDecision.objects.count(), Entry.objects.filter(nature="gov_transfer").count()), (0, 0))

    def test_the_transfer_counts_as_revenue_for_the_receiver_and_the_ceiling_sees_it(self):
        transfers.transfer_budget(self.governor.pk, self.to_city(80_000))
        v = fiscal.fiscal_view(Level.MUNICIPALITY, self.city_a.pk, self.clk.now())
        self.assertEqual(v["period"]["revenue"], 80_000)
        self.assertEqual(v["period"]["revenue_by_nature"], {"gov_transfer": 80_000})

    def test_the_funds_quote_is_structured(self):
        q = transfers.funds_quote(self.union(), 5)
        self.assertEqual(set(q), {"requested", "gross", "committed", "available_after_commitments", "pending_obligations", "spendable", "shortfall", "ok",
                                  "explained"})

    def test_the_audit_accepts_real_transfers(self):
        transfers.transfer_budget(self.president.pk, self.to_state(10))
        transfers.transfer_budget(self.governor.pk, self.to_city(10))
        r = audit_budget()
        self.assertTrue(r.ok, r.findings)
        self.assertEqual(r.stats["transfer_decisions"], 2)


class TransferActionTests(BudgetBase):
    """Bots e jogadores usam o mesmo Action Registry (CLAUDE.md §5.4): a consulta e a execução usam a mesma regra."""

    def setUp(self):
        super().setUp()
        self.fund(self.union(), 1_000)

    def test_availability_matches_execution(self):
        for player, target in ((self.president, self.to_state(500)), (self.other, self.to_state(500)), (self.president, self.to_state(5_000))):
            avail = registry.check_action(player.pk, "budget_transfer", target)
            res = registry.execute_action(player.pk, "budget_transfer", target)
            self.assertEqual(avail.available, res.ok, (player.pk, target, avail, res))
            if not res.ok:
                self.assertEqual(avail.code, res.code)

    def test_execution_through_the_registry_moves_the_money(self):
        res = registry.execute_action(self.president.pk, "budget_transfer", self.to_state(400))
        self.assertTrue(res.ok, res)
        self.assertEqual(self.bal(self.st()), 400)

    def test_the_preview_shows_what_can_be_transferred(self):
        pv = registry.check_action(self.president.pk, "budget_transfer", self.to_state(400)).preview
        self.assertEqual(pv["funds"]["spendable"], 1_000)

    def test_a_target_is_required(self):
        self.assertEqual(registry.execute_action(self.president.pk, "budget_transfer", None).code, "TARGET_REQUIRED")
