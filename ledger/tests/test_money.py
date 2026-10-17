from decimal import Decimal

from django.test import SimpleTestCase

from ledger import money
from ledger.constants import MAX_AMOUNT


class MoneyTests(SimpleTestCase):
    def test_from_reais_exact(self):
        self.assertEqual(money.from_reais(Decimal("12.34")), 1234)
        self.assertEqual(money.from_reais("0.01"), 1)
        self.assertEqual(money.from_reais(5), 500)

    def test_from_reais_refuses_float_and_sub_centavo(self):
        with self.assertRaises(ValueError):
            money.from_reais(1.5)
        with self.assertRaises(ValueError):
            money.from_reais(Decimal("0.001"))

    def test_amount_problem(self):
        self.assertIsNone(money.amount_problem(1))
        self.assertIsNone(money.amount_problem(MAX_AMOUNT))
        self.assertEqual(money.amount_problem(0), "AMOUNT_NOT_POSITIVE")
        self.assertEqual(money.amount_problem(-5), "AMOUNT_NOT_POSITIVE")
        self.assertEqual(money.amount_problem(MAX_AMOUNT + 1), "AMOUNT_TOO_LARGE")
        for bad in (1.5, "10", Decimal("1"), True, None):
            self.assertEqual(money.amount_problem(bad), "AMOUNT_NOT_IN_CENTAVOS")

    def test_percent_half_even_once(self):
        self.assertEqual(money.percent_of(1005, Decimal("0.1")), 100)     # 100,5 → 100 (par)
        self.assertEqual(money.percent_of(1015, Decimal("0.1")), 102)     # 101,5 → 102 (par)
        self.assertEqual(money.percent_of(10, Decimal("0")), 0)
        with self.assertRaises(ValueError):
            money.percent_of(10, 0.1)

    def test_to_reais(self):
        self.assertEqual(money.to_reais(1234), Decimal("12.34"))

    def test_competence_day_changes_at_local_midnight(self):
        from core.timeline import game_ts
        a = money.competence_day_of(game_ts(2026, 10, 5, 23, 59))
        b = money.competence_day_of(game_ts(2026, 10, 6, 0, 0))
        self.assertEqual(b, a + 1)
