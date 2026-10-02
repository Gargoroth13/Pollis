from django.test import override_settings

from skills import curves, rules, services
from skills.balance import get_skill_balance
from skills.rules import SkillRequirement

from core.breakdown import Calc

from .base import CHA, D, INT, PHY, SkillTestCase


class RequirementTests(SkillTestCase):
    """01 §1.9: nível mínimo de uma ou mais skills; reutilizável por cargos e atividades."""

    def check(self, minimums, **levels):
        lv = {INT: D(levels.get("i", 0)), PHY: D(levels.get("f", 0)), CHA: D(levels.get("c", 0))}
        return rules.check_requirements(lv, SkillRequirement.of(minimums))

    def test_single_requirement_boundary_is_inclusive(self):
        self.assertTrue(self.check({"intelligence": 100}, i=100).met)
        self.assertFalse(self.check({"intelligence": 100}, i="99.999999").met)

    def test_doc_example_requires_two_skills_at_once(self):
        """Atividade X: INT ≥ 100 e FIS ≥ 75."""
        req = {"intelligence": 100, "physical": 75}
        self.assertTrue(self.check(req, i=100, f=75).met)
        self.assertFalse(self.check(req, i=500, f=74).met)      # uma skill alta não compensa a outra
        self.assertFalse(self.check(req, i=99, f=500).met)

    def test_details_say_exactly_what_is_missing(self):
        r = self.check({"intelligence": 100, "physical": 75}, i=60, f=80)
        by = {d.skill: d for d in r.details}
        self.assertEqual((by[INT].met, by[INT].shortfall, by[INT].current), (False, 40, 60))
        self.assertEqual((by[PHY].met, by[PHY].shortfall), (True, 0))
        self.assertEqual(r.to_dict()["details"][0], {"skill": "intelligence", "required": "100", "current": "60", "met": False, "shortfall": "40"})

    def test_requirement_accepts_enum_or_string_and_has_a_stable_order(self):
        a = SkillRequirement.of({CHA: 1, "intelligence": 2})
        self.assertEqual([s.value for s, _ in a.minimums], ["intelligence", "charisma"])

    def test_invalid_requirements_are_rejected(self):
        with self.assertRaises(ValueError):
            SkillRequirement.of({"industry": 10})
        with self.assertRaises(ValueError):
            SkillRequirement.of({"physical": -1})

    def test_empty_requirement_is_always_met(self):
        self.assertTrue(self.check({}).met)

    def test_service_reads_the_players_current_levels(self):
        req = SkillRequirement.of({"physical": D("0.5")})
        self.assertFalse(services.meets_requirements(self.player.pk, req).met)
        self.act_study = self.act
        from players.actions import Action
        self.act(Action.STUDY)
        self.assertTrue(services.meets_requirements(self.player.pk, req).met)


class SkillAsMultiplierAndSalaryTests(SkillTestCase):
    """01 §1.6-1.7: pontos de extensão; nenhuma fórmula definitiva foi escolhida."""

    def test_production_multiplier_is_neutral_until_the_design_defines_the_relation(self):
        for level in (0, 1, 100, 10 ** 9):
            self.assertEqual(rules.production_multiplier(D(level), get_skill_balance()).value, 1)

    def test_production_curve_is_pluggable_and_explained(self):
        curves.register_production_curve("test_prod", lambda level: Calc("linear", 1 + level / 100).result())
        with override_settings(POLIS_SKILLS_BALANCE={"production_curve": "test_prod"}):
            m = rules.production_multiplier(D(50), get_skill_balance(), at=7)
        self.assertEqual((m.value, m.computed_at), (D("1.5"), 7))
        self.assertEqual([s.key for s in m.steps], ["neutral_multiplier", "production_curve"])
        self.assertEqual(m.step("production_curve").detail.steps[0].key, "linear")

    def test_a_negative_production_factor_is_rejected(self):
        curves.register_production_curve("test_prod", lambda level: Calc("bad", -1).result())
        with override_settings(POLIS_SKILLS_BALANCE={"production_curve": "test_prod"}):
            with self.assertRaises(ValueError):
                rules.production_multiplier(D(1), get_skill_balance())

    def test_service_feeds_the_players_own_level_into_the_curve(self):
        seen = []
        curves.register_production_curve("test_prod", lambda level: (seen.append(level), Calc("c", 1 + level / 100).result())[1])
        self.set_level(PHY, 40)
        self.set_level(INT, 10)
        with override_settings(POLIS_SKILLS_BALANCE={"production_curve": "test_prod"}):
            self.assertEqual(services.production_multiplier_for(self.player.pk, PHY).value, D("1.4"))
            self.assertEqual(services.production_multiplier_for(self.player.pk, INT).value, D("1.1"))
        self.assertEqual(seen, [40, 10])

    def test_salary_cap_is_skill_times_multiplier(self):
        """01 §1.7: 'Físico 100 × 1.5 = salário máximo de R$150'."""
        c = rules.salary_cap(D(100), get_skill_balance())
        self.assertEqual(c.value, 150)
        self.assertEqual([s.key for s in c.steps], ["skill_level", "salary_multiplier"])

    @override_settings(POLIS_SKILLS_BALANCE={"salary_cap_multiplier": 3})
    def test_salary_multiplier_is_a_parameter_not_a_constant(self):
        """01 §2: o multiplicador NÃO é definitivo (pode virar lei)."""
        self.assertEqual(rules.salary_cap(D(100), get_skill_balance()).value, 300)

    def test_salary_cap_grows_with_the_skill_without_a_ceiling(self):
        self.assertEqual(rules.salary_cap(D(10 ** 9), get_skill_balance()).value, D(15 * 10 ** 8))
