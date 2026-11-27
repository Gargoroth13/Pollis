"""Propriedade: qualquer sequência de operações documentadas conserva os itens (entram só por compra/produção, saem só por
venda/consumo, o Correio apenas move), conserva o dinheiro (a taxa só muda de mãos) e deixa a trilha auditável."""
import random

from inventory import services
from inventory.audit import audit_inventory
from inventory.constants import Operation
from inventory.models import InventoryItem
from ledger.audit import ledger_metrics

from .base import InventoryTestCase
from .test_mail import ledger_account

PRODUCTS = ("bread", "hamburger", "wheat", "pasta", "clothes")


class ConservationPropertyTests(InventoryTestCase):
    def test_random_sequences_conserve_items_and_money(self):
        players = [self.player, self.other, self.third]
        for p in players:
            self.fund(ledger_account(p), 500_000)
        circulation = ledger_metrics()["in_circulation"]
        for seed in range(6):
            rng = random.Random(seed)
            entered = left = 0
            for step in range(40):
                p, q = rng.sample(players, 2)
                product, quantity = rng.choice(PRODUCTS), rng.randint(1, 4)
                op = rng.choice(("buy", "send", "send", "eat", "sell", "produce"))
                key = f"s{seed}-{step}"
                if op in ("buy", "produce"):
                    res = services.credit(p.pk, product, quantity, operation=Operation.PURCHASE if op == "buy" else Operation.PRODUCTION,
                                          origin="x:1", key=key, reference_kind="t", reference_id=key)
                    entered += quantity if res.ok else 0
                elif op == "send":
                    res = services.send_item(p.pk, q.pk, product, quantity)
                elif op == "eat":
                    res = services.consume(p.pk, product)
                    left += 1 if res.ok else 0
                else:
                    res = services.debit(p.pk, product, quantity, operation=Operation.SALE, destination="market:1", key=key,
                                         reference_kind="t", reference_id=key)
                    left += quantity if res.ok else 0
                self.assertIn(res.code, {"OK", "INSUFFICIENT_QUANTITY", "NOT_IN_INVENTORY", "NO_CONSUMPTION_EFFECT",
                                         "INSUFFICIENT_FUNDS"}, (op, res))
                held = sum(InventoryItem.objects.values_list("quantity", flat=True))
                self.assertEqual(held, self._baseline + entered - left)
                self.assertFalse(InventoryItem.objects.filter(quantity__lte=0).exists())
            self.assertEqual(ledger_metrics()["in_circulation"], circulation)
            report = audit_inventory()
            self.assertTrue(report.ok, report.findings)
            self._baseline += entered - left

    def setUp(self):
        super().setUp()
        self._baseline = 0
