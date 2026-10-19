"""Posse (05 §2-3, §17-19): agregada por jogador e produto, trilha imutável, idempotência e operações documentadas."""
from django.db.models import F

from inventory import services
from inventory.constants import MAX_QUANTITY, Operation
from inventory.models import InventoryImmutableError, InventoryItem, InventoryMovement, Shipment
from players.models import Player

from .base import InventoryTestCase


def credit(player, product="wheat", quantity=5, **kw):
    """`services.credit` com padrões válidos; `kw` sobrescreve (inclusive a chave de idempotência `key`)."""
    args = dict(operation=Operation.PURCHASE, origin="retail:1", key="k1", reference_kind="order", reference_id="1")
    args.update(kw)
    return services.credit(player.pk, product, quantity, **args)


class StructureTests(InventoryTestCase):
    def test_holdings_are_aggregated_per_player_and_product(self):
        self.give(self.player, "wheat", 20)
        self.give(self.player, "wheat", 5)
        self.give(self.player, "bread", 2)
        self.give(self.other, "wheat", 1)
        self.assertEqual((self.qty(self.player, "wheat"), self.qty(self.player, "bread"), self.qty(self.other, "wheat")), (25, 2, 1))
        self.assertEqual(InventoryItem.objects.filter(player=self.player, product__key="wheat").count(), 1)   # uma linha agregada
        self.assertEqual(self.qty(self.third, "wheat"), 0)

    def test_the_inventory_view_groups_by_the_catalog_category_without_inventing_categories(self):
        self.give(self.player, "bread", 3)
        self.give(self.player, "wheat", 4)
        self.give(self.player, "clothes", 1)
        view = services.inventory_of(self.player.pk)
        self.assertEqual(sorted(view), ["equipment", "food", "material"])           # categorias do catálogo
        self.assertEqual([(i.key, i.quantity, i.is_consumable) for i in view["food"]], [("bread", 3, True)])
        self.assertEqual([i.key for i in view["material"]], ["wheat"])
        self.assertEqual(view["equipment"][0].category, "equipment")
        self.assertEqual(services.inventory_of(self.third.pk), {})

    def test_holdings_reference_the_catalog_product_and_never_copy_it(self):
        fields = {f.name for f in InventoryItem._meta.get_fields()}
        self.assertEqual(fields, {"id", "player", "product", "quantity"})

    def test_the_holding_row_disappears_at_zero_but_the_trail_keeps_the_history(self):
        self.give(self.player, "wheat", 3)
        res = services.debit(self.player.pk, "wheat", 3, operation=Operation.SALE, destination="market:1", key="s1",
                             reference_kind="listing", reference_id="1")
        self.assertEqual((res.ok, res.detail["quantity"]), (True, 0))
        self.assertFalse(InventoryItem.objects.filter(player=self.player).exists())
        self.assertEqual(list(InventoryMovement.objects.order_by("id").values_list("delta", "quantity_after")), [(3, 3), (-3, 0)])

    def test_there_is_no_capacity_limit_in_this_version(self):
        self.give(self.player, "wheat", 10 ** 9)
        self.assertEqual(self.qty(self.player, "wheat"), 10 ** 9)


class OperationsAreDocumentedTests(InventoryTestCase):
    def test_other_systems_may_only_credit_by_purchase_or_production(self):
        for op in (Operation.CONSUMPTION, Operation.TRANSFER_IN, Operation.TRANSFER_OUT, Operation.SALE):
            self.assertRefused(credit(self.player, operation=op, key=f"c-{op.value}"), "OPERATION_NOT_ALLOWED")
        self.assertRefused(credit(self.player, operation="gift", key="c-x"), "OPERATION_NOT_ALLOWED")
        self.assertTrue(credit(self.player, operation=Operation.PRODUCTION, key="c-prod", origin="company:1").ok)
        self.assertEqual(self.qty(self.player, "wheat"), 5)

    def test_other_systems_may_only_debit_by_sale(self):
        self.give(self.player, "wheat", 5)
        for op in (Operation.PURCHASE, Operation.CONSUMPTION, Operation.TRANSFER_OUT):
            res = services.debit(self.player.pk, "wheat", 1, operation=op, destination="x", key=f"d-{op.value}",
                                 reference_kind="t", reference_id=1)
            self.assertRefused(res, "OPERATION_NOT_ALLOWED")
        self.assertEqual(self.qty(self.player, "wheat"), 5)

    def test_a_purchase_is_not_a_consumption(self):
        before = self.state().nutrition
        self.set_state(nutrition=20)
        self.give(self.player, "bread", 4)
        self.assertEqual((self.state().nutrition, self.qty(self.player, "bread")), (20, 4))     # nada é aplicado ao comprar
        self.assertEqual(before, 100)

    def test_origin_destination_key_and_reference_are_mandatory(self):
        for bad in (dict(origin=""), dict(key=""), dict(reference_kind=""), dict(reference_id="")):
            self.assertRefused(credit(self.player, **bad), "INVALID_PARAMS")
        res = services.debit(self.player.pk, "wheat", 1, operation=Operation.SALE, destination="", key="k", reference_kind="t",
                             reference_id=1)
        self.assertRefused(res, "INVALID_PARAMS")
        self.assertEqual(InventoryMovement.objects.count(), 0)


class ValidationTests(InventoryTestCase):
    def test_quantities_must_be_positive_integers_within_the_limit(self):
        for bad in (0, -1, 1.5, "2", None, True, MAX_QUANTITY + 1):
            self.assertRefused(credit(self.player, quantity=bad, key=f"q{bad!r}"), "INVALID_QUANTITY")
        self.assertTrue(credit(self.player, quantity=MAX_QUANTITY, key="max").ok)

    def test_unknown_product_and_player_are_refused_without_side_effects(self):
        before = self.world()
        self.assertRefused(credit(self.player, "no_such", key="u1"), "UNKNOWN_PRODUCT")
        self.assertRefused(services.credit(10 ** 9, "wheat", 1, operation=Operation.PURCHASE, origin="r", key="u2",
                                           reference_kind="o", reference_id=1), "PLAYER_NOT_FOUND")
        self.assertEqual(self.world(), before)

    def test_debit_cannot_go_below_zero(self):
        self.give(self.player, "wheat", 2)
        before = self.world()
        res = services.debit(self.player.pk, "wheat", 3, operation=Operation.SALE, destination="m", key="d1",
                             reference_kind="l", reference_id=1)
        self.assertRefused(res, "INSUFFICIENT_QUANTITY", have=2, required=3)
        none = services.debit(self.player.pk, "bread", 1, operation=Operation.SALE, destination="m", key="d2",
                              reference_kind="l", reference_id=1)
        self.assertRefused(none, "INSUFFICIENT_QUANTITY", have=0)
        self.assertEqual(self.world(), before)


class IdempotencyTests(InventoryTestCase):
    def test_repeating_a_key_with_the_same_content_changes_nothing(self):
        first = credit(self.player, quantity=5, key="same")
        again = credit(self.player, quantity=5, key="same")
        self.assertTrue(first.ok and again.ok)
        self.assertTrue(again.detail.get("already_applied"))
        self.assertEqual((self.qty(self.player, "wheat"), InventoryMovement.objects.count()), (5, 1))

    def test_repeating_a_key_with_other_content_is_a_conflict(self):
        credit(self.player, quantity=5, key="same")
        self.assertRefused(credit(self.player, quantity=6, key="same"), "IDEMPOTENCY_CONFLICT")              # outra quantidade
        self.assertRefused(credit(self.player, "bread", quantity=5, key="same"), "IDEMPOTENCY_CONFLICT")     # outro produto
        self.assertRefused(credit(self.player, quantity=5, key="same", operation=Operation.PRODUCTION),
                           "IDEMPOTENCY_CONFLICT")                                                           # outra operação
        self.assertRefused(credit(self.other, quantity=5, key="same"), "IDEMPOTENCY_CONFLICT")               # outro jogador
        self.assertEqual((self.qty(self.player, "wheat"), InventoryMovement.objects.count()), (5, 1))


class TrailTests(InventoryTestCase):
    def test_every_change_records_origin_destination_product_quantity_time_and_type(self):
        self.clk.advance(seconds=77)
        self.give(self.player, "wheat", 4)
        m = InventoryMovement.objects.get()
        self.assertEqual((m.player_id, m.product.key, m.delta, m.quantity_after, m.operation, m.origin, m.destination, m.at),
                         (self.player.pk, "wheat", 4, 4, "purchase", "retail:test", f"player:{self.player.pk}", self.clk.now()))
        self.assertTrue(m.key and m.reference_kind and m.reference_id)

    def test_the_trail_cannot_be_changed_or_erased(self):
        self.give(self.player, "wheat", 4)
        m = InventoryMovement.objects.get()
        with self.assertRaises(InventoryImmutableError):
            m.delta = 9
            m.save()
        with self.assertRaises(InventoryImmutableError):
            m.delete()
        with self.assertRaises(InventoryImmutableError):
            InventoryMovement.objects.update(delta=F("delta") + 1)
        with self.assertRaises(InventoryImmutableError):
            InventoryMovement.objects.all().delete()
        with self.assertRaises(InventoryImmutableError):
            InventoryMovement.objects.all()._raw_delete("default")
        self.assertEqual(InventoryMovement.objects.get().delta, 4)

    def test_players_with_holdings_or_history_cannot_be_deleted_by_cascade(self):
        self.give(self.player, "wheat", 1)
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            Player.objects.filter(pk=self.player.pk).delete()


class IntegrityRetryTests(InventoryTestCase):
    def test_a_real_database_violation_is_raised_once_and_never_recurses_forever(self):
        """Corrida na criação = UMA releitura; restrição violada de verdade (aqui simulada) sobe, sem recursão infinita."""
        from unittest import mock

        from django.db import IntegrityError
        calls = []

        def boom(*args, **kwargs):
            calls.append(1)
            raise IntegrityError("restrição violada")

        with mock.patch.object(InventoryMovement.objects, "create", side_effect=boom):
            with self.assertRaises(IntegrityError):
                credit(self.player, "wheat", 3)
        self.assertEqual(len(calls), 2)                                 # tentativa + uma releitura
        self.assertEqual(self.qty(self.player, "wheat"), 0)
        self.assertEqual(InventoryMovement.objects.count(), 0)
