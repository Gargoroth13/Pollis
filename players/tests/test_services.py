from unittest import mock

from django.db import IntegrityError, transaction

from accounts.models import Usuario
from core.ticks import registry
from core.timeline import TickKind
from players.models import Player, QolEffect
from players.rules import Action
from players.services import (EffectSpec, apply_temporary_effect, change_health, consume_food, create_player,
                              get_snapshot, perform_action, sync_player)

from .base import CYCLE, D, HOUR, PlayerTestCase, T0


class CreatePlayerTests(PlayerTestCase):
    def test_initial_state(self):
        p = self.state()
        self.assertEqual((p.energy, p.health, p.nutrition, p.burnout), (100, 100, 100, 0))
        self.assertEqual((p.burnout_active, p.health_critical, p.hospitalized_until, p.last_work_at),
                         (False, False, None, None))
        self.assertEqual((p.processed_until, p.created_at_game), (T0, T0))

    def test_one_player_per_user(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_player(self.player.user)

    def test_new_player_starts_at_current_game_time_not_in_the_past(self):
        self.clk.advance(days=40)
        later = self.new_player("late")
        self.assertEqual(later.processed_until, self.clk.now())
        self.assertEqual(sync_player(later.pk).nutrition, 100)          # sem ciclos "retroativos"

    def test_player_and_bot_users_use_the_same_services(self):
        bot = create_player(Usuario.objects.create_user("bot_01"))
        self.assertTrue(perform_action(bot.pk, Action.WORK).ok)         # mesma ação para os dois (design/21)


class SyncTests(PlayerTestCase):
    def test_sync_is_idempotent(self):
        perform_action(self.player.pk, Action.WORK)
        self.clk.advance(seconds=7 * CYCLE)
        a, b = self.state(), self.state()
        self.assertEqual((a.energy, a.health, a.nutrition, a.burnout, a.processed_until),
                         (b.energy, b.health, b.nutrition, b.burnout, b.processed_until))

    def test_processing_pointer_advances_to_now(self):
        self.clk.advance(seconds=3 * CYCLE + 17)
        self.assertEqual(self.state().processed_until, self.clk.now())

    def test_snapshot_is_complete_and_explained(self):
        s = get_snapshot(self.player.pk)
        self.assertEqual((s.at, s.energy, s.burnout_active, s.health_critical, s.hospitalized), (T0, 100, False, False, False))
        for name in ("qol_base", "qol_base_effective", "qol_current", "energy_regen_per_cycle", "health_change_per_cycle"):
            explained = getattr(s, name)
            self.assertEqual(explained.computed_at, T0, name)            # 20.9
            self.assertGreaterEqual(len(explained.steps), 1, name)
        self.assertEqual((s.work_blocked_by, s.study_blocked_by, s.leisure_blocked_by), ([], [], []))

    def test_snapshot_exposes_why_actions_are_blocked(self):
        self.set_state(burnout=100, burnout_active=True)
        change_health(self.player.pk, -100, "t")
        s = self.snap()
        self.assertEqual(s.work_blocked_by, ["HOSPITALIZED", "HEALTH_CRITICAL", "BURNOUT_ACTIVE"])
        self.assertEqual(s.study_blocked_by, ["BURNOUT_ACTIVE"])


class AtomicityTests(PlayerTestCase):
    def test_failure_AFTER_writing_rolls_everything_back_in_every_service(self):
        """
        A falha ocorre depois do save(): só uma transação atômica desfaz o que já foi gravado
        (inclusive o catch-up de ciclos, que também é gravado).
        """
        real_save = Player.save

        def save_then_fail(instance, *args, **kwargs):
            real_save(instance, *args, **kwargs)
            raise RuntimeError("falha depois de gravar")

        calls = {
            "perform_action": lambda pk: perform_action(pk, Action.WORK),
            "consume_food": lambda pk: consume_food(pk, 10),
            "change_health": lambda pk: change_health(pk, -10, "t"),
            "apply_temporary_effect": lambda pk: apply_temporary_effect(pk, "food", "x", D("0.1"), HOUR),
        }
        for name, call in calls.items():
            with self.subTest(service=name):
                player = self.new_player(f"atomic_{name}")
                self.clk.advance(seconds=3 * CYCLE)                     # catch-up pendente
                before = Player.objects.get(pk=player.pk)
                with mock.patch.object(Player, "save", save_then_fail):
                    with self.assertRaises(RuntimeError):
                        call(player.pk)
                after = Player.objects.get(pk=player.pk)
                self.assertEqual(
                    (after.energy, after.health, after.nutrition, after.burnout, after.processed_until, after.last_work_at),
                    (before.energy, before.health, before.nutrition, before.burnout, before.processed_until, before.last_work_at))

    def test_effect_row_is_rolled_back_when_a_later_step_fails(self):
        before = QolEffect.objects.count()
        with mock.patch.object(Player, "save", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                consume_food(self.player.pk, 10, effect=EffectSpec("f", D("0.1"), HOUR))
        self.assertEqual(QolEffect.objects.count(), before)

    def test_refused_actions_change_nothing_about_the_outcome(self):
        self.set_state(energy=5)
        for _ in range(3):
            self.assertFalse(perform_action(self.player.pk, Action.WORK).ok)
        s = self.state()
        self.assertEqual((s.energy, s.burnout, s.last_work_at), (5, 0, None))


class CycleHandlerTests(PlayerTestCase):
    def test_single_handler_on_the_ten_minute_cycle(self):
        """A ordem interna do ciclo é regra do design (04 §23): vive em rules.advance_cycle, não em prioridades."""
        names = [r.name for r in registry.handlers_for("player", TickKind.TEN_MINUTES)]
        self.assertEqual(names, ["cycle"])
        self.assertEqual(registry.kinds_for("player"), [TickKind.TEN_MINUTES])
