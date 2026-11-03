"""Observadores de ação do Action Registry: só em execução bem-sucedida, isolados, determinísticos, sem alterar o resultado."""
import logging

from players import registry
from players.models import Player
from travel.tests.base import TravelTestCase


class ActionObserverTests(TravelTestCase):
    def setUp(self):
        super().setUp()
        self.saved = dict(registry._observers)
        registry.clear_action_observers()
        self.addCleanup(self._restore)
        self.calls = []

    def _restore(self):
        registry.clear_action_observers()
        registry._observers.update(self.saved)

    def watch(self, name="obs"):
        registry.register_action_observer(name, lambda pid, aid, res: self.calls.append((name, pid, aid, res.ok)))

    def test_called_after_a_successful_action_with_player_action_and_result(self):
        self.watch()
        self.assertTrue(registry.execute_action(self.player.pk, "leisure").ok)
        self.assertEqual(self.calls, [("obs", self.player.pk, "leisure", True)])

    def test_not_called_for_refusals(self):
        self.watch()
        self.assertEqual(registry.execute_action(self.player.pk, "fly").code, "UNKNOWN_ACTION")
        self.assertFalse(registry.execute_action(self.player.pk, "leisure", foo=1).ok)
        self.assertEqual(registry.execute_action(self.player.pk, "work", 5).code, "TARGET_NOT_ALLOWED")
        Player.objects.filter(pk=self.player.pk).update(energy=0)
        self.assertFalse(registry.execute_action(self.player.pk, "leisure").ok)        # recusa do serviço dono (energia)
        self.assertEqual(self.calls, [])

    def test_deterministic_order_by_name(self):
        for n in ("b", "c", "a"):
            self.watch(n)
        registry.execute_action(self.player.pk, "leisure")
        self.assertEqual([c[0] for c in self.calls], ["a", "b", "c"])

    def test_duplicate_name_is_an_error_and_unregister_works(self):
        self.watch()
        with self.assertRaises(ValueError):
            self.watch()
        registry.unregister_action_observer("obs")
        registry.execute_action(self.player.pk, "leisure")
        self.assertEqual(self.calls, [])

    def test_failing_observer_never_revokes_the_action_and_is_logged(self):
        def boom(pid, aid, res):
            Player.objects.filter(pk=pid).update(health=1)          # escrita do observador: deve ser desfeita com o savepoint
            raise RuntimeError("falhou")
        registry.register_action_observer("a_boom", boom)
        self.watch("z_ok")
        with self.assertLogs("players.registry", level=logging.ERROR) as cm:
            res = registry.execute_action(self.player.pk, "leisure")
        self.assertTrue(res.ok)
        self.assertIn("a_boom", cm.output[0])
        self.assertEqual([c[0] for c in self.calls], ["z_ok"])      # o seguinte ainda roda
        after = Player.objects.get(pk=self.player.pk)
        self.assertNotEqual(after.health, 1)                         # escrita do observador revertida (savepoint)
        self.assertEqual(after.energy, res.detail["energy"])         # a ação em si ficou aplicada (Lazer gastou Energia)
        self.assertLess(after.energy, 100)

    def test_action_effects_are_those_of_the_service_regardless_of_observers(self):
        a = self.new_player("a")
        b = self.new_player("b")
        self.watch()
        registry.execute_action(a.pk, "leisure")
        registry.unregister_action_observer("obs")
        registry.execute_action(b.pk, "leisure")
        ea, eb = Player.objects.get(pk=a.pk), Player.objects.get(pk=b.pk)
        self.assertEqual((ea.energy, ea.burnout, ea.processed_until), (eb.energy, eb.burnout, eb.processed_until))
