from django.test import override_settings

from players import services as player_services
from players.actions import Action
from players.hooks import ActivityContext
from skills import rules, services
from skills.balance import get_skill_balance
from skills.models import Specialization

from .base import CHA, D, INT, PHY, SkillTestCase

DAY = 86400
WORK_BRICK = ActivityContext(skills=("physical",), specialization_key="product:tijolo")


class SpecializationGainTests(SkillTestCase):
    """02 §13: ganho pelo trabalho em determinada atividade ou produto."""

    def spec(self, key="product:tijolo", player=None):
        return Specialization.objects.get(player=player or self.player, key=key)

    def work(self, **kw):
        return self.act(Action.WORK, activity=kw.get("activity", WORK_BRICK))

    def test_working_in_an_area_develops_that_specialization(self):
        r = self.work()
        s = self.spec()
        self.assertEqual((s.value, s.historic_max), (D(1), D(1)))                       # ganho provisório = 1
        self.assertEqual(r.detail["hooks"]["skills"]["specialization"]["key"], "product:tijolo")

    def test_each_area_has_its_own_value(self):
        self.work()
        self.work(activity=ActivityContext(skills=("physical",), specialization_key="product:cimento"))
        self.work()
        self.assertEqual((self.spec().value, self.spec("product:cimento").value), (D(2), D(1)))

    def test_only_work_develops_specialization(self):
        self.act(Action.STUDY, activity=ActivityContext(specialization_key="product:tijolo"))
        self.assertFalse(Specialization.objects.filter(player=self.player).exists())

    def test_specialization_is_independent_from_skills(self):
        self.work()
        self.assertEqual(self.levels(), {INT: 0, PHY: D("0.25"), CHA: 0})               # skill: ganho do trabalho
        self.assertEqual(self.spec().value, 1)                                         # especialização: própria

    def test_no_key_means_no_specialization(self):
        self.work(activity=ActivityContext(skills=("physical",)))
        self.assertFalse(Specialization.objects.filter(player=self.player).exists())

    def test_invalid_key_is_rejected(self):
        for bad in ("", "x" * 65):
            with self.assertRaises(ValueError):
                self.work(activity=ActivityContext(skills=("physical",), specialization_key=bad))

    def test_gain_has_no_ceiling(self):
        Specialization.objects.create(player=self.player, key="product:tijolo", value=10 ** 6, historic_max=10 ** 6,
                                      last_used_day=rules.day_index(self.clk.now()))
        self.work()
        self.assertEqual(self.spec().value, 10 ** 6 + 1)


# Estes testes atravessam muitos dias: sem comer, o jogador ficaria Crítico/Hospitalizado e o Trabalho seria
# bloqueado (04 §12/§14). A dinâmica de Nutrição é do P0.04 e não é o que se mede aqui, então fica neutralizada.
@override_settings(POLIS_BALANCE={"nutrition_decay_per_cycle": 0})
class SpecializationDecayTests(SkillTestCase):
    """02 §13: decadência diária baixa quando deixa de usar; piso de 50% do máximo histórico."""

    def setUp(self):
        super().setUp()
        self.work()

    def work(self):
        return self.act(Action.WORK, activity=WORK_BRICK)

    def value(self, player=None):
        return Specialization.objects.get(player=player or self.player).value

    def snapshot_value(self):
        return services.get_skill_snapshot(self.player.pk).specializations["product:tijolo"].value

    def test_no_decay_on_the_day_it_was_used_nor_the_day_after(self):
        self.clk.advance(seconds=DAY)                   # dia seguinte: o dia em que foi usada acabou, mas foi USADA
        self.assertEqual(self.snapshot_value(), 1)

    def test_decays_per_full_day_without_use(self):
        self.clk.advance(seconds=2 * DAY)               # o dia D+1 inteiro sem uso
        self.assertEqual(self.snapshot_value(), D("0.9"))
        self.clk.advance(seconds=DAY)
        self.assertEqual(self.snapshot_value(), D("0.8"))

    def test_using_it_every_day_prevents_decay(self):
        for _ in range(10):
            self.clk.advance(seconds=DAY)
            self.work()
        self.assertEqual(self.value(), 11)             # 1 + 10 trabalhos, nenhuma decadência

    def test_never_falls_below_half_of_the_historical_maximum(self):
        self.clk.advance(days=400)
        self.assertEqual(self.snapshot_value(), D("0.5"))
        s = services.get_skill_snapshot(self.player.pk).specializations["product:tijolo"]
        self.assertEqual((s.historic_max, s.floor), (1, D("0.5")))

    def test_floor_follows_the_historical_maximum_not_the_current_value(self):
        for _ in range(9):
            self.work()                                 # chega a 10 (máx histórico 10)
        self.clk.advance(days=800)
        self.assertEqual(self.snapshot_value(), 5)      # 50% de 10

    def test_decay_never_increases_a_value_already_at_or_below_the_floor(self):
        bal = get_skill_balance()
        self.assertEqual(rules.apply_daily_decay(D("0.4"), D(1), bal), D("0.4"))
        self.assertEqual(rules.apply_daily_decay(D("0.5"), D(1), bal), D("0.5"))

    def test_returning_recovers_at_one_and_a_half_times_the_normal_speed(self):
        self.clk.advance(days=5)                        # decai: 1 -> 0,7 (4 dias completos sem uso: D+1..D+4)
        self.assertEqual(self.snapshot_value(), D("0.6"))   # D+1 usada? não: 4 ticks de decadência
        self.work()                                     # abaixo do máximo histórico => recuperação ×1,5
        self.assertEqual(self.value(), D("0.6") + D("1.5"))
        self.assertEqual(Specialization.objects.get(player=self.player).historic_max, D("2.1"))
        self.work()                                     # agora no máximo histórico => velocidade normal
        self.assertEqual(self.value(), D("3.1"))

    def test_recovering_flag_is_exposed(self):
        self.clk.advance(days=3)
        self.assertTrue(services.get_skill_snapshot(self.player.pk).specializations["product:tijolo"].recovering)

    def test_lazy_equivalence_accessing_often_never_changes_the_result(self):
        """04 §22: acessar o jogo a mais não muda a decadência."""
        other = self.new_player("lazy")
        self.act(Action.WORK, player=other, activity=WORK_BRICK)
        for _ in range(40):
            self.clk.advance(seconds=DAY // 2)
            player_services.sync_player(self.player.pk)       # acessa a cada meio dia
        player_services.sync_player(other.pk)                  # o outro só acessa no fim
        self.assertEqual(self.value(), self.value(other))
        self.assertEqual(self.value(), D("0.5"))               # e ambos chegaram ao piso

    @override_settings(POLIS_SKILLS_BALANCE={"specialization_decay_per_day": 0.25, "specialization_floor_ratio": 0.8})
    def test_decay_and_floor_are_parameters(self):
        self.clk.advance(days=30)
        self.assertEqual(self.snapshot_value(), D("0.8"))


class EmergentProfileTests(SkillTestCase):
    """01 §1.1: a especialização 'deve surgir naturalmente das atividades escolhidas'. Só descrição, sem mecânica."""

    def test_profile_of_a_player_with_no_progress(self):
        p = rules.specialization_profile({INT: D(0), PHY: D(0), CHA: D(0)})
        self.assertEqual((p.total, p.leading, p.shares[INT]), (0, (), 0))

    def test_profile_reflects_what_the_player_actually_did(self):
        for _ in range(4):
            self.act(Action.STUDY)
            self.set_state(burnout=0, burnout_active=False)
            self.act(Action.WORK, activity=ActivityContext(skills=("physical",)))
        snap = services.get_skill_snapshot(self.player.pk)
        self.assertEqual(snap.profile.leading, (PHY,))                  # quem trabalhou com Físico se concentrou nele
        self.assertGreater(snap.profile.shares[PHY], snap.profile.shares[INT])
        self.assertEqual(sum(snap.profile.shares.values()), 1)

    def test_ties_report_every_leading_skill(self):
        p = rules.specialization_profile({INT: D(5), PHY: D(5), CHA: D(1)})
        self.assertEqual(p.leading, (INT, PHY))
