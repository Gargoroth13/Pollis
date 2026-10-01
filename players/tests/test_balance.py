from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from players.balance import get_balance

from .base import D


class DocumentedValuesTests(SimpleTestCase):
    """Os valores marcados [04] não são calibração livre: este teste os trava contra o design."""

    def test_values_defined_by_the_document(self):
        b = get_balance()
        self.assertEqual((b.energy_max, b.energy_cost_work, b.energy_cost_study, b.energy_cost_leisure),
                         (100, 20, 10, 10))                                            # 04 §2.1-2.2
        self.assertEqual((b.energy_regen_per_cycle, b.energy_regen_modifier_cap, b.qol_neutral_point),
                         (5, D("0.10"), 1))                                            # 04 §2.3
        self.assertEqual(b.qol_base_baseline, D("0.5"))                                # 04 §4.1
        self.assertEqual((b.burnout_max, b.burnout_gain_work, b.burnout_gain_study, b.burnout_change_leisure),
                         (100, 5, 3, -10))                                             # 04 §7.1
        self.assertEqual((b.burnout_recovery_per_cycle, b.burnout_recovery_wait_seconds), (5, 3600))  # 04 §7.2
        self.assertEqual((b.burnout_active_enter, b.burnout_active_exit), (100, 50))   # 04 §7.3
        self.assertEqual((b.health_max, b.health_base_recovery_per_cycle), (100, 5))   # 04 §10
        self.assertEqual((b.health_critical_enter, b.health_critical_exit), (20, 30))  # 04 §12
        self.assertEqual((b.nutrition_max, b.nutrition_initial, b.health_initial), (100, 100, 100))  # 04 §15, §24
        self.assertEqual(b.burnout_risk_floor, D("0.01"))                              # 02 §9.2


class OverrideTests(SimpleTestCase):
    @override_settings(POLIS_BALANCE={"nutrition_decay_per_cycle": 2, "energy_regen_qol_sensitivity": 0.5})
    def test_override_from_settings(self):
        b = get_balance()
        self.assertEqual((b.nutrition_decay_per_cycle, b.energy_regen_qol_sensitivity), (2, D("0.5")))

    def test_invalid_overrides_fail_loudly(self):
        bad = [
            {"nope": 1},                                                    # chave desconhecida
            {"health_critical_enter": 40, "health_critical_exit": 30},      # histerese de saúde invertida
            {"health_critical_enter": 30, "health_critical_exit": 30},      # sem folga
            {"burnout_active_enter": 40, "burnout_active_exit": 50},        # histerese de burnout invertida
            {"burnout_risk_floor": 0},                                      # risco nunca pode zerar
            {"burnout_gain_study": 9},                                      # estudo > trabalho contraria 04 §7.1
            {"burnout_change_leisure": 5},                                  # lazer deve reduzir burnout
            {"energy_max": 0},
            {"energy_cost_work": 500},                                      # custo acima do máximo
            {"energy_regen_modifier_cap": 1},
            {"hospitalization_duration_seconds": 0},
        ]
        for overrides in bad:
            with override_settings(POLIS_BALANCE=overrides):
                with self.assertRaises(ImproperlyConfigured, msg=str(overrides)):
                    get_balance()
