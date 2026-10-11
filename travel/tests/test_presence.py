from django.test import SimpleTestCase

from players import hooks
from players.actions import Action
from players.hooks import ActivityContext
from players.services import perform_action
from skills.models import PlayerSkill
from travel import rules

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

    def test_study_is_blocked_while_traveling(self):
        """Decisão do GD (2026-10-07): Estudo exige presença."""
        self.travel()
        r = self.act(Action.STUDY)
        self.assertEqual((r.ok, r.code), (False, "TRAVELING"))

    def test_leisure_is_not_blocked_while_traveling(self):
        """Decisão do GD: Lazer não exige presença."""
        self.travel()
        self.assertTrue(self.act(Action.LEISURE).ok)

    def test_blocked_study_costs_no_energy_and_grants_no_skills(self):
        self.travel()
        before = {s.skill: s.level for s in PlayerSkill.objects.filter(player=self.player)}
        self.act(Action.STUDY)
        self.assertEqual(self.state().energy, 100)
        self.assertEqual({s.skill: s.level for s in PlayerSkill.objects.filter(player=self.player)}, before)

    def test_presence_check_comes_before_energy(self):
        """Bloqueio de presença vem ANTES de energia: sem energia E viajando, o motivo de presença também aparece, e nada é gasto."""
        self.travel()
        self.set_state(energy=0)
        r = perform_action(self.player.pk, Action.WORK)
        self.assertEqual(r.ok, False)
        self.assertIn("TRAVELING", r.detail["reasons"])
        self.assertEqual(self.state().energy, 0)

    def test_a_presence_free_activity_cannot_contradict_the_fixed_rule_of_work(self):
        """Regra fixa: Trabalho/Estudo exigem; uma atividade não pode declarar o contrário (erro, não escolha silenciosa)."""
        self.travel()
        with self.assertRaises(ValueError):
            self.act(Action.WORK, activity=ActivityContext(requires_presence=False))
        with self.assertRaises(ValueError):
            self.act(Action.STUDY, activity=ActivityContext(requires_presence=False))

    def test_a_presence_requiring_activity_cannot_contradict_the_fixed_rule_of_leisure(self):
        self.travel()
        with self.assertRaises(ValueError):
            self.act(Action.LEISURE, activity=ActivityContext(requires_presence=True))

    def test_declaring_the_same_as_the_rule_is_accepted(self):
        self.travel()
        self.assertEqual(self.act(Action.WORK, activity=ActivityContext(requires_presence=True)).code, "TRAVELING")
        self.assertTrue(self.act(Action.LEISURE, activity=ActivityContext(requires_presence=False)).ok)

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
        self.assertIn("TRAVELING", s.study_blocked_by)
        self.assertNotIn("TRAVELING", s.leisure_blocked_by)
        self.clk.advance(days=2)
        s = get_snapshot(self.player.pk)
        self.assertNotIn("TRAVELING", s.work_blocked_by + s.study_blocked_by)

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


class PresenceRuleTests(SimpleTestCase):
    """Regra pura: tabela fixa por ação; ação sem regra fixa exige declaração da atividade."""

    def test_fixed_table(self):
        self.assertEqual(rules.PRESENCE_BY_ACTION, {"work": True, "study": True, "leisure": False, "treatment": False})
        self.assertTrue(rules.requires_presence(Action.WORK, None))
        self.assertTrue(rules.requires_presence(Action.STUDY, None))
        self.assertFalse(rules.requires_presence(Action.LEISURE, None))

    def test_an_action_outside_the_table_needs_the_activity_to_declare(self):
        class Other:
            value = "craft"
        with self.assertRaises(ValueError):
            rules.requires_presence(Other, None)
        with self.assertRaises(ValueError):
            rules.requires_presence(Other, ActivityContext())
        self.assertTrue(rules.requires_presence(Other, ActivityContext(requires_presence=True)))
        self.assertFalse(rules.requires_presence(Other, ActivityContext(requires_presence=False)))

    def test_treatment_is_already_registered_as_not_requiring_presence(self):
        """Tratamento ainda não é uma Action (depende de dinheiro), mas a regra já existe para quando for."""
        class Treatment:
            value = "treatment"
        self.assertFalse(rules.requires_presence(Treatment, None))
        with self.assertRaises(ValueError):
            rules.requires_presence(Treatment, ActivityContext(requires_presence=True))
