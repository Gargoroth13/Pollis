"""Ligação real: toda ação bem-sucedida do Action Registry conta para o Maior tempo ativo e checa o recorde de patrimônio."""
from unittest import mock

from players import registry
from players.models import Player
from rankings import activity, wiring
from rankings.constants import Cat
from rankings.models import ActivityStreak, RankingHistorico

from .base import DAY, HOUR, T0, RankingsTestCase


class RegistryIntegrationTests(RankingsTestCase):
    def test_observers_are_registered_by_the_app(self):
        self.assertEqual(set(registry.action_observer_names()) & {wiring.OBSERVER_ACTIVITY, wiring.OBSERVER_NET_WORTH},
                         {wiring.OBSERVER_ACTIVITY, wiring.OBSERVER_NET_WORTH})

    # Esperar dias reais de jogo sem comer hospitaliza o jogador (04), então o passado da sequência é semeado por
    # `activity.record_action` com instantes anteriores e a ação real acontece AGORA, pelo registro.

    def test_successful_registry_action_extends_the_streak(self):
        self.assertTrue(registry.execute_action(self.player.pk, "leisure").ok)
        s = ActivityStreak.objects.get(player=self.player)
        self.assertEqual((s.current_start, s.last_action_at), (T0, T0))

    def test_real_action_continues_a_streak_when_the_gap_is_below_72h(self):
        activity.record_action(self.player.pk, T0 - 48 * HOUR)
        self.assertTrue(registry.execute_action(self.player.pk, "leisure").ok)
        s = ActivityStreak.objects.get(player=self.player)
        self.assertEqual((s.current_start, s.best_length), (T0 - 48 * HOUR, 48 * HOUR))
        self.assertEqual(RankingHistorico.objects.get(category=Cat.ACTIVE_TIME_RECORD.value).value, 48 * HOUR)

    def test_gap_of_72h_before_a_real_action_starts_a_new_streak(self):
        activity.record_action(self.player.pk, T0 - 72 * HOUR)
        registry.execute_action(self.player.pk, "leisure")
        s = ActivityStreak.objects.get(player=self.player)
        self.assertEqual((s.current_start, s.best_length), (T0, 0))

    def test_refused_actions_do_not_count(self):
        Player.objects.filter(pk=self.player.pk).update(energy=0)
        self.assertFalse(registry.execute_action(self.player.pk, "leisure").ok)
        self.assertFalse(registry.execute_action(self.player.pk, "fly").ok)
        self.assertFalse(ActivityStreak.objects.exists())

    def test_observer_failure_does_not_revoke_the_action(self):
        with mock.patch.object(activity, "record_action", side_effect=RuntimeError("x")):
            with self.assertLogs("players.registry", level="ERROR"):
                res = registry.execute_action(self.player.pk, "leisure")
        self.assertTrue(res.ok)
        self.assertFalse(ActivityStreak.objects.exists())
        self.assertLess(Player.objects.get(pk=self.player.pk).energy, 100)      # a ação continua aplicada

    def test_action_updates_net_worth_record_of_the_actor(self):
        self.fund(self.acct(), 6_000)
        registry.execute_action(self.player.pk, "leisure")
        r = RankingHistorico.objects.get(category=Cat.NET_WORTH_RECORD.value)
        self.assertEqual((r.entity_id, r.value), (self.player.pk, 6_000))

    def test_login_or_page_views_do_not_count(self):
        self.client.get("/rankings/")
        self.assertFalse(ActivityStreak.objects.exists())
