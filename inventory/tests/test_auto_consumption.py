"""
Auto-consumo (design/04 §16). O "acesso" que dispara o hook é qualquer processamento lazy do jogador (aqui `self.state()` =
`sync_player`). Alimentos [PROV] usados: juice 5, chocolate 15, hamburger 30, bread 30, sun_dried_meat 30 (debuff), pasta 50
(sem efeito de QoL), ice_cream e soda com ganho 0 (inelegíveis: não resolvem a fome).
"""
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test.utils import CaptureQueriesContext

from inventory import auto, services
from inventory.audit import audit_inventory
from inventory.constants import AUTO_CONSUMPTION_REFERENCE, Operation
from inventory.models import AutoConsumption, InventoryMovement
from players import registry
from players import services as player_services
from players.models import Player, QolEffect

from .base import InventoryTestCase

D = Decimal


def auto_movements(player):
    return list(InventoryMovement.objects.filter(player=player, reference_kind=AUTO_CONSUMPTION_REFERENCE).order_by("id"))


def food_effect(player):
    return QolEffect.objects.filter(player=player, category="food").first()


class AutoTestCase(InventoryTestCase):
    def enable(self, preferred=None, player=None):
        res = auto.configure((player or self.player).pk, True, preferred)
        self.assertTrue(res.ok, res)

    def hungry(self, nutrition=5, player=None):
        self.set_state(player, nutrition=D(nutrition))


class ConfigurationTests(AutoTestCase):
    def test_it_starts_disabled_and_can_be_enabled_with_a_preferred_food(self):
        self.assertEqual(auto.settings_of(self.player.pk), {"enabled": False, "preferred": None})
        self.assertTrue(auto.configure(self.player.pk, True, "pasta").ok)
        self.assertEqual(auto.settings_of(self.player.pk), {"enabled": True, "preferred": "pasta"})
        self.assertTrue(auto.configure(self.player.pk, True, None).ok)                  # o preferido é opcional e pode ser limpo
        self.assertEqual(auto.settings_of(self.player.pk), {"enabled": True, "preferred": None})
        self.assertTrue(auto.configure(self.player.pk, False, "juice").ok)
        self.assertEqual(auto.settings_of(self.player.pk), {"enabled": False, "preferred": "juice"})
        self.assertEqual(AutoConsumption.objects.filter(player=self.player).count(), 1)  # uma configuração por jogador

    def test_configuration_is_per_player(self):
        auto.configure(self.player.pk, True, "pasta")
        self.assertEqual(auto.settings_of(self.other.pk), {"enabled": False, "preferred": None})

    def test_invalid_configurations_are_refused_without_changing_anything(self):
        auto.configure(self.player.pk, True, "pasta")
        before = auto.settings_of(self.player.pk)
        for enabled, preferred, code in [
            (True, "wheat", "NO_CONSUMPTION_EFFECT"),            # não é alimento
            (True, "nothing", "UNKNOWN_PRODUCT"),
            ("yes", "pasta", "INVALID_PARAMS"),
            (1, None, "INVALID_PARAMS"),
            (True, 5, "INVALID_PARAMS"),
        ]:
            self.assertRefused(auto.configure(self.player.pk, enabled, preferred), code)
        self.unspecify_food("juice")
        self.assertRefused(auto.configure(self.player.pk, True, "juice"), "UNSPECIFIED_DESIGN_VALUE")
        self.assertRefused(auto.configure(10 ** 9, True, None), "PLAYER_NOT_FOUND")
        self.assertEqual(auto.settings_of(self.player.pk), before)

    def test_it_is_an_action_of_the_shared_registry(self):
        d = registry.get_descriptor("auto_consumption")
        self.assertEqual((d.id, d.target), ("auto_consumption", registry.TargetSpec(registry.TARGET_PARAMS, True)))
        res = registry.execute_action(self.player.pk, "auto_consumption", {"enabled": True, "preferred": "pasta"})
        self.assertTrue(res.ok, res)
        self.assertEqual(auto.settings_of(self.player.pk), {"enabled": True, "preferred": "pasta"})
        for bad in ({"enabled": True}, {"enabled": True, "preferred": None, "x": 1}, "pasta", {"enabled": "s", "preferred": None}):
            self.assertRefused(registry.execute_action(self.player.pk, "auto_consumption", bad), "INVALID_PARAMS")
        self.assertRefused(registry.execute_action(self.player.pk, "auto_consumption", {"enabled": True, "preferred": "wheat"}),
                           "NO_CONSUMPTION_EFFECT")
        check = registry.check_action(self.player.pk, "auto_consumption", {"enabled": True, "preferred": "wheat"})
        self.assertEqual((check.available, check.code), (False, "NO_CONSUMPTION_EFFECT"))


class SelectionTests(AutoTestCase):
    def test_nothing_happens_while_disabled(self):
        self.give(self.player, "chocolate", 3)
        self.hungry(5)
        self.assertEqual(self.state().nutrition, 5)
        self.assertEqual(self.qty(self.player, "chocolate"), 3)
        self.assertEqual(auto_movements(self.player), [])

    def test_the_threshold_is_strictly_below_ten(self):
        self.give(self.player, "chocolate", 3)
        self.enable()
        self.hungry(10)
        self.assertEqual(self.state().nutrition, 10)                          # 10 não é "abaixo de 10"
        self.assertEqual(self.qty(self.player, "chocolate"), 3)
        self.hungry("9.9")
        self.assertEqual(self.state().nutrition, D("24.9"))                   # 9,9 + 15
        self.assertEqual(self.qty(self.player, "chocolate"), 2)

    def test_the_preferred_food_has_priority_when_it_is_in_the_inventory(self):
        for key in ("juice", "chocolate", "pasta"):
            self.give(self.player, key, 2)
        self.enable("pasta")
        self.hungry(5)
        self.assertEqual(self.state().nutrition, 55)
        self.assertEqual((self.qty(self.player, "pasta"), self.qty(self.player, "juice"), self.qty(self.player, "chocolate")), (1, 2, 2))
        sel = auto_movements(self.player)[0].explained["selection"]
        self.assertEqual((sel["rule"], sel["chosen"], sel["preferred"]), ("preferred", "pasta", "pasta"))
        self.assertEqual(sel["candidates"], {"chocolate": "15.0000", "juice": "5.0000", "pasta": "50.0000"})

    def test_without_the_preferred_food_it_eats_the_available_food_with_the_smallest_nutrition_gain(self):
        for key in ("pasta", "chocolate", "hamburger"):
            self.give(self.player, key, 1)
        self.enable("juice")                                                   # preferido configurado, mas não está no inventário
        self.hungry(5)
        self.assertEqual(self.state().nutrition, 20)                           # chocolate (15) é o de menor ganho
        self.assertEqual([m.product.key for m in auto_movements(self.player)], ["chocolate"])
        self.assertEqual(auto_movements(self.player)[0].explained["selection"]["rule"], "lowest_gain")

    def test_without_any_preference_it_also_uses_the_smallest_gain(self):
        self.give(self.player, "pasta", 1)
        self.give(self.player, "hamburger", 1)
        self.enable()
        self.hungry(0)
        self.assertEqual(self.state().nutrition, 30)
        self.assertEqual(self.qty(self.player, "hamburger"), 0)
        self.assertEqual(self.qty(self.player, "pasta"), 1)

    def test_ties_in_the_smallest_gain_are_broken_deterministically_by_product_key(self):
        for key in ("sun_dried_meat", "hamburger", "bread"):                   # os três ganham 30
            self.give(self.player, key, 1)
        self.enable()
        self.hungry(0)
        self.state()
        self.assertEqual([m.product.key for m in auto_movements(self.player)], ["bread"])

    def test_a_preferred_food_that_cannot_be_consumed_is_skipped(self):
        self.give(self.player, "juice", 2)
        self.give(self.player, "chocolate", 2)
        self.enable("juice")
        self.unspecify_food("juice")                                           # NULL ≠ 0: o consumo manual também o recusaria
        self.hungry(5)
        self.assertEqual(self.state().nutrition, 20)
        self.assertEqual((self.qty(self.player, "juice"), self.qty(self.player, "chocolate")), (2, 1))

    def test_zero_gain_foods_and_non_food_items_are_not_eligible(self):
        for key in ("ice_cream", "soda", "wheat", "clothes"):
            self.give(self.player, key, 2)
        self.enable("ice_cream")
        self.hungry(5)
        self.assertEqual(self.state().nutrition, 5)
        self.assertEqual(auto_movements(self.player), [])
        self.give(self.player, "juice", 1)                                     # com um alimento elegível, ele é escolhido
        self.assertEqual(self.state().nutrition, 10)
        self.assertEqual(self.qty(self.player, "ice_cream"), 2)


class RepetitionTests(AutoTestCase):
    def test_it_repeats_while_below_ten_and_stops_when_it_reaches_ten(self):
        self.give(self.player, "juice", 5)
        self.enable()
        self.hungry(0)
        self.assertEqual(self.state().nutrition, 10)                           # 0 → 5 → 10: "atingir" encerra
        self.assertEqual(self.qty(self.player, "juice"), 3)
        self.assertEqual(len(auto_movements(self.player)), 2)

    def test_it_stops_after_passing_ten(self):
        self.give(self.player, "juice", 5)
        self.enable()
        self.hungry(4)
        self.assertEqual(self.state().nutrition, 14)                           # 4 → 9 → 14: "ultrapassar" encerra
        self.assertEqual(self.qty(self.player, "juice"), 3)

    def test_it_stops_when_the_eligible_food_runs_out(self):
        self.give(self.player, "juice", 1)
        self.enable()
        self.hungry(0)
        self.assertEqual(self.state().nutrition, 5)                            # acabou o alimento: sem erro, sem ação extra
        self.assertEqual(self.qty(self.player, "juice"), 0)
        self.assertEqual(self.state().nutrition, 5)

    def test_it_can_change_food_between_repetitions(self):
        self.give(self.player, "juice", 1)
        self.give(self.player, "chocolate", 1)
        self.enable("juice")
        self.hungry(0)
        self.assertEqual(self.state().nutrition, 20)                           # suco (5, preferido) e depois chocolate (15)
        self.assertEqual([m.product.key for m in auto_movements(self.player)], ["juice", "chocolate"])

    def test_no_eligible_food_means_no_action_at_all(self):
        self.enable("pasta")
        self.hungry(3)
        world = self.world()
        self.assertEqual(self.state().nutrition, 3)
        self.assertEqual(self.world(), world)
        self.assertIsNone(food_effect(self.player))

    def test_it_does_not_run_again_once_the_player_is_fed(self):
        self.give(self.player, "chocolate", 3)
        self.enable()
        self.hungry(5)
        self.state()
        self.state()
        self.state()
        self.assertEqual(self.qty(self.player, "chocolate"), 2)
        self.assertEqual(len(auto_movements(self.player)), 1)


class SameRulesAsManualTests(AutoTestCase):
    def test_automatic_and_manual_consumption_have_exactly_the_same_effect(self):
        for p in (self.player, self.other):
            self.give(p, "chocolate", 2)
            self.hungry(5, p)
        self.enable(player=self.player)
        auto_state = self.state(self.player)                                   # automático
        manual = services.consume(self.other.pk, "chocolate")                  # manual, mesmo alimento
        self.assertTrue(manual.ok)
        self.assertEqual(auto_state.nutrition, self.state(self.other).nutrition)           # sem bônus especial
        self.assertEqual(self.qty(self.player, "chocolate"), self.qty(self.other, "chocolate"))
        a, b = food_effect(self.player), food_effect(self.other)
        self.assertEqual((a.source, a.amount, a.expires_at - a.starts_at), (b.source, b.amount, b.expires_at - b.starts_at))
        ma = auto_movements(self.player)[0]
        mb = InventoryMovement.objects.get(player=self.other, operation=Operation.CONSUMPTION.value)
        self.assertEqual((ma.delta, ma.quantity_after, ma.origin, ma.destination), (mb.delta, mb.quantity_after, mb.origin.replace(
            str(self.other.pk), str(self.player.pk)), mb.destination))
        self.assertEqual(ma.explained["nutrition_gain"], mb.explained["nutrition_gain"])

    def test_the_food_effect_replaces_the_previous_one_instead_of_stacking(self):
        self.give(self.player, "sun_dried_meat", 1)
        self.give(self.player, "chocolate", 1)
        services.consume(self.player.pk, "chocolate")
        self.assertEqual(food_effect(self.player).amount, D("0.05"))
        self.give(self.player, "chocolate", 1)
        self.enable("sun_dried_meat")
        self.hungry(5)
        self.state()                                                           # come a carne de sol (debuff) sozinho
        self.assertEqual(QolEffect.objects.filter(player=self.player, category="food").count(), 1)
        self.assertEqual((food_effect(self.player).source, food_effect(self.player).amount), ("food:sun_dried_meat", D("-0.05")))

    def test_a_food_without_qol_effect_leaves_the_current_effect_alone_also_automatically(self):
        self.give(self.player, "chocolate", 1)
        self.give(self.player, "pasta", 1)
        services.consume(self.player.pk, "chocolate")
        self.enable("pasta")
        self.hungry(5)
        self.state()
        self.assertEqual(food_effect(self.player).source, "food:chocolate")
        self.assertEqual(self.qty(self.player, "pasta"), 0)

    def test_the_nutrition_never_exceeds_the_maximum_and_money_never_moves(self):
        self.give(self.player, "pasta", 3)
        self.enable()
        self.hungry("9.99")
        money = (self.money(self.player), self.union())
        self.assertEqual(self.state().nutrition, D("59.99"))
        self.assertEqual((self.money(self.player), self.union()), money)


class TrailAndAuditTests(AutoTestCase):
    audit_inventory_at_end = False          # um teste grava de propósito um movimento forjado para provar que a auditoria o acusa

    def test_every_automatic_consumption_is_in_the_trail_with_its_explanation(self):
        self.give(self.player, "chocolate", 2)
        self.enable()
        self.hungry("4.5")
        self.state()
        (m,) = auto_movements(self.player)
        self.assertEqual((m.operation, m.delta, m.quantity_after, m.reference_kind, m.reference_id, m.destination),
                         ("consumption", -1, 1, AUTO_CONSUMPTION_REFERENCE, "chocolate", "consumption"))
        self.assertEqual((m.explained["automatic"], m.explained["nutrition_before"], m.explained["threshold"]), (True, "4.500000", "10"))
        self.assertEqual(m.explained["selection"]["candidates"], {"chocolate": "15.0000"})
        self.assertTrue(audit_inventory().ok)

    def test_the_audit_flags_an_automatic_consumption_above_the_threshold(self):
        self.give(self.player, "chocolate", 1)
        InventoryMovement.objects.create(
            player=self.player, product_id=InventoryMovement.objects.first().product_id, delta=-1, quantity_after=0,
            operation="consumption", origin=f"player:{self.player.pk}", destination="consumption", key="forged",
            reference_kind=AUTO_CONSUMPTION_REFERENCE, reference_id="chocolate", at=0,
            explained={"automatic": True, "nutrition_before": "50"})
        report = audit_inventory()
        self.assertIn("AUTO_CONSUMPTION_ABOVE_THRESHOLD", {f["code"] for f in report.findings})


class LazyIntegrationTests(AutoTestCase):
    def test_hunger_that_builds_up_over_time_is_handled_at_the_next_access_and_not_before(self):
        self.give(self.player, "chocolate", 2)
        self.enable()
        self.hungry(12)
        self.clk.advance(hours=2)                                              # 12 ciclos × 0,5 de queda: Nutrição abaixo de 10
        self.assertEqual(InventoryMovement.objects.filter(operation="consumption").count(), 0)      # ninguém "vigia": nada rodou
        player = self.state()
        self.assertEqual(self.qty(self.player, "chocolate"), 1)
        self.assertGreaterEqual(player.nutrition, 10)

    def test_with_enough_nutrition_the_hook_does_not_even_query_the_configuration(self):
        self.give(self.player, "chocolate", 1)
        self.enable()
        self.hungry(50)
        with CaptureQueriesContext(connection) as ctx:
            self.state()
        self.assertFalse([q for q in ctx.captured_queries if "inventory_autoconsumption" in q["sql"]])

    def test_every_lazy_processing_path_triggers_it_exactly_once(self):
        """Qualquer processamento do jogador (sync, sessão de outros sistemas, snapshot, ações do registro) roda o hook."""
        def locked(p):
            with player_services.locked_player(p.pk):
                pass

        paths = {
            "sync_player": lambda p: player_services.sync_player(p.pk),
            "locked_player": locked,
            "get_snapshot": lambda p: player_services.get_snapshot(p.pk),
            "check_action": lambda p: registry.check_action(p.pk, "consume", "chocolate"),
            "available_actions": lambda p: registry.available_actions(p.pk),
            "execute_action(leisure)": lambda p: registry.execute_action(p.pk, "leisure"),
        }
        self.enable()
        for name, run in paths.items():
            with self.subTest(name):
                before = len(auto_movements(self.player))
                self.give(self.player, "chocolate", 1)
                self.hungry(5)
                run(self.player)
                self.assertEqual(len(auto_movements(self.player)), before + 1, name)
                self.assertEqual(self.qty(self.player, "chocolate"), 0, name)
                self.assertEqual(Player.objects.get(pk=self.player.pk).nutrition, 20, name)

    def test_a_manual_consumption_processes_the_player_first_and_stays_consistent(self):
        self.give(self.player, "chocolate", 1)
        self.give(self.player, "pasta", 1)
        self.enable("chocolate")
        self.hungry(5)
        res = services.consume(self.player.pk, "pasta")                        # o acesso come o chocolate; depois a massa
        self.assertTrue(res.ok, res)
        self.assertEqual((self.qty(self.player, "chocolate"), self.qty(self.player, "pasta")), (0, 0))
        self.assertEqual(self.state().nutrition, 70)                           # 5 + 15 + 50
        self.assertEqual(len(auto_movements(self.player)), 1)


class NoRecursionTests(AutoTestCase):
    """`_catch_up` → hook → consumo → `sync_player` → `_catch_up` → hook... não pode acontecer."""

    def test_the_catch_up_runs_exactly_once_per_access_even_when_it_auto_consumes(self):
        self.give(self.player, "chocolate", 1)
        self.enable()
        self.hungry(5)
        with mock.patch.object(player_services, "_catch_up", wraps=player_services._catch_up) as catch_up:
            self.state()
        self.assertEqual(catch_up.call_count, 1)
        self.assertEqual(len(auto_movements(self.player)), 1)

    def test_the_hook_never_calls_the_public_consumption_or_sync_services(self):
        self.give(self.player, "chocolate", 1)
        self.enable()
        self.hungry(5)
        with mock.patch.object(services, "consume", side_effect=AssertionError("consume público")), \
                mock.patch.object(player_services, "sync_player", side_effect=AssertionError("sync_player")):
            with player_services.locked_player(self.player.pk):                # o catch-up roda o hook aqui dentro
                pass
        self.assertEqual(len(auto_movements(self.player)), 1)

    def test_a_manual_consumption_runs_the_catch_up_once(self):
        self.give(self.player, "chocolate", 1)
        self.hungry(50)
        with mock.patch.object(player_services, "_catch_up", wraps=player_services._catch_up) as catch_up:
            self.assertTrue(services.consume(self.player.pk, "chocolate").ok)
        self.assertEqual(catch_up.call_count, 1)

    def test_the_reentrancy_guard_makes_a_nested_hook_a_no_op(self):
        self.give(self.player, "chocolate", 3)
        self.enable()
        self.hungry(5)
        real = services.consume_locked

        def nested(player, key, now, **kw):
            auto.on_access(player, now)                                        # alguém religa o caminho: o guarda segura
            return real(player, key, now, **kw)

        with mock.patch.object(services, "consume_locked", side_effect=nested):
            self.state()
        self.assertEqual(self.qty(self.player, "chocolate"), 2)                # um consumo só, sem laço aninhado
        self.assertEqual(len(auto_movements(self.player)), 1)


class IntegrityTests(AutoTestCase):
    def test_a_long_session_of_hunger_keeps_inventory_nutrition_and_audit_consistent(self):
        self.give(self.player, "juice", 7)
        self.give(self.player, "chocolate", 4)
        self.give(self.player, "pasta", 2)
        self.enable("chocolate")
        eaten = 0
        for day in range(6):
            self.clk.advance(hours=12)
            state = self.state()
            self.assertTrue(0 <= state.nutrition <= 100, state.nutrition)
        for m in InventoryMovement.objects.filter(operation="consumption"):
            eaten += -m.delta
        held = sum(self.qty(self.player, k) for k in ("juice", "chocolate", "pasta"))
        self.assertEqual(held + eaten, 13)                                     # nada nasce nem some
        self.assertGreater(eaten, 0)
        self.assertTrue(audit_inventory().ok)
