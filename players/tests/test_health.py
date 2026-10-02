import random

from django.test import override_settings

from players import rules
from players.rules import Action
from players.services import change_health, perform_action

from .base import CYCLE, D, HOUR, PlayerTestCase

HOSPITAL = 6 * HOUR  # hospitalization_duration_seconds [PROV]


class HealthCycleTests(PlayerTestCase):
    """04 §10: variação por ciclo (10 min) = Recuperação Regional + 5 - Penalidades."""

    def test_base_recovery_is_five_per_cycle(self):
        self.set_state(health=50)
        self.clk.advance(seconds=CYCLE)
        self.assertEqual(self.state().health, 55)

    def test_cycle_uses_the_state_at_the_START_of_the_cycle(self):
        """
        04 §23: 'estado no início do período -> calcula Saúde'. A Nutrição decai no mesmo ciclo,
        mas a penalidade usa a do início (100 => penalidade 0): se usasse a nova (99,5) daria 54,96.
        """
        self.set_state(health=50)
        self.clk.advance(seconds=CYCLE)
        s = self.state()
        self.assertEqual((s.health, s.nutrition), (55, D("99.5")))

    def test_low_nutrition_adds_a_penalty_and_can_make_it_negative(self):
        """04 §17. Penalidade calibrável: padrão 8 × (1 - nutrição/100)."""
        for nutrition, expected in ((100, 5), (50, 1), (0, -3)):
            c = self.snap_with(nutrition=nutrition)
            self.assertEqual(c.value, expected, nutrition)
            self.assertEqual(c.step("penalty:nutrition").amount, -D(8) * (1 - D(nutrition) / 100))

    def snap_with(self, **fields):
        self.set_state(**fields)
        return self.snap().health_change_per_cycle

    def test_regional_recovery_component_is_zero_until_a_health_system_registers(self):
        c = self.snap().health_change_per_cycle
        self.assertEqual([s.key for s in c.steps], ["base_recovery", "regional_recovery", "penalty:nutrition"])
        self.assertEqual(c.step("regional_recovery").amount, 0)
        rules.register_regional_recovery_provider("hospital", lambda p, at: D("1.5"))
        self.assertEqual(self.snap().health_change_per_cycle.value, D("6.5"))

    def test_health_is_clamped_to_0_100(self):
        self.set_state(health=98)
        self.clk.advance(seconds=CYCLE)
        self.assertEqual(self.state().health, 100)
        change_health(self.player.pk, -250, "t")
        self.assertEqual(self.state().health, 0)

    def test_starving_player_declines_to_hospitalization(self):
        self.set_state(nutrition=0, health=40)
        self.clk.advance(seconds=14 * CYCLE)                    # -3 por ciclo: 40 -> 0 em 14 ciclos
        s = self.state()
        self.assertEqual(s.health, 0)
        self.assertTrue(s.health_critical)
        self.assertIsNotNone(s.hospitalized_until)


class CriticalHealthTests(PlayerTestCase):
    """04 §12: Saúde <= 20 entra; Saúde > 30 sai."""

    def critical(self):
        return self.state().health_critical

    def test_enters_at_20_inclusive(self):
        change_health(self.player.pk, -79, "t")                 # 21
        self.assertFalse(self.critical())
        change_health(self.player.pk, -1, "t")                  # 20
        self.assertTrue(self.critical())

    def test_stays_critical_through_30_and_exits_above_30(self):
        change_health(self.player.pk, -80, "t")                 # 20
        change_health(self.player.pk, 10, "t")                  # 30
        self.assertTrue(self.critical())
        change_health(self.player.pk, D("0.000001"), "t")       # 30,000001
        self.assertFalse(self.critical())

    def test_does_not_flip_inside_the_band(self):
        for _ in range(4):                                       # nunca crítica: oscila 21..30
            change_health(self.player.pk, 25 - self.state().health, "t")
            change_health(self.player.pk, 30 - self.state().health, "t")
            self.assertFalse(self.critical())
        change_health(self.player.pk, -100, "t")
        for _ in range(4):                                       # crítica: oscila 21..30 e continua
            change_health(self.player.pk, 22 - self.state().health, "t")
            change_health(self.player.pk, 30 - self.state().health, "t")
            self.assertTrue(self.critical())

    def test_matches_independent_reference_model_on_random_walks(self):
        rng = random.Random(20261001)
        for _ in range(5):
            ref, health = False, self.state().health
            for _ in range(60):
                health = max(D(0), min(D(100), health + D(rng.randint(-30, 30))))
                if not ref and health <= 20:
                    ref = True
                elif ref and health > 30:
                    ref = False
                change_health(self.player.pk, health - self.state().health, "t")
                self.assertEqual(self.critical(), ref, f"saúde={health}")

    def test_blocks_work_but_not_study_or_leisure(self):
        change_health(self.player.pk, -85, "t")                  # 15
        r = perform_action(self.player.pk, Action.WORK)
        self.assertEqual((r.ok, r.code), (False, "HEALTH_CRITICAL"))
        self.assertTrue(perform_action(self.player.pk, Action.STUDY).ok)
        self.assertTrue(perform_action(self.player.pk, Action.LEISURE).ok)

    def test_debuffs_qol_current_but_not_the_base(self):
        before = self.snap()
        change_health(self.player.pk, -85, "t")
        after = self.snap()
        self.assertEqual(after.qol_current.step("critical_health").amount, D("-0.1"))
        self.assertEqual(after.qol_current.value, before.qol_current.value - D("0.1"))
        self.assertEqual(after.qol_base_effective.value, before.qol_base_effective.value)

    def test_exits_naturally_by_recovery(self):
        change_health(self.player.pk, -90, "t")                  # 10
        self.clk.advance(seconds=4 * CYCLE)                      # 10 + 4×5 = 30: ainda crítica
        self.assertTrue(self.critical())
        self.clk.advance(seconds=CYCLE)                          # 35
        self.assertFalse(self.critical())


class HospitalizationTests(PlayerTestCase):
    """04 §14: Saúde = 0 => hospitalização, estado DISTINTO da Saúde Crítica."""

    def test_enters_at_zero_health_and_is_distinct_from_critical(self):
        change_health(self.player.pk, -100, "t")
        s = self.snap()
        self.assertTrue(s.hospitalized and s.health_critical)
        change_health(self.player.pk, 0, "t")
        self.set_state(health=10)                                # crítica, mas não hospitalizada de novo
        self.assertTrue(self.snap().health_critical)

    def test_crossing_into_critical_alone_does_not_hospitalize(self):
        change_health(self.player.pk, -85, "t")                  # 15
        s = self.snap()
        self.assertTrue(s.health_critical)
        self.assertFalse(s.hospitalized)

    def test_blocks_work_and_reports_reasons_in_fixed_order(self):
        change_health(self.player.pk, -100, "t")
        r = perform_action(self.player.pk, Action.WORK)
        self.assertEqual((r.code, r.detail["reasons"]), ("HOSPITALIZED", ["HOSPITALIZED", "HEALTH_CRITICAL"]))

    def test_blocks_work_study_and_leisure(self):
        """04 §14: enquanto hospitalizado, o jogador não pode Trabalhar, Estudar nem fazer Lazer."""
        change_health(self.player.pk, -100, "t")
        before = self.state().energy
        for action in (Action.WORK, Action.STUDY, Action.LEISURE):
            r = perform_action(self.player.pk, action)
            self.assertEqual((r.ok, r.code), (False, "HOSPITALIZED"), action)
        self.assertEqual(self.state().energy, before)                       # recusa não custa Energia
        s = self.snap()
        self.assertEqual((s.study_blocked_by, s.leisure_blocked_by), (["HOSPITALIZED"], ["HOSPITALIZED"]))
        self.assertEqual(s.work_blocked_by[0], "HOSPITALIZED")

    def test_everything_is_released_when_the_hospitalization_ends(self):
        change_health(self.player.pk, -100, "t")
        self.clk.advance(seconds=HOSPITAL)
        s = self.snap()
        self.assertEqual((s.work_blocked_by, s.study_blocked_by, s.leisure_blocked_by), ([], [], []))
        for action in (Action.WORK, Action.STUDY, Action.LEISURE):
            self.assertTrue(perform_action(self.player.pk, action).ok, action)

    @override_settings(POLIS_BALANCE={"hospitalization_blocked_actions": ["work"]})
    def test_the_blocked_set_is_configurable(self):
        change_health(self.player.pk, -100, "t")
        self.assertEqual(perform_action(self.player.pk, Action.WORK).code, "HOSPITALIZED")
        self.assertTrue(perform_action(self.player.pk, Action.STUDY).ok)
        self.assertTrue(perform_action(self.player.pk, Action.LEISURE).ok)

    def test_recovers_by_normal_rules_and_ends_after_the_duration(self):
        change_health(self.player.pk, -100, "t")
        self.clk.advance(seconds=HOSPITAL - 1)
        self.assertTrue(self.snap().hospitalized)
        self.clk.advance(seconds=1)
        s = self.snap()
        self.assertFalse(s.hospitalized)
        self.assertGreater(s.health, 30)                         # 36 ciclos × 5, saiu da crítica pela regra normal
        self.assertFalse(s.health_critical)

    @override_settings(POLIS_BALANCE={"hospitalization_duration_seconds": 1800})
    def test_duration_is_configurable(self):
        change_health(self.player.pk, -100, "t")
        self.clk.advance(seconds=1799)
        self.assertTrue(self.snap().hospitalized)
        self.clk.advance(seconds=1)
        self.assertFalse(self.snap().hospitalized)
