from core.breakdown import StepKind
from players.rules import Action
from players.services import perform_action

from .base import CYCLE, D, HOUR, PlayerTestCase


class InitialStateTests(PlayerTestCase):
    def test_initial_state_matches_04_section_24(self):
        s = self.snap()
        self.assertEqual((s.energy, s.health, s.nutrition, s.burnout), (100, 100, 100, 0))
        self.assertEqual((s.burnout_active, s.health_critical, s.hospitalized), (False, False, False))
        self.assertEqual(s.qol_current.value, s.qol_base.value)          # "QoL Atual inicial = QoL Base inicial"
        self.assertEqual(s.qol_base.value, D("0.5"))                     # 0,50 + modificadores estruturais


class FixedActionCostTests(PlayerTestCase):
    def test_each_action_has_a_fixed_cost_the_player_cannot_choose(self):
        for action, cost in ((Action.WORK, 20), (Action.STUDY, 10), (Action.LEISURE, 10)):
            before = self.state().energy
            r = perform_action(self.player.pk, action)
            self.assertTrue(r.ok, action)
            self.assertEqual((r.detail["energy_spent"], self.state().energy), (cost, before - cost), action)

    def test_action_without_enough_energy_is_refused_and_changes_nothing(self):
        self.set_state(energy=15)
        r = perform_action(self.player.pk, Action.WORK)                # custa 20
        self.assertEqual((r.ok, r.code), (False, "INSUFFICIENT_ENERGY"))
        s = self.state()
        self.assertEqual((s.energy, s.burnout, s.last_work_at), (15, 0, None))
        self.assertTrue(perform_action(self.player.pk, Action.STUDY).ok)   # custa 10: cabe
        self.assertEqual(self.state().energy, 5)
        self.assertFalse(perform_action(self.player.pk, Action.STUDY).ok)  # 5 < 10

    def test_spending_the_exact_balance_is_allowed(self):
        self.set_state(energy=20)
        self.assertTrue(perform_action(self.player.pk, Action.WORK).ok)
        self.assertEqual(self.state().energy, 0)


class EnergyRegenTests(PlayerTestCase):
    def test_neutral_qol_regenerates_five_per_ten_minutes(self):
        self.neutral_qol("1.0")                                        # QoL 1,00 => modificador 0%
        self.set_state(energy=50)
        self.clk.advance(seconds=CYCLE - 1)
        self.assertEqual(self.state().energy, 50)                      # ainda não completou um ciclo
        self.clk.advance(seconds=1)
        self.assertEqual(self.state().energy, 55)
        self.clk.advance(seconds=HOUR - CYCLE)
        self.assertEqual(self.state().energy, 80)                      # 6 ciclos = 30

    def test_doc_example_qol_plus_5_percent_gives_5_25(self):
        """04 §25: 'Energia regenerada: 5,25 / 10 min; Base 5,00; QoL +5%'."""
        self.neutral_qol("1.05")
        r = self.snap().energy_regen_per_cycle
        self.assertEqual(r.value, D("5.25"))
        self.assertEqual(r.step("regen_base").amount, 5)
        self.assertEqual(r.step("qol_modifier").detail.value, D("0.05"))   # o "+5%"

    def test_bonus_is_capped_at_plus_ten_percent(self):
        self.neutral_qol("1.8")
        r = self.snap().energy_regen_per_cycle
        self.assertEqual(r.value, D("5.5"))
        self.assertEqual(r.step("qol_modifier").detail.restricted_by, ("modifier_max",))

    def test_penalty_is_capped_at_minus_ten_percent(self):
        r = self.snap().energy_regen_per_cycle                          # QoL padrão 0,50 < 1,00
        self.assertEqual(r.value, D("4.5"))
        self.assertEqual(r.step("qol_modifier").detail.restricted_by, ("modifier_min",))
        self.neutral_qol("-3")
        self.assertEqual(self.snap().energy_regen_per_cycle.value, D("4.5"))  # nem QoL absurda passa de -10%

    def test_regeneration_is_never_negative(self):
        self.assertGreaterEqual(self.snap().energy_regen_per_cycle.value, 0)

    def test_energy_never_exceeds_maximum(self):
        self.set_state(energy=98)
        self.clk.advance(days=3)
        self.assertEqual(self.state().energy, 100)

    def test_uses_qol_base_effective_not_qol_current(self):
        """04 §2.3: buffs temporários não podem oscilar a regeneração."""
        from players.services import apply_temporary_effect
        self.neutral_qol("1.0")
        apply_temporary_effect(self.player.pk, "leisure", "x", D("0.5"), HOUR)
        s = self.snap()
        self.assertEqual(s.qol_current.value, D("1.5"))
        self.assertEqual(s.energy_regen_per_cycle.value, 5)             # regeneração ignora o buff

    def test_burnout_penalty_lowers_regen_through_qol_base_effective(self):
        self.neutral_qol("1.0")
        self.set_state(burnout=100, burnout_active=True)
        self.assertEqual(self.snap().energy_regen_per_cycle.value, D("4.5"))   # 1,0-0,1=0,9 => -10%

    def test_explanation_is_structured_and_hierarchical(self):
        r = self.snap().energy_regen_per_cycle
        self.assertEqual([s.key for s in r.steps], ["regen_base", "qol_modifier", "regen_floor"])
        self.assertEqual(r.step("qol_modifier").kind, StepKind.MULTIPLY)
        modifier = r.step("qol_modifier").detail                         # QoL -> modificador
        self.assertEqual([s.key for s in modifier.steps], ["qol_delta", "sensitivity", "modifier_min", "modifier_max"])
        effective = modifier.step("qol_delta").detail                    # de onde veio a QoL
        self.assertEqual(effective.step("structural").detail.step("baseline").amount, D("0.5"))
        self.assertIsInstance(r.to_dict()["steps"][1]["detail"], dict)

    def test_lazy_catch_up_equals_cycle_by_cycle(self):
        """04 §22: acessar a cada ciclo ou só no fim dá o MESMO resultado."""
        a, b = self.player, self.new_player("b")
        for p in (a, b):
            self.set_state(p, energy=0)
        for _ in range(20):
            self.clk.advance(seconds=CYCLE)
            self.state(a)
        self.assertEqual(self.state(a).energy, self.state(b).energy)
