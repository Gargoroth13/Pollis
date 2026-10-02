from django.test import override_settings

from core.breakdown import Calc
from players import services as player_services
from players.actions import Action
from players.hooks import ActivityContext
from players.services import apply_temporary_effect
from skills import rules, services
from skills.balance import get_skill_balance
from skills.constants import Skill

from .base import CHA, D, HOUR, INT, PHY, SkillTestCase


class GainFormulaTests(SkillTestCase):
    """01 §1.3: ganho_base = QoL_base × qualidade_da_escola × ganho_base_da_atividade."""

    def gain(self, qol, school, base=1, level=0):
        return rules.skill_gain(D(base), self.qol(qol), D(school), D(level), get_skill_balance())

    def test_doc_examples(self):
        self.assertEqual(self.gain("1.0", "1.0").value, D("1.0"))     # QoL 1.0 × escola 1.0 × 1.0 = 1.0
        self.assertEqual(self.gain("0.5", "1.0").value, D("0.5"))     # QoL 0.5 × escola 1.0 × 1.0 = 0.5
        self.assertEqual(self.gain("0.5", "0.5").value, D("0.25"))    # QoL 0.5 × escola 0.5 × 1.0 = 0.25

    def test_breakdown_exposes_every_component(self):
        g = self.gain("0.5", "0.5", base="2")
        self.assertEqual([s.key for s in g.steps], ["activity_base_gain", "qol_base", "school_quality", "diminishing_returns"])
        self.assertEqual([s.amount for s in g.steps], [2, D("0.5"), D("0.5"), 1])
        self.assertEqual(g.step("qol_base").detail.value, D("0.5"))            # de onde veio a QoL (20.6)

    def test_default_diminishing_returns_is_neutral(self):
        for level in (0, 1, 100, 10 ** 9):
            self.assertEqual(self.gain("1", "1", level=level).value, 1)


class ActivityDrivesSkillsTests(SkillTestCase):
    """01 §1.1: a atividade realizada determina quais skills evoluem; o jogador não escolhe."""

    def gains(self, result):
        return result.detail["hooks"]["skills"]["gains"]

    def test_study_develops_all_three_skills(self):
        r = self.act(Action.STUDY)
        self.assertEqual(set(self.gains(r)), {"intelligence", "physical", "charisma"})
        self.assertEqual(self.levels(), {INT: D("0.5"), PHY: D("0.5"), CHA: D("0.5")})   # 1 × QoL 0,5

    def test_work_develops_the_skill_the_job_names(self):
        r = self.act(Action.WORK, activity=ActivityContext(skills=("physical",)))
        self.assertEqual(set(self.gains(r)), {"physical"})
        self.assertEqual(self.levels(), {INT: 0, PHY: D("0.25"), CHA: 0})

    def test_work_without_a_job_skill_develops_nothing(self):
        """O cargo (Empresas) é quem diz qual é a skill relevante; sem isso não há o que desenvolver."""
        r = self.act(Action.WORK)
        self.assertEqual(r.detail["hooks"], {})
        self.assertEqual(self.levels(), {INT: 0, PHY: 0, CHA: 0})

    def test_work_gain_is_smaller_than_study_gain(self):
        """01 §1.2: o ganho do Trabalho é menor que o do estudo."""
        self.act(Action.WORK, activity=ActivityContext(skills=("intelligence",)))
        work = self.levels()[INT]
        other = self.new_player("studier")
        self.act(Action.STUDY, player=other)
        self.assertLess(work, self.levels(other)[INT])

    def test_an_activity_can_depend_on_multiple_skills(self):
        """01 §1.2/§1.9: múltiplas skills quando a atividade realmente exige."""
        r = self.act(Action.WORK, activity=ActivityContext(skills=("intelligence", "charisma")))
        self.assertEqual(list(self.gains(r)), ["intelligence", "charisma"])           # ordem determinística
        self.assertEqual(self.levels(), {INT: D("0.25"), PHY: 0, CHA: D("0.25")})

    def test_leisure_has_no_skill_gain_unless_the_activity_defines_one(self):
        """01 §2: 'quais atividades existem fora de trabalho e estudo e quais skills desenvolvem' está em aberto."""
        self.assertEqual(self.act(Action.LEISURE).detail["hooks"], {})
        with self.assertRaises(ValueError):                      # pediu skill mas o design não define o ganho
            self.act(Action.LEISURE, activity=ActivityContext(skills=("charisma",)))
        self.assertEqual(self.levels()[CHA], 0)                  # e a ação inteira foi desfeita
        self.act(Action.LEISURE, activity=ActivityContext(skills=("charisma",), base_gain={"charisma": D("0.3")}))
        self.assertEqual(self.levels()[CHA], D("0.15"))          # 0,3 × QoL 0,5

    def test_activity_can_override_the_base_gain_per_skill(self):
        self.act(Action.STUDY, activity=ActivityContext(skills=("intelligence", "physical"),
                                                        base_gain={"intelligence": D(4), "physical": D(2)}))
        self.assertEqual(self.levels(), {INT: D(2), PHY: D(1), CHA: 0})

    def test_unknown_skill_is_rejected_and_nothing_changes(self):
        energy = self.state().energy
        with self.assertRaises(ValueError):
            self.act(Action.WORK, activity=ActivityContext(skills=("industry",)))
        self.assertEqual(self.state().energy, 100)               # custo de energia também desfeito (mesma transação)

    def test_negative_base_gain_is_rejected(self):
        with self.assertRaises(ValueError):
            self.act(Action.STUDY, activity=ActivityContext(base_gain={"physical": D(-1)}))

    def test_school_quality_scales_the_gain(self):
        self.act(Action.STUDY, activity=ActivityContext(school_quality=D("0.5")))
        self.assertEqual(self.levels()[INT], D("0.25"))          # 1 × QoL 0,5 × escola 0,5

    def test_structural_qol_raises_the_gain(self):
        from players import qol
        qol.register_qol_base_provider("housing", lambda p, a: D("0.5"))     # QoL Base 1,0
        self.act(Action.STUDY)
        self.assertEqual(self.levels()[INT], D("1.0"))

    def test_gain_explanation_is_returned_with_the_action(self):
        r = self.act(Action.STUDY)
        g = self.gains(r)["physical"]
        self.assertEqual((g["level_before"], g["level_after"]), (0, D("0.5")))
        self.assertEqual(g["gain"].value, D("0.5"))
        self.assertEqual(g["gain"].computed_at, self.clk.now())


class QolSourceTests(SkillTestCase):
    """[ABERTO] 01 §1.3 escreve 'QoL_base'; o 04 distingue QoL Base (estrutural) e Base efetiva (com Burnout)."""

    def test_default_reads_qol_base_literally_so_burnout_does_not_change_the_gain(self):
        self.set_state(burnout=95, burnout_active=False)
        self.act(Action.STUDY)                      # burnout +3 => ainda < 100
        self.assertEqual(self.levels()[INT], D("0.5"))

    @override_settings(POLIS_SKILLS_BALANCE={"qol_source": "base_effective"})
    def test_base_effective_includes_the_burnout_penalty(self):
        self.set_state(burnout=100, burnout_active=True)       # estudo bloqueado em burnout ativo; usa lazer com base explícita
        self.act(Action.LEISURE, activity=ActivityContext(skills=("physical",), base_gain={"physical": D(1)}))
        self.assertEqual(self.levels()[PHY], D("0.4"))          # 1 × (0,5 − penalidade 0,1)

    def test_temporary_effects_never_enter_either_reading(self):
        apply_temporary_effect(self.player.pk, "food", "f", D("0.4"), HOUR)
        self.act(Action.STUDY)
        self.assertEqual(self.levels()[INT], D("0.5"))


class SameRuleForEveryAgentTests(SkillTestCase):
    def test_refused_actions_never_grant_skill(self):
        self.set_state(energy=5)
        r = player_services.perform_action(self.player.pk, Action.STUDY)
        self.assertEqual(r.code, "INSUFFICIENT_ENERGY")
        self.set_state(burnout=100, burnout_active=True)
        self.set_state(energy=100)
        self.assertEqual(player_services.perform_action(self.player.pk, Action.WORK, activity=ActivityContext(skills=("physical",))).code, "BURNOUT_ACTIVE")
        self.assertEqual(self.levels(), {INT: 0, PHY: 0, CHA: 0})

    def test_human_and_bot_get_identical_results(self):
        from accounts.models import Usuario
        bot = self.new_player("bot_07")
        for p in (self.player, bot):
            self.act(Action.STUDY, player=p)
            self.act(Action.WORK, player=p, activity=ActivityContext(skills=("physical",)))
        self.assertEqual(self.levels(), self.levels(bot))

    def test_skills_defines_no_action_of_its_own(self):
        """Não existe 'treinar' nem 'ganhar skill': a skill cresce porque a atividade foi feita."""
        public = [n for n in dir(services) if not n.startswith("_")]
        self.assertFalse([n for n in public if n.startswith(("train", "grant", "award", "perform"))])

    def test_a_failure_AFTER_skills_were_written_undoes_the_whole_action(self):
        """
        Um hook posterior falha depois de o hook de skills já ter GRAVADO o ganho: só a transação atômica de
        perform_action desfaz isso (energia, burnout e skills voltam juntos).
        """
        from players import hooks

        def boom(ctx):
            raise RuntimeError("falha em outro sistema, depois de skills")

        hooks.register_action_hook("zzz_fails_after_skills", boom)       # 'zzz' roda depois de 'skills'
        self.addCleanup(hooks.unregister_action_hook, "zzz_fails_after_skills")
        for activity in (None, ActivityContext(skills=("physical",), specialization_key="product:x")):
            with self.assertRaises(RuntimeError):
                self.act(Action.WORK if activity else Action.STUDY, activity=activity)
        self.assertEqual(self.levels(), {INT: 0, PHY: 0, CHA: 0})
        from skills.models import Specialization
        self.assertFalse(Specialization.objects.filter(player=self.player).exists())
        s = self.state()
        self.assertEqual((s.energy, s.burnout, s.last_work_at), (100, 0, None))

    def test_a_failing_skill_hook_undoes_the_whole_action(self):
        from unittest import mock
        before = self.state().energy
        with mock.patch("skills.services.rules.skill_gain", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.act(Action.STUDY)
        self.assertEqual((self.state().energy, self.state().burnout, self.levels()), (100, 0, {INT: 0, PHY: 0, CHA: 0}))
