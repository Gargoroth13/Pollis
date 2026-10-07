from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from players import hooks
from players.actions import Action
from players.hooks import ActivityContext
from players.services import perform_action
from skills.models import PlayerSkill
from travel.balance import get_travel_balance

from .base import D, T0, TravelTestCase


class ActionsBlockedWhileTravelingTests(TravelTestCase):
    """04 §6, §20: durante a viagem o jogador não executa ação que dependa de presença física."""

    def act(self, action, player=None, **kw):
        p = player or self.player
        self.set_state(p, energy=100)
        return perform_action(p.pk, action, **kw)

    def travel(self):
        self.go(self.far())

    def test_work_is_refused_with_a_code_while_traveling(self):
        self.travel()
        r = self.act(Action.WORK)
        self.assertEqual((r.ok, r.code), (False, "TRAVELING"))
        self.assertIn("TRAVELING", r.detail["reasons"])

    def test_the_refusal_costs_nothing_and_grants_no_skill(self):
        self.travel()
        before = self.state()
        self.act(Action.WORK, activity=ActivityContext(skills=("physical",)))
        after = self.state()
        self.assertEqual((after.energy, after.burnout, after.last_work_at), (100, before.burnout, None))
        self.assertEqual(float(PlayerSkill.objects.get(player=self.player, skill="physical").level), 0)

    def test_work_works_again_the_instant_the_player_arrives(self):
        arrives = self.go(self.far()).detail["arrives_at"]
        self.clk.set(arrives - 1)
        self.assertEqual(self.act(Action.WORK).code, "TRAVELING")
        self.clk.set(arrives)
        self.assertTrue(self.act(Action.WORK).ok)

    def test_work_before_departure_is_not_affected(self):
        self.assertTrue(self.act(Action.WORK).ok)

    def test_actions_that_do_not_depend_on_presence_are_not_blocked(self):
        """O 04 só nomeia o Trabalho; Estudo e Lazer seguem permitidos por padrão ([ABERTO], configurável)."""
        self.travel()
        self.assertTrue(self.act(Action.STUDY).ok)
        self.assertTrue(self.act(Action.LEISURE).ok)

    def test_the_activity_can_say_it_does_not_require_presence(self):
        """04 §6: bloqueia 'quando o trabalho exigir presença física': um trabalho remoto passa."""
        self.travel()
        self.assertTrue(self.act(Action.WORK, activity=ActivityContext(requires_presence=False)).ok)

    def test_the_activity_can_say_it_requires_presence(self):
        self.travel()
        self.assertEqual(self.act(Action.STUDY, activity=ActivityContext(requires_presence=True)).code, "TRAVELING")
        self.assertEqual(self.act(Action.LEISURE, activity=ActivityContext(requires_presence=True)).code, "TRAVELING")

    @override_settings(POLIS_TRAVEL_BALANCE={"presence_dependent_by_default": {"study": True}})
    def test_presence_defaults_are_configurable_per_action(self):
        self.travel()
        self.assertEqual(self.act(Action.STUDY).code, "TRAVELING")
        self.assertEqual(self.act(Action.WORK).code, "TRAVELING")                 # o resto do padrão se mantém
        self.assertTrue(self.act(Action.LEISURE).ok)

    @override_settings(POLIS_TRAVEL_BALANCE={"presence_dependent_by_default": {"work": False}})
    def test_work_can_be_configured_as_not_presence_dependent(self):
        self.travel()
        self.assertTrue(self.act(Action.WORK).ok)

    def test_travel_reason_comes_after_the_players_own_reasons_in_a_fixed_order(self):
        self.travel()
        self.set_state(burnout=100, burnout_active=True)
        r = self.act(Action.WORK)
        self.assertEqual((r.code, r.detail["reasons"]), ("BURNOUT_ACTIVE", ["BURNOUT_ACTIVE", "TRAVELING"]))

    def test_snapshot_exposes_why_actions_are_blocked(self):
        from players.services import get_snapshot
        self.assertNotIn("TRAVELING", get_snapshot(self.player.pk).work_blocked_by)
        self.travel()
        s = get_snapshot(self.player.pk)
        self.assertIn("TRAVELING", s.work_blocked_by)
        self.assertNotIn("TRAVELING", s.study_blocked_by + s.leisure_blocked_by)
        self.clk.advance(days=2)
        self.assertNotIn("TRAVELING", get_snapshot(self.player.pk).work_blocked_by)

    def test_human_and_bot_take_the_same_path(self):
        bot = self.new_player("bot_09")
        self.go(self.far(), bot)
        self.travel()
        self.assertEqual(self.act(Action.WORK, player=bot).code, self.act(Action.WORK).code)
        self.assertEqual(self.act(Action.WORK).code, "TRAVELING")

    def test_another_player_traveling_does_not_block_me(self):
        other = self.new_player("other")
        self.go(self.far(), other)
        self.assertTrue(self.act(Action.WORK).ok)

    def test_block_provider_names_are_unique(self):
        with self.assertRaises(ValueError):
            hooks.register_block_provider("travel", lambda *a: None)


class TravelBalanceTests(SimpleTestCase):
    def test_defaults(self):
        b = get_travel_balance()
        self.assertEqual(b.presence_dependent_by_default, {"work": True, "study": False, "leisure": False})
        self.assertEqual(b.travel_blocking_states, ())

    def test_invalid_overrides_fail_loudly(self):
        for overrides in ({"nope": 1}, {"travel_blocking_states": ["asleep"]}, {"presence_dependent_by_default": {"fly": True}}):
            with override_settings(POLIS_TRAVEL_BALANCE=overrides):
                with self.assertRaises(ImproperlyConfigured, msg=str(overrides)):
                    get_travel_balance()
