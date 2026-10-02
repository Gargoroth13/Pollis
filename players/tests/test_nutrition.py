from players.rules import Action
from players.services import EffectSpec, consume_food, perform_action

from .base import CYCLE, D, HOUR, PlayerTestCase


class NutritionTests(PlayerTestCase):
    def test_changes_over_time_lazily(self):
        self.clk.advance(seconds=HOUR)                           # 6 ciclos × 0,5 [PROV]
        self.assertEqual(self.state().nutrition, 97)

    def test_floor_is_zero(self):
        self.clk.advance(days=30)
        self.assertEqual(self.state().nutrition, 0)

    def test_food_raises_nutrition_up_to_100(self):
        self.set_state(nutrition=40)
        consume_food(self.player.pk, 25)
        self.assertEqual(self.state().nutrition, 65)
        consume_food(self.player.pk, 999)
        self.assertEqual(self.state().nutrition, 100)

    def test_negative_gain_is_refused(self):
        self.assertEqual(consume_food(self.player.pk, -1).code, "INVALID_AMOUNT")

    def test_food_effect_uses_the_food_category_and_replaces_the_previous_one(self):
        consume_food(self.player.pk, 10, effect=EffectSpec("food:chocolate", D("0.1"), HOUR))
        consume_food(self.player.pk, 10, effect=EffectSpec("food:suco", D("0.04"), HOUR))
        c = self.snap().qol_current
        self.assertEqual(c.step("effect:food").amount, D("0.04"))
        self.assertEqual(len([s for s in c.steps if s.key == "effect:food"]), 1)

    def test_manual_food_and_leisure_effects_are_independent_categories(self):
        consume_food(self.player.pk, 10, effect=EffectSpec("food:x", D("0.1"), HOUR))
        perform_action(self.player.pk, Action.LEISURE, effect=EffectSpec("leisure:y", D("0.2"), HOUR))
        keys = [s.key for s in self.snap().qol_current.steps]
        self.assertTrue("effect:food" in keys and "effect:leisure" in keys)
