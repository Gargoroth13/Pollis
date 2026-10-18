"""Auditoria do Inventário (05 §19): a trilha reconstrói a posse; adulteração direta no banco (fora do ORM) é detectada."""
import io

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from inventory import services
from inventory.audit import audit_inventory
from inventory.constants import Operation
from inventory.models import InventoryItem, InventoryMovement, Shipment

from .base import InventoryTestCase
from .test_mail import ledger_account


def sql(statement, params=()):
    with connection.cursor() as cur:
        cur.execute(statement, params)


class AuditTests(InventoryTestCase):
    audit_inventory_at_end = False        # estes testes adulteram o banco de propósito

    def setUp(self):
        super().setUp()
        self.give(self.player, "hamburger", 4)
        self.give(self.player, "bread", 2)
        self.fund(ledger_account(self.player), 100_000)
        services.send_item(self.player.pk, self.other.pk, "hamburger", 1)
        services.consume(self.player.pk, "bread")

    def codes(self):
        return sorted({f["code"] for f in audit_inventory().findings})

    def test_a_consistent_inventory_passes_and_reports_its_totals(self):
        report = audit_inventory()
        self.assertTrue(report.ok, report.findings)
        self.assertEqual(report.stats, {"movements": 5, "holdings": 3, "shipments": 1, "units": 3 + 1 + 1})

    def test_a_changed_holding_is_detected(self):
        InventoryItem.objects.filter(player=self.player, product__key="hamburger").update(quantity=99)
        self.assertEqual(self.codes(), ["HOLDING_MISMATCH"])

    def test_a_holding_without_movements_and_a_missing_holding_are_detected(self):
        InventoryItem.objects.create(player=self.third, product=InventoryMovement.objects.first().product, quantity=3)
        self.assertEqual(self.codes(), ["HOLDING_WITHOUT_MOVEMENTS"])
        InventoryItem.objects.filter(player=self.third).delete()
        InventoryItem.objects.filter(player=self.other).delete()
        self.assertEqual(self.codes(), ["HOLDING_MISMATCH"])

    def test_a_forged_quantity_after_and_a_wrong_sign_are_detected(self):
        first = InventoryMovement.objects.order_by("id").first()
        sql("UPDATE inventory_inventorymovement SET quantity_after = quantity_after + 7 WHERE id = %s", [first.pk])
        self.assertIn("QUANTITY_AFTER_MISMATCH", self.codes())
        sql("UPDATE inventory_inventorymovement SET quantity_after = %s WHERE id = %s", [first.quantity_after, first.pk])
        self.assertTrue(audit_inventory().ok)
        sql("UPDATE inventory_inventorymovement SET operation = %s WHERE id = %s", [Operation.SALE.value, first.pk])
        self.assertEqual(self.codes(), ["OPERATION_SIGN_MISMATCH"])
        sql("UPDATE inventory_inventorymovement SET operation = %s WHERE id = %s", ["gift", first.pk])
        self.assertEqual(self.codes(), ["UNKNOWN_OPERATION"])

    def test_a_shipment_missing_a_movement_or_with_another_fee_is_detected(self):
        shipment = Shipment.objects.get()
        sql("UPDATE inventory_shipment SET fee = fee + 1 WHERE id = %s", [shipment.pk])
        self.assertEqual(self.codes(), ["SHIPMENT_FEE_ENTRY_MISMATCH"])
        sql("UPDATE inventory_shipment SET fee = fee - 1 WHERE id = %s", [shipment.pk])
        sql("UPDATE inventory_shipment SET quantity = 9 WHERE id = %s", [shipment.pk])
        self.assertIn("SHIPMENT_MOVEMENT_MISMATCH", self.codes())
        sql("UPDATE inventory_shipment SET quantity = 1 WHERE id = %s", [shipment.pk])
        self.assertTrue(audit_inventory().ok)
        sql("UPDATE inventory_inventorymovement SET reference_id = %s WHERE operation = %s", ["999", "transfer_in"])
        self.assertIn("SHIPMENT_MOVEMENTS_MISSING", self.codes())

    def test_the_command_reports_and_fails_on_findings(self):
        out = io.StringIO()
        call_command("audit_inventory", stdout=out)
        self.assertIn("achados=0", out.getvalue())
        call_command("audit_inventory", "--json", stdout=io.StringIO())
        InventoryItem.objects.filter(player=self.player, product__key="hamburger").update(quantity=99)
        with self.assertRaises(CommandError):
            call_command("audit_inventory", stdout=io.StringIO())


class EmptyInventoryAuditTests(InventoryTestCase):
    def test_an_empty_inventory_passes(self):
        report = audit_inventory()
        self.assertTrue(report.ok)
        self.assertEqual(report.stats, {"movements": 0, "holdings": 0, "shipments": 0, "units": 0})
