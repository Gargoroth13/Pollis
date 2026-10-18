"""Correio (05 §11-14): envio direto com taxa obrigatória `MAX(mínimo, valor de referência × percentual)`, cobrada do remetente."""
from decimal import ROUND_HALF_EVEN, Decimal
from unittest import mock

from core.breakdown import Calc
from inventory import params, services
from inventory.models import InventoryImmutableError, InventoryMovement, Shipment
from ledger.audit import ledger_metrics
from ledger.models import Entry
from players import registry

from .base import InventoryTestCase

D = Decimal


class MailFeeFormulaTests(InventoryTestCase):
    def test_the_fee_is_the_larger_of_the_minimum_and_the_reference_value_times_the_rate(self):
        # hambúrguer R$ 75,00 × 3 = R$ 225,00 → 10% = R$ 22,50 (acima do mínimo de R$ 1,00)
        fee, refusal = services.mail_fee("hamburger", 3)
        self.assertIsNone(refusal)
        self.assertEqual((fee.value, services.fee_cents(fee)), (D(2250), 2250))
        self.assertEqual(fee.step("reference_value").amount, D(22500))
        self.assertEqual(fee.step("mail_fee_rate").amount, params.MAIL_FEE_RATE)
        self.assertFalse(fee.step("mail_fee_min").binding)
        self.assertEqual(fee.restricted_by, ())

    def test_the_minimum_binds_for_cheap_items_and_the_explanation_says_so(self):
        with mock.patch.object(params, "MAIL_FEE_MIN_CENTS", 5000):
            fee, _ = services.mail_fee("wheat", 1)                              # R$ 10,00 × 10% = R$ 1,00 < R$ 50,00
        self.assertEqual((services.fee_cents(fee), fee.restricted_by), (5000, ("mail_fee_min",)))

    def test_the_fee_scales_with_the_quantity_and_uses_the_catalog_reference_value_not_a_market_price(self):
        one, _ = services.mail_fee("pasta", 1)
        ten, _ = services.mail_fee("pasta", 10)
        self.assertEqual((services.fee_cents(one), services.fee_cents(ten)), (550, 5500))      # R$ 55,00 [PROV] × 10%

    def test_rounding_happens_once_to_centavos_half_even(self):
        for raw, expected in (("2.5", 2), ("3.5", 4), ("2.4", 2), ("2.6", 3)):
            self.assertEqual(services.fee_cents(Calc("x", D(raw)).result()), expected)
        with mock.patch.object(params, "MAIL_FEE_RATE", D("0.0333")):
            fee, _ = services.mail_fee("pasta", 1)                              # 5500 × 0,0333 = 183,15 → 183 (mínimo 100)
        self.assertEqual(services.fee_cents(fee), 183)

    def test_a_fee_cannot_be_invented_without_a_reference_value(self):
        self.unspecify_price("pasta")
        fee, refusal = services.mail_fee("pasta", 1)
        self.assertIsNone(fee)
        self.assertRefused(refusal, "UNSPECIFIED_DESIGN_VALUE", missing=["base_price"])
        self.assertEqual(services.mail_fee("no_such", 1)[1].code, "UNKNOWN_PRODUCT")
        for bad in (0, -1, True, 1.5):
            self.assertEqual(services.mail_fee("pasta", bad)[1].code, "INVALID_QUANTITY")

    def test_the_provisional_table_lists_every_inventory_parameter_with_its_source(self):
        rows = {r.parameter: r for r in params.provisional_table()}
        self.assertEqual(set(rows), {"mail_fee_rate", "mail_fee_min_cents", "food_effect_duration_seconds"})
        for r in rows.values():
            self.assertEqual((r.status, r.source), ("PROV", params.SOURCE))
        self.assertEqual(D(rows["mail_fee_rate"].value), params.MAIL_FEE_RATE)
        self.assertEqual(int(rows["mail_fee_min_cents"].value), params.MAIL_FEE_MIN_CENTS)
        self.assertEqual(int(rows["food_effect_duration_seconds"].value), params.FOOD_EFFECT_DURATION_SECONDS)


class SendItemTests(InventoryTestCase):
    def setUp(self):
        super().setUp()
        self.give(self.player, "hamburger", 5)
        self.fund(ledger_account(self.player), 100_000)             # R$ 1.000,00

    def test_the_item_moves_the_fee_is_charged_and_everything_is_traceable(self):
        union_before, money_before = self.union(), self.money(self.player)
        circulation = ledger_metrics()["in_circulation"]
        res = services.send_item(self.player.pk, self.other.pk, "hamburger", 2)
        self.assertTrue(res.ok, res)
        self.assertEqual((self.qty(self.player, "hamburger"), self.qty(self.other, "hamburger")), (3, 2))
        self.assertEqual((res.detail["fee"], res.detail["reference_value"]), (1500, 15000))        # 10% de R$ 150,00
        self.assertEqual((self.money(self.player), self.union()), (money_before - 1500, union_before + 1500))
        self.assertEqual(ledger_metrics()["in_circulation"], circulation)                          # dinheiro só mudou de mãos
        shipment = Shipment.objects.get()
        self.assertEqual((shipment.sender_id, shipment.recipient_id, shipment.quantity, shipment.fee, shipment.sequence),
                         (self.player.pk, self.other.pk, 2, 1500, 1))
        self.assertEqual(shipment.explained["steps"][0]["key"], "reference_value")
        out, inn = InventoryMovement.objects.filter(reference_kind="shipment").order_by("id")
        self.assertEqual((out.operation, out.delta, out.origin, out.destination, out.quantity_after),
                         ("transfer_out", -2, f"player:{self.player.pk}", f"player:{self.other.pk}", 3))
        self.assertEqual((inn.operation, inn.delta, inn.player_id, inn.quantity_after), ("transfer_in", 2, self.other.pk, 2))
        entry = Entry.objects.get(nature="mail_fee")
        self.assertEqual((entry.amount, entry.reference_kind, entry.operation), (1500, "shipment", "send_item"))

    def test_there_is_no_free_transfer_the_fee_always_applies(self):
        for quantity in (1, 2, 2):
            before = self.money(self.player)
            self.assertTrue(services.send_item(self.player.pk, self.other.pk, "hamburger", quantity).ok)
            self.assertGreater(before - self.money(self.player), 0)
        self.assertEqual(Entry.objects.filter(nature="mail_fee").count(), 3)
        self.assertEqual(list(Shipment.objects.values_list("sequence", flat=True)), [1, 2, 3])

    def test_sending_all_of_an_item_empties_the_sender_and_the_recipient_accumulates(self):
        self.give(self.other, "hamburger", 1)
        self.assertTrue(services.send_item(self.player.pk, self.other.pk, "hamburger", 5).ok)
        self.assertEqual((self.qty(self.player, "hamburger"), self.qty(self.other, "hamburger")), (0, 6))

    def test_refusals_change_nothing(self):
        self.unspecify_price("pasta")
        self.give(self.player, "pasta", 1)
        broke = self.new_player("broke")
        self.give(broke, "hamburger", 1)
        before = self.world()
        cases = [
            (self.player.pk, self.other.pk, "hamburger", 6, "INSUFFICIENT_QUANTITY"),
            (self.player.pk, self.other.pk, "wheat", 1, "INSUFFICIENT_QUANTITY"),
            (self.player.pk, self.player.pk, "hamburger", 1, "SAME_PLAYER"),
            (self.player.pk, 10 ** 9, "hamburger", 1, "RECIPIENT_NOT_FOUND"),
            (self.player.pk, "x", "hamburger", 1, "INVALID_PARAMS"),
            (self.player.pk, self.other.pk, "no_such", 1, "UNKNOWN_PRODUCT"),
            (self.player.pk, self.other.pk, "pasta", 1, "UNSPECIFIED_DESIGN_VALUE"),
            (self.player.pk, self.other.pk, "hamburger", 0, "INVALID_QUANTITY"),
            (self.player.pk, self.other.pk, "hamburger", True, "INVALID_QUANTITY"),
            (10 ** 9, self.other.pk, "hamburger", 1, "PLAYER_NOT_FOUND"),
            (broke.pk, self.other.pk, "hamburger", 1, "INSUFFICIENT_FUNDS"),
        ]
        for sender, recipient, product, quantity, code in cases:
            self.assertRefused(services.send_item(sender, recipient, product, quantity), code)
        self.assertEqual(self.world(), before)

    def test_insufficient_funds_reports_the_shortfall_and_moves_nothing(self):
        poor = self.new_player("poor")
        self.give(poor, "hamburger", 2)
        self.fund(ledger_account(poor), 1000)                          # R$ 10,00, a taxa de 1 hambúrguer é R$ 7,50; de 2, R$ 15,00
        self.assertTrue(services.send_item(poor.pk, self.other.pk, "hamburger", 1).ok)
        res = services.send_item(poor.pk, self.other.pk, "hamburger", 1)
        self.assertRefused(res, "INSUFFICIENT_FUNDS", fee=750)
        self.assertEqual((self.qty(poor, "hamburger"), self.qty(self.other, "hamburger"), self.money(poor)), (1, 1, 250))

    def test_the_trail_and_the_shipments_are_immutable(self):
        services.send_item(self.player.pk, self.other.pk, "hamburger", 1)
        shipment = Shipment.objects.get()
        with self.assertRaises(InventoryImmutableError):
            shipment.fee = 0
            shipment.save()
        with self.assertRaises(InventoryImmutableError):
            shipment.delete()
        with self.assertRaises(InventoryImmutableError):
            Shipment.objects.update(fee=0)
        with self.assertRaises(InventoryImmutableError):
            Shipment.objects.all().delete()


class SendThroughTheRegistryTests(InventoryTestCase):
    def setUp(self):
        super().setUp()
        self.give(self.player, "hamburger", 3)
        self.fund(ledger_account(self.player), 100_000)

    def target(self, **kw):
        t = {"recipient": self.other.pk, "product": "hamburger", "quantity": 1}
        t.update(kw)
        return t

    def test_available_in_general_and_the_preview_shows_the_fee_before_any_charge(self):
        self.assertTrue({a.action_id: a for a in registry.available_actions(self.player.pk)}["send_item"].available)
        money = self.money(self.player)
        c = registry.check_action(self.player.pk, "send_item", self.target(quantity=2))
        self.assertEqual((c.available, c.target_validated, c.preview["fee_cents"]), (True, True, 1500))
        self.assertEqual(c.preview["fee"].value, D(1500))
        self.assertEqual(self.money(self.player), money)                         # só consulta

    def test_execution_through_the_registry_equals_the_direct_service(self):
        res = registry.execute_action(self.player.pk, "send_item", self.target(quantity=2))
        self.assertTrue(res.ok, res)
        self.assertEqual((res.detail["fee"], self.qty(self.other, "hamburger")), (1500, 2))

    def test_invalid_params_and_requirements_are_declared(self):
        for bad in ({"recipient": 1}, {**self.target(), "extra": 1}, {**self.target(), "product": 5}, [1, 2], "x"):
            self.assertEqual(registry.check_action(self.player.pk, "send_item", bad).code, "INVALID_PARAMS", bad)
            self.assertEqual(registry.execute_action(self.player.pk, "send_item", bad).code, "INVALID_PARAMS", bad)
        self.assertEqual(registry.execute_action(self.player.pk, "send_item").code, "TARGET_REQUIRED")
        declared = set(registry.get_descriptor("send_item").requirements)
        seen = {registry.check_action(self.player.pk, "send_item", self.target(**kw)).code for kw in (
            {"quantity": 0}, {"recipient": self.player.pk}, {"recipient": 10 ** 9}, {"product": "no_such"},
            {"quantity": 99})}
        self.assertLessEqual(seen, declared)
        self.unspecify_price("pasta")
        self.give(self.player, "pasta", 1)
        seen.add(registry.check_action(self.player.pk, "send_item", self.target(product="pasta")).code)
        self.assertEqual(seen, {"INVALID_QUANTITY", "SAME_PLAYER", "RECIPIENT_NOT_FOUND", "UNKNOWN_PRODUCT",
                                "INSUFFICIENT_QUANTITY", "UNSPECIFIED_DESIGN_VALUE"})


def ledger_account(player):
    from ledger import services as ledger
    return ledger.player_account(player.pk)
