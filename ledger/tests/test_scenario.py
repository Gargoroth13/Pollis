from ledger import services as ledger
from ledger.constants import Nature
from ledger.models import Entry

from .base import LedgerTestCase


class ScenarioGrantTests(LedgerTestCase):
    def test_missing_value_refuses_activation_and_lists_pending(self):
        ledger.create_scenario("s1", {"player": 1000, "union": None})
        res = ledger.activate_scenario("s1", ["player", "union", "state"])
        self.assertEqual(res.code, "SCENARIO_GRANT_UNSPECIFIED")
        self.assertEqual(res.detail["missing"], ["state", "union"])
        self.assertIsNone(ledger.active_scenario())

    def test_explicit_zero_is_valid_and_emits_nothing(self):
        ledger.create_scenario("s2", {"player": 0, "union": 0})
        self.assertTrue(ledger.activate_scenario("s2", ["player", "union"]).ok)
        acc = self.company(1)
        res = ledger.grant_for_role(acc.pk, "player")
        self.assertTrue(res.ok)
        self.assertTrue(res.detail["explicit_zero"])
        self.assertEqual(Entry.objects.count(), 0)

    def test_role_absent_from_active_scenario_refuses(self):
        ledger.create_scenario("s3", {"player": 5})
        ledger.activate_scenario("s3", ["player"])
        self.assertEqual(ledger.grant_for_role(self.company(1).pk, "union").code, "SCENARIO_GRANT_UNSPECIFIED")

    def test_grant_is_only_source_and_idempotent_per_account(self):
        ledger.create_scenario("s4", {"player": 700})
        ledger.activate_scenario("s4", ["player"])
        acc = self.company(1)
        r1 = ledger.grant_for_role(acc.pk, "player")
        r2 = ledger.grant_for_role(acc.pk, "player")
        self.assertEqual((r1.detail["granted"], self.bal(acc)), (700, 700))
        self.assertTrue(r2.detail["already_posted"])
        self.assertEqual(self.bal(acc), 700)
        e = Entry.objects.get()
        self.assertEqual((e.nature, e.reference_kind, e.reference_id, e.from_account.kind), ("scenario_grant", "scenario", "s4", "issuance"))
        emitted, circ, _, _ = self.total_supply()
        self.assertEqual((emitted, circ), (700, 700))

    def test_no_active_scenario_creates_no_money(self):
        res = ledger.grant_for_role(self.company(1).pk, "player")
        self.assertEqual((res.ok, res.code), (True, "NO_ACTIVE_SCENARIO"))
        self.assertEqual(Entry.objects.count(), 0)

    def test_only_one_active_scenario(self):
        ledger.create_scenario("a", {"player": 1})
        ledger.create_scenario("b", {"player": 2})
        ledger.activate_scenario("a", ["player"])
        ledger.activate_scenario("b", ["player"])
        self.assertEqual(ledger.active_scenario().name, "b")

    def test_unknown_scenario_and_invalid_lines(self):
        self.assertEqual(ledger.activate_scenario("nope", []).code, "SCENARIO_NOT_FOUND")
        self.assertEqual(ledger.grant_scenario_allocation("nope", self.company(1).pk, 5).code, "SCENARIO_NOT_FOUND")
        ledger.create_scenario("c", {})
        for bad in (-1, 1.5, True):
            with self.assertRaises(ValueError):
                ledger.set_grant_line("c", "player", bad)

    def test_union_state_municipality_and_bank_grants(self):
        ledger.create_scenario("gov", {"union": 10_000, "militia_bank": 0})
        ledger.activate_scenario("gov", ["union", "militia_bank"])
        union = ledger.union_account()
        self.assertEqual(ledger.grant_for_role(union.pk, "union").detail["granted"], 10_000)
        self.assertEqual(self.bal(union), 10_000)

    def test_grant_zero_amount_direct_refused(self):
        ledger.create_scenario("z", {})
        self.assertEqual(ledger.grant_scenario_allocation("z", self.company(1).pk, 0).code, "AMOUNT_NOT_POSITIVE")
