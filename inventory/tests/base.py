from decimal import Decimal

from catalog.loader import sync_catalog
from catalog.models import FoodProfile, Product
from inventory import services
from inventory.audit import audit_inventory
from inventory.constants import Operation
from inventory.models import InventoryItem, InventoryMovement, Shipment
from ledger import services as ledger
from ledger.audit import ledger_metrics
from ledger.models import Account
from ledger.tests.base import LedgerHelpers, T0  # noqa: F401
from players.tests.base import PlayerTestCase

D = Decimal


class InventoryTestCase(LedgerHelpers, PlayerTestCase):
    """Mundo pequeno + catálogo do 22 + relógio manual + jogador; ao fim de TODO teste, o ledger e o inventário estão íntegros."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        sync_catalog()

    audit_inventory_at_end = True

    def setUp(self):
        super().setUp()
        self.ledger_setup()
        if self.audit_inventory_at_end:
            self.addCleanup(self._audit_inventory)
        self.other = self.new_player("p2")
        self.third = self.new_player("p3")

    def _audit_inventory(self):
        report = audit_inventory()
        self.assertTrue(report.ok, report.findings)

    # --- auxiliares ---
    _seq = 0

    def give(self, player, key, quantity, operation=Operation.PURCHASE):
        """Item entra por uma operação documentada (compra), como o Varejo fará."""
        self._seq += 1
        res = services.credit(player.pk, key, quantity, operation=operation, origin="retail:test", key=f"t{id(self)}-{self._seq}",
                              reference_kind="test", reference_id=self._seq)
        self.assertTrue(res.ok, res)
        return res

    def qty(self, player, key):
        return services.quantity_of(player.pk, key)

    def money(self, player):
        return ledger.balance_of(ledger.player_account(player.pk).pk)

    def union(self):
        return ledger.balance_of(ledger.union_account().pk)

    def world(self):
        """Tudo que não pode mudar numa recusa."""
        return (list(InventoryItem.objects.values_list("player_id", "product_id", "quantity")),
                InventoryMovement.objects.count(), Shipment.objects.count(), ledger_metrics()["in_circulation"],
                {a.pk: a.balance for a in Account.objects.all()})

    def assertRefused(self, res, code, **detail):
        self.assertEqual((res.ok, res.code), (False, code), (res.code, res.detail))
        for k, v in detail.items():
            self.assertEqual(res.detail.get(k), v, (k, res.detail))

    def unspecify_food(self, key):
        FoodProfile.objects.filter(product__key=key).update(nutrition_amount=None, qol_intensity=None)

    def unspecify_price(self, key):
        Product.objects.filter(key=key).update(base_price=None)
