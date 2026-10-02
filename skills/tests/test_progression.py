from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from core.breakdown import Calc
from players.actions import Action
from skills import curves, rules
from skills.balance import get_skill_balance

from .base import CHA, D, INT, PHY, SkillTestCase


class NoCeilingTests(SkillTestCase):
    """01 §1.1, §1.10: as skills crescem infinitamente."""

    def test_pure_formula_never_clamps_even_at_absurd_levels(self):
        bal = get_skill_balance()
        for level in (10 ** 3, 10 ** 12, 10 ** 25, D("1e40")):
            g = rules.skill_gain(D(1), self.qol("1"), D(1), D(level), bal)
            self.assertEqual(g.value, 1)                       # sem teto e, com o padrão, sem queda
            self.assertEqual(g.restricted_by, ())              # nenhum limite restringiu o resultado

    def test_level_keeps_growing_past_any_round_number(self):
        for start in (99, 100, 1_000, 10 ** 6, 10 ** 9):
            self.set_level(INT, start)
            self.act(Action.STUDY)
            self.assertEqual(self.levels()[INT], D(start) + D("0.5"), start)

    def test_hundreds_of_actions_grow_linearly_by_default(self):
        """Com o padrão neutro, N estudos rendem exatamente N × ganho (sem faixas, sem queda)."""
        for _ in range(200):
            self.set_state(burnout=0, burnout_active=False)   # isola o crescimento de skill do Burnout do 04
            self.act(Action.STUDY)
        self.assertEqual(self.levels(), {INT: D(100), PHY: D(100), CHA: D(100)})

    def test_no_artificial_catch_up_between_veterans_and_newcomers(self):
        """01 §3: veteranos não devem ser artificialmente nivelados aos novatos."""
        newbie = self.new_player("newbie")
        self.set_level(INT, 5_000)
        self.act(Action.STUDY)
        self.act(Action.STUDY, player=newbie)
        gain_vet, gain_new = self.levels()[INT] - 5_000, self.levels(newbie)[INT]
        self.assertEqual(gain_vet, gain_new)                   # a diferença de nível se mantém, não é reduzida
        self.assertGreater(self.levels()[INT] - self.levels(newbie)[INT], 4_999)

    def test_database_column_is_not_a_practical_ceiling(self):
        from skills.models import PlayerSkill
        self.assertGreaterEqual(PlayerSkill._meta.get_field("level").max_digits - PlayerSkill._meta.get_field("level").decimal_places, 20)


class DiminishingReturnsExtensionPointTests(SkillTestCase):
    """
    01 §1.5: a fórmula do diminishing returns NÃO está fechada. Estas curvas existem SÓ para provar que o
    ponto de extensão funciona; NENHUMA delas é uma proposta de design nem fica embutida.
    """

    def register_harmonic(self, name="test_dr"):
        curves.register_progress_curve(name, lambda level: Calc("harmonic", D(1) / (1 + level)).result())

    def test_only_the_neutral_curve_is_built_in(self):
        self.assertEqual(curves.progress_curve_names(), ["none"])
        self.assertEqual(curves.production_curve_names(), ["none"])

    def test_a_plugged_curve_reduces_gain_as_level_grows(self):
        self.register_harmonic()
        bal_override = override_settings(POLIS_SKILLS_BALANCE={"progress_curve": "test_dr"})
        with bal_override:
            gains = []
            for _ in range(6):
                before = self.levels()[INT]
                self.act(Action.STUDY)
                gains.append(self.levels()[INT] - before)
        self.assertEqual(gains, sorted(gains, reverse=True))               # cada ganho <= o anterior
        self.assertLess(gains[-1], gains[0])
        self.assertGreater(gains[-1], 0)                                   # nunca zera: continua infinito

    def test_with_a_plugged_curve_growth_is_still_unbounded(self):
        self.register_harmonic()
        with override_settings(POLIS_SKILLS_BALANCE={"progress_curve": "test_dr"}):
            bal = get_skill_balance()
            level = D(0)
            history = []
            for _ in range(3000):
                level += rules.skill_gain(D(1), self.qol("0.5"), D(1), level, bal).value
                history.append(level)
            self.assertTrue(all(b > a for a, b in zip(history, history[1:])))   # estritamente crescente
            self.assertGreater(history[-1], 40)                                  # ~ raiz de N: lento, mas sem teto

    def test_the_breakdown_shows_the_curve_that_was_applied(self):
        self.register_harmonic()
        with override_settings(POLIS_SKILLS_BALANCE={"progress_curve": "test_dr"}):
            g = rules.skill_gain(D(1), self.qol("1"), D(1), D(3), get_skill_balance())
        dr = g.step("diminishing_returns")
        self.assertEqual((dr.amount, g.value), (D("0.25"), D("0.25")))
        self.assertEqual(dr.detail.steps[0].key, "harmonic")

    def test_curve_that_would_stop_progress_is_rejected(self):
        curves.register_progress_curve("test_dr", lambda level: Calc("zero", 0).result())
        with override_settings(POLIS_SKILLS_BALANCE={"progress_curve": "test_dr"}):
            with self.assertRaises(ValueError):
                rules.skill_gain(D(1), self.qol("1"), D(1), D(10), get_skill_balance())

    def test_unknown_curve_is_a_configuration_error(self):
        with override_settings(POLIS_SKILLS_BALANCE={"progress_curve": "inventada"}):
            with self.assertRaises(ImproperlyConfigured):
                get_skill_balance()
        with override_settings(POLIS_SKILLS_BALANCE={"production_curve": "inventada"}):
            with self.assertRaises(ImproperlyConfigured):
                get_skill_balance()

    def test_duplicate_curve_names_rejected(self):
        with self.assertRaises(ValueError):
            curves.register_progress_curve("none", lambda l: Calc("x", 1).result())
