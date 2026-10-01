from players import qol
from players.rules import Action
from players.services import EffectSpec, apply_temporary_effect, change_health, perform_action

from .base import D, HOUR, PlayerTestCase


class QolLayersTests(PlayerTestCase):
    def test_base_is_half_plus_structural_modifiers(self):
        self.assertEqual(self.snap().qol_base.value, D("0.5"))
        qol.register_qol_base_provider("housing", lambda p, a: D("0.12"))
        b = self.snap().qol_base
        self.assertEqual((b.value, b.step("housing").amount), (D("0.62"), D("0.12")))

    def test_provider_order_is_deterministic_and_names_are_validated(self):
        qol.register_qol_base_provider("zeta", lambda p, a: D("0.01"))
        qol.register_qol_base_provider("alpha", lambda p, a: D("0.02"))
        self.assertEqual([s.key for s in self.snap().qol_base.steps], ["baseline", "alpha", "zeta"])
        for bad in ("burnout", "baseline", "effect:x", "alpha"):
            with self.assertRaises(ValueError):
                qol.register_qol_base_provider(bad, lambda p, a: None)

    def test_burnout_penalty_applies_to_effective_base_only_while_active(self):
        before = self.snap()
        self.set_state(burnout=100, burnout_active=True)
        during = self.snap()
        self.assertEqual(during.qol_base_effective.value, before.qol_base_effective.value - D("0.1"))
        self.assertEqual(during.qol_base.value, before.qol_base.value)    # a Base ESTRUTURAL não é reescrita (§7.3)
        self.set_state(burnout=50, burnout_active=False)
        self.assertEqual(self.snap().qol_base_effective.value, before.qol_base_effective.value)  # volta exatamente

    def test_current_is_effective_plus_effects_minus_critical_debuff(self):
        self.set_state(burnout=100, burnout_active=True)
        apply_temporary_effect(self.player.pk, "food", "food:x", D("0.2"), HOUR)
        change_health(self.player.pk, -85, "t")                           # 15 => Saúde Crítica
        c = self.snap().qol_current
        self.assertEqual([s.key for s in c.steps], ["qol_base_effective", "effect:food", "critical_health"])
        self.assertEqual(c.value, D("0.5") - D("0.1") + D("0.2") - D("0.1"))

    def test_there_is_no_ceiling_or_floor(self):
        """O 04 não define escala: QoL > 1,00 dá bônus (§2.3) e não é truncada."""
        qol.register_qol_base_provider("big", lambda p, a: D("3"))
        self.assertEqual(self.snap().qol_base.value, D("3.5"))
        self.assertEqual(self.snap().qol_current.restricted_by, ())

    def test_current_nests_effective_which_nests_structural(self):
        c = self.snap().qol_current
        eff = c.steps[0].detail
        self.assertEqual(eff.steps[0].detail.step("baseline").amount, D("0.5"))   # hierarquia (20.6)
        self.assertEqual(c.computed_at, self.clk.now())                           # 20.9


class EffectCategoryTests(PlayerTestCase):
    """04 §4.4: no máximo UM efeito por categoria; o novo SUBSTITUI o anterior; categorias diferentes coexistem."""

    def effects(self):
        return [s.key for s in self.snap().qol_current.steps if s.key.startswith("effect:")]

    def test_same_category_replaces_instead_of_stacking(self):
        apply_temporary_effect(self.player.pk, "food", "food:chocolate", D("0.10"), HOUR)
        apply_temporary_effect(self.player.pk, "food", "food:suco", D("0.04"), HOUR)
        c = self.snap().qol_current
        self.assertEqual(c.step("effect:food").amount, D("0.04"))                  # só o novo
        self.assertEqual(c.value, D("0.54"))                                       # não 0,64
        self.assertEqual(self.effects(), ["effect:food"])

    def test_replacement_resets_the_duration(self):
        apply_temporary_effect(self.player.pk, "food", "a", D("0.1"), HOUR)
        self.clk.advance(seconds=HOUR - 600)
        apply_temporary_effect(self.player.pk, "food", "b", D("0.1"), HOUR)
        self.clk.advance(seconds=HOUR - 1)
        self.assertEqual(self.effects(), ["effect:food"])                          # novo prazo, não o do antigo

    def test_different_categories_coexist(self):
        apply_temporary_effect(self.player.pk, "food", "f", D("0.1"), HOUR)
        apply_temporary_effect(self.player.pk, "leisure", "l", D("0.2"), HOUR)
        apply_temporary_effect(self.player.pk, "services", "s", D("0.05"), HOUR)
        self.assertEqual(self.effects(), ["effect:food", "effect:leisure", "effect:services"])
        self.assertEqual(self.snap().qol_current.value, D("0.5") + D("0.35"))

    def test_a_debuff_in_the_same_category_replaces_a_buff(self):
        """04 §18: alimentos podem dar efeito negativo; a categoria Comida tem um único espaço."""
        apply_temporary_effect(self.player.pk, "food", "food:ice_cream", D("0.1"), HOUR)
        apply_temporary_effect(self.player.pk, "food", "food:carne_de_sol", D("-0.05"), HOUR)
        self.assertEqual(self.snap().qol_current.step("effect:food").amount, D("-0.05"))

    def test_window_is_start_inclusive_expiry_exclusive_and_needs_no_tick(self):
        apply_temporary_effect(self.player.pk, "leisure", "l", D("0.2"), 2 * HOUR)
        self.assertEqual(self.effects(), ["effect:leisure"])
        self.clk.advance(seconds=2 * HOUR - 1)
        self.assertEqual(self.effects(), ["effect:leisure"])
        self.clk.advance(seconds=1)
        self.assertEqual(self.effects(), [])                                       # expirou sozinho (lazy)

    def test_effects_never_change_the_structural_base(self):
        apply_temporary_effect(self.player.pk, "food", "f", D("0.3"), HOUR)
        s = self.snap()
        self.assertEqual((s.qol_base.value, s.qol_base_effective.value), (D("0.5"), D("0.5")))

    def test_invalid_duration_refused(self):
        self.assertEqual(apply_temporary_effect(self.player.pk, "food", "x", 1, 0).code, "INVALID_DURATION")

    def test_leisure_action_applies_the_leisure_category_effect(self):
        spec = EffectSpec("leisure:walk", D("0.08"), 2 * HOUR)
        perform_action(self.player.pk, Action.LEISURE, effect=spec)
        self.assertEqual(self.snap().qol_current.step("effect:leisure").amount, D("0.08"))
        perform_action(self.player.pk, Action.LEISURE, effect=EffectSpec("leisure:walk", D("0.08"), 2 * HOUR))
        self.assertEqual(self.effects(), ["effect:leisure"])                       # não acumula (04 §19)
        self.assertEqual(self.snap().qol_current.value, D("0.58"))

    def test_only_leisure_carries_its_own_effect(self):
        with self.assertRaises(ValueError):
            perform_action(self.player.pk, Action.WORK, effect=EffectSpec("x", D("0.1"), HOUR))
