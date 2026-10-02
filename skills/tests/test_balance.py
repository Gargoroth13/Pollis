from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from skills.balance import get_skill_balance

from .base import D


class SkillBalanceTests(SimpleTestCase):
    def test_values_defined_by_the_documents(self):
        b = get_skill_balance()
        self.assertEqual((b.specialization_floor_ratio, b.specialization_recovery_multiplier), (D("0.5"), D("1.5")))  # 02 §13

    def test_open_decisions_default_to_the_most_neutral_setting(self):
        b = get_skill_balance()
        self.assertEqual((b.progress_curve, b.production_curve, b.qol_source), ("none", "none", "base"))

    def test_work_gain_is_smaller_than_study_gain_by_default(self):
        b = get_skill_balance()
        for skill in b.base_gain["study"]:
            self.assertLess(b.base_gain["work"][skill], b.base_gain["study"][skill])      # 01 §1.2

    def test_no_default_for_leisure_the_design_defines_none(self):
        self.assertNotIn("leisure", get_skill_balance().base_gain)

    @override_settings(POLIS_SKILLS_BALANCE={"base_gain": {"work": {"physical": 0.2}}, "initial_level": 3})
    def test_overrides_merge_by_activity_and_skill(self):
        b = get_skill_balance()
        self.assertEqual((b.base_gain["work"]["physical"], b.base_gain["work"]["charisma"]), (D("0.2"), D("0.5")))
        self.assertEqual((b.initial_level, b.base_gain["study"]["physical"]), (3, 1))

    @override_settings(POLIS_SKILLS_BALANCE={"base_gain": {"leisure": {"charisma": 2}}})
    def test_a_new_activity_can_be_configured_without_code_changes(self):
        self.assertEqual(get_skill_balance().base_gain["leisure"]["charisma"], 2)

    def test_invalid_overrides_fail_loudly(self):
        bad = [
            {"nope": 1},
            {"initial_level": -1},
            {"base_gain": {"work": {"industry": 1}}},                        # só existem 3 skills
            {"base_gain": {"work": {"physical": 1}}},                        # trabalho não pode ser >= estudo (01 §1.2)
            {"base_gain": {"work": {"physical": -1}}},
            {"qol_source": "current"},
            {"progress_curve": "inventada"},
            {"salary_cap_multiplier": -1},
            {"specialization_floor_ratio": 2},
            {"specialization_recovery_multiplier": "0.5"},                   # recuperação é MAIS rápida
            {"specialization_decay_per_day": -1},
        ]
        for overrides in bad:
            with override_settings(POLIS_SKILLS_BALANCE=overrides):
                with self.assertRaises(ImproperlyConfigured, msg=str(overrides)):
                    get_skill_balance()
