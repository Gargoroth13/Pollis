from decimal import Decimal

from ledger import integration, services as ledger
from ledger.constants import Nature
from ledger.models import Account, Entry
from players import registry
from travel import services as travel
from travel.models import Journey
from travel.tests.base import TravelTestCase

from .base import LedgerHelpers


class IntegrationTestCase(LedgerHelpers, TravelTestCase):
    def setUp(self):
        super().setUp()
        self.ledger_setup()
        integration.register_travel_payment()          # o app registra em ready(); a base de viagem parte sem handler

    def activate(self, player=0, union=0):
        ledger.create_scenario("sc", {"player": player, "union": union})
        self.assertTrue(ledger.activate_scenario("sc", ["player", "union"]).ok)

    def player_cents(self, player=None):
        return ledger.balance_of(ledger.player_account((player or self.player).pk).pk)


class PlayerCreationTests(IntegrationTestCase):
    def test_new_player_gets_account_and_scenario_grant(self):
        self.activate(player=5000)
        p = self.new_player("novo")
        self.assertEqual(self.player_cents(p), 5000)
        e = Entry.objects.get(to_account__owner_id=p.pk, nature="scenario_grant")
        self.assertEqual((e.reference_id, e.from_account.kind), ("sc", "issuance"))

    def test_explicit_zero_grant_creates_account_without_money(self):
        self.activate(player=0)
        p = self.new_player("zero")
        self.assertEqual(self.player_cents(p), 0)
        self.assertFalse(Entry.objects.filter(to_account__owner_id=p.pk).exists())

    def test_without_scenario_account_exists_and_no_money_is_created(self):
        p = self.new_player("sem-cenario")
        self.assertTrue(Account.objects.filter(kind="player", owner_id=p.pk).exists())
        self.assertEqual(self.player_cents(p), 0)

    def test_unspecified_role_in_active_scenario_blocks_player_creation(self):
        ledger.create_scenario("incompleto", {"union": 0})
        ledger.activate_scenario("incompleto", ["union"])
        with self.assertRaises(ledger.LedgerRefusal) as cm:
            self.new_player("x")
        self.assertEqual(cm.exception.result.code, "SCENARIO_GRANT_UNSPECIFIED")


class TravelPaymentTests(IntegrationTestCase):
    def test_without_active_scenario_travel_behaves_as_before(self):
        r = self.go(self.far())
        self.assertTrue(r.ok)
        self.assertEqual(r.detail["payment"], "NO_PAYMENT_SYSTEM")
        self.assertFalse(Journey.objects.get().charged)
        self.assertEqual(Entry.objects.count(), 0)

    def test_travel_charges_player_to_union_and_marks_journey(self):
        self.activate(player=0)
        ledger.create_scenario("extra", {})
        ledger.grant_scenario_allocation("extra", ledger.player_account(self.player.pk).pk, 100_000)
        dest = self.far()
        before = self.player_cents()
        r = self.go(dest)
        self.assertTrue(r.ok, r)
        cents = int(r.detail["cost"] * 100)
        self.assertEqual(r.detail["payment"], "CHARGED")
        self.assertTrue(Journey.objects.get().charged)
        self.assertEqual((self.player_cents(), self.bal_union()), (before - cents, cents))
        e = Entry.objects.get(nature="travel_fee")
        self.assertEqual((e.from_account.owner_id, e.to_account.kind, e.amount, e.reference_kind, e.operation),
                         (self.player.pk, "union", cents, "travel", "start_travel"))
        self.assertTrue(e.transaction.key.startswith(f"travel:{self.player.pk}:"))

    def bal_union(self):
        return ledger.balance_of(ledger.union_account().pk)

    def test_insufficient_funds_refuses_without_journey_or_entry(self):
        self.activate(player=0)
        r = self.go(self.far())
        self.assertEqual((r.ok, r.code), (False, "INSUFFICIENT_FUNDS"))
        self.assertEqual((Journey.objects.count(), Entry.objects.filter(nature="travel_fee").count()), (0, 0))

    def test_failure_after_payment_rolls_back_money_too(self):
        from unittest import mock
        self.activate(player=0)
        ledger.create_scenario("extra", {})
        ledger.grant_scenario_allocation("extra", ledger.player_account(self.player.pk).pk, 100_000)
        with mock.patch.object(Journey.objects, "create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.go(self.far())
        self.assertEqual(self.player_cents(), 100_000)
        self.assertEqual(Entry.objects.filter(nature="travel_fee").count(), 0)

    def test_check_action_reports_insufficient_funds_before_executing(self):
        self.activate(player=0)
        dest = self.far()
        a = registry.check_action(self.player.pk, "travel", dest.pk)
        self.assertEqual((a.available, a.code), (False, "INSUFFICIENT_FUNDS"))
        self.assertEqual(Entry.objects.filter(nature="travel_fee").count(), 0)         # consulta não move dinheiro
        ledger.create_scenario("extra", {})
        ledger.grant_scenario_allocation("extra", ledger.player_account(self.player.pk).pk, 100_000)
        b = registry.check_action(self.player.pk, "travel", dest.pk)
        self.assertEqual((b.available, b.code), (True, "OK"))
        self.assertEqual(self.player_cents(), 100_000)

    def test_check_matches_execute_for_bots_and_humans(self):
        self.activate(player=0)
        dest = self.far()
        check = registry.check_action(self.player.pk, "travel", dest.pk)
        res = registry.execute_action(self.player.pk, "travel", dest.pk)
        self.assertEqual((check.available, check.code), (res.ok, res.code))

    def test_funds_quote_for_the_trip_cost_has_explained(self):
        self.activate(player=0)
        r = self.go(self.far())
        res = ledger.quote(ledger.player_account(self.player.pk).pk, int(r.detail["cost"] * 100))
        self.assertEqual(res.code, "INSUFFICIENT_FUNDS")
        self.assertIn("steps", res.detail["explained"])

    def test_free_trip_never_charges(self):
        from django.test import override_settings
        self.activate(player=0)
        with override_settings(POLIS_GEOGRAPHY={"travel_cost_per_unit": 0}):
            r = self.go(self.far())
        self.assertTrue(r.ok)
        self.assertEqual(r.detail["payment"], "NOT_REQUIRED")
        self.assertEqual(Entry.objects.filter(nature="travel_fee").count(), 0)

    def test_handler_registration_is_idempotent(self):
        integration.register_travel_payment()
        self.assertTrue(travel.has_payment_handler() is False)         # sem cenário ativo o sistema de dinheiro está inativo
        self.activate()
        self.assertTrue(travel.has_payment_handler())
