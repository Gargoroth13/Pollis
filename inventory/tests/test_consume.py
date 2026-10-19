"""Consumir (05 §5-6; 04 §15-16): item → efeito → quantidade reduzida; efeito de Comida substitui o anterior; sem valor inventado."""
from decimal import Decimal

from inventory import params, services
from inventory.models import InventoryMovement
from players import registry
from players.models import QolEffect

from .base import InventoryTestCase

D = Decimal


def food_effect(player):
    return QolEffect.objects.filter(player=player, category="food").first()


class ConsumeTests(InventoryTestCase):
    def test_consuming_reduces_the_item_raises_nutrition_and_applies_the_food_effect(self):
        self.give(self.player, "chocolate", 3)
        self.set_state(nutrition=40)
        res = services.consume(self.player.pk, "chocolate")
        self.assertTrue(res.ok, res)
        self.assertEqual(self.qty(self.player, "chocolate"), 2)
        self.assertEqual(self.state().nutrition, 55)                          # chocolate: nível "pouca" = 15 [PROV]
        effect = food_effect(self.player)
        self.assertEqual((effect.amount, effect.source, effect.expires_at - effect.starts_at),
                         (D("0.05"), "food:chocolate", params.FOOD_EFFECT_DURATION_SECONDS))
        last = InventoryMovement.objects.order_by("id").last()
        self.assertEqual((last.operation, last.delta, last.quantity_after, last.origin, last.destination, last.reference_kind),
                         ("consumption", -1, 2, f"player:{self.player.pk}", "consumption", "consumption"))

    def test_the_gain_is_explained_with_the_limit_that_restricted_it(self):
        self.give(self.player, "pasta", 2)
        self.set_state(nutrition=D(80))
        res = services.consume(self.player.pk, "pasta")                       # massa "bastante" = 50, mas só cabem 20
        gain = res.detail["nutrition_gain"]
        self.assertEqual((gain.value, res.detail["nutrition_applied"], res.detail["nutrition"]), (D(20), D(20), D(100)))
        self.assertEqual(gain.step("food_nutrition").amount, D(50))
        self.assertEqual(gain.restricted_by, ("nutrition_room",))
        self.set_state(nutrition=D(10))
        free = services.consume(self.player.pk, "pasta").detail["nutrition_gain"]
        self.assertEqual((free.value, free.restricted_by), (D(50), ()))

    def test_a_debuff_food_has_a_negative_effect_and_replaces_a_buff(self):
        self.give(self.player, "chocolate", 1)
        self.give(self.player, "sun_dried_meat", 1)
        services.consume(self.player.pk, "chocolate")
        self.assertEqual(food_effect(self.player).amount, D("0.05"))
        services.consume(self.player.pk, "sun_dried_meat")                     # 04 §4.4: o novo substitui o anterior
        self.assertEqual(QolEffect.objects.filter(player=self.player, category="food").count(), 1)
        self.assertEqual(food_effect(self.player).amount, D("-0.05"))
        c = self.snap().qol_current
        self.assertEqual(c.step("effect:food").amount, D("-0.05"))

    def test_a_food_without_qol_effect_leaves_the_current_effect_alone(self):
        self.give(self.player, "chocolate", 1)
        self.give(self.player, "bread", 1)                                    # Pão: consumível, sem efeito de QoL (Q5)
        services.consume(self.player.pk, "chocolate")
        res = services.consume(self.player.pk, "bread")
        self.assertTrue(res.ok)
        self.assertIsNone(res.detail["qol_effect"])
        self.assertEqual(food_effect(self.player).source, "food:chocolate")

    def test_two_consumptions_in_the_same_instant_are_two_separate_events(self):
        self.give(self.player, "bread", 2)
        self.assertTrue(services.consume(self.player.pk, "bread").ok)
        self.assertTrue(services.consume(self.player.pk, "bread").ok)
        self.assertEqual(self.qty(self.player, "bread"), 0)
        keys = list(InventoryMovement.objects.filter(operation="consumption").values_list("key", flat=True))
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(services.consume(self.player.pk, "bread").code, "NOT_IN_INVENTORY")

    def test_the_nutrition_decay_up_to_now_is_applied_before_the_gain(self):
        self.give(self.player, "pasta", 1)
        self.clk.advance(seconds=3600)                                        # 6 ciclos × 0,5 = −3 → 97
        res = services.consume(self.player.pk, "pasta")
        self.assertEqual((res.detail["nutrition_gain"].value, res.detail["nutrition"]), (D(3), D(100)))


class ConsumeRefusalTests(InventoryTestCase):
    def test_refusals_leave_everything_unchanged(self):
        self.give(self.player, "iron", 2)
        self.give(self.player, "chocolate", 1)
        self.set_state(nutrition=40)
        self.unspecify_food("chocolate")
        before = self.world()
        nutrition = self.state().nutrition
        self.assertRefused(services.consume(self.player.pk, "no_such"), "UNKNOWN_PRODUCT")
        self.assertRefused(services.consume(self.player.pk, "iron"), "NO_CONSUMPTION_EFFECT")      # só alimento tem efeito definido
        self.assertRefused(services.consume(self.player.pk, "chocolate"), "UNSPECIFIED_DESIGN_VALUE",
                           missing=["nutrition_amount", "qol_intensity"])
        self.assertRefused(services.consume(self.player.pk, "juice"), "NOT_IN_INVENTORY")
        self.assertRefused(services.consume(10 ** 9, "bread"), "PLAYER_NOT_FOUND")
        self.assertEqual(self.world(), before)
        self.assertEqual((self.state().nutrition, food_effect(self.player)), (nutrition, None))

    def test_another_players_item_cannot_be_consumed(self):
        self.give(self.other, "bread", 1)
        self.assertRefused(services.consume(self.player.pk, "bread"), "NOT_IN_INVENTORY")
        self.assertEqual(self.qty(self.other, "bread"), 1)


class ConsumeThroughTheRegistryTests(InventoryTestCase):
    def test_the_registry_availability_and_preview_use_the_same_rules_as_the_execution(self):
        self.give(self.player, "chocolate", 1)
        self.set_state(nutrition=D(90))
        general = {a.action_id: a for a in registry.available_actions(self.player.pk)}
        self.assertTrue(general["consume"].available and general["consume"].target_required)
        ok = registry.check_action(self.player.pk, "consume", "chocolate")
        self.assertEqual((ok.available, ok.target_validated), (True, True))
        self.assertEqual(ok.preview["nutrition_gain"].value, D(10))                  # 15 limitado ao espaço (10)
        self.assertEqual(ok.preview["nutrition_gain"].restricted_by, ("nutrition_room",))
        self.assertEqual(ok.preview["qol_effect"]["amount"], D("0.05"))
        for target, code in (("no_such", "UNKNOWN_PRODUCT"), ("iron", "NO_CONSUMPTION_EFFECT"), ("juice", "NOT_IN_INVENTORY")):
            c = registry.check_action(self.player.pk, "consume", target)
            self.assertEqual((c.available, c.code), (False, code))
        res = registry.execute_action(self.player.pk, "consume", "chocolate")
        self.assertEqual((res.ok, res.detail["nutrition_gain"].value), (True, ok.preview["nutrition_gain"].value))

    def test_registry_target_rules(self):
        self.assertEqual(registry.execute_action(self.player.pk, "consume").code, "TARGET_REQUIRED")
        for bad in (5, ["bread"], "", "x" * 65, None):
            if bad is None:
                continue
            self.assertEqual(registry.execute_action(self.player.pk, "consume", bad).code, "INVALID_PARAMS", bad)
        self.assertEqual(registry.execute_action(self.player.pk, "consume", "bread", amount=3).code, "INVALID_PARAMS")

    def test_every_real_refusal_is_a_declared_requirement(self):
        declared = set(registry.get_descriptor("consume").requirements)
        self.give(self.player, "chocolate", 1)
        self.unspecify_food("chocolate")
        seen = set()
        for target in ("no_such", "iron", "chocolate", "juice"):
            seen.add(registry.check_action(self.player.pk, "consume", target).code)
        self.assertEqual(seen, declared)
