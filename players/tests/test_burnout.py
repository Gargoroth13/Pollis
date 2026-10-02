from django.test import override_settings

from players.rules import Action
from players.services import perform_action

from .base import CYCLE, D, HOUR, PlayerTestCase


def act(test, action, **kw):
    return perform_action(test.player.pk, action, **kw)


class BurnoutChangeTests(PlayerTestCase):
    def test_table_work_5_study_3_leisure_minus_10(self):
        """04 §7.1."""
        act(self, Action.WORK)
        self.assertEqual(self.state().burnout, 5)
        act(self, Action.STUDY)
        self.assertEqual(self.state().burnout, 8)
        self.set_state(burnout=30)
        act(self, Action.LEISURE)
        self.assertEqual(self.state().burnout, 20)

    def test_burnout_is_clamped_to_0_100(self):
        act(self, Action.LEISURE)                                       # 0 - 10 => 0
        self.assertEqual(self.state().burnout, 0)
        self.set_state(burnout=98)
        act(self, Action.WORK)                                          # 98 + 5 => 100
        self.assertEqual(self.state().burnout, 100)

    def test_risk_multiplier_scales_gains_but_never_below_one_percent(self):
        r = act(self, Action.WORK, burnout_risk=D("0.5")).detail["burnout_change"]
        self.assertEqual(r.value, D("2.5"))
        r = act(self, Action.WORK, burnout_risk=0).detail["burnout_change"]
        self.assertEqual(r.value, D("0.05"))                            # 5 × 1%
        self.assertEqual(r.step("risk").detail.restricted_by, ("risk_floor",))

    def test_risk_does_not_weaken_the_leisure_reduction(self):
        self.set_state(burnout=40)
        act(self, Action.LEISURE, burnout_risk=D("0.01"))
        self.assertEqual(self.state().burnout, 30)

    def test_change_explanation_is_structured(self):
        r = act(self, Action.STUDY).detail["burnout_change"]
        self.assertEqual([s.key for s in r.steps], ["action_gain", "risk"])
        self.assertEqual(r.step("action_gain").amount, 3)


class BurnoutActiveHysteresisTests(PlayerTestCase):
    def activate(self):
        self.set_state(burnout=95)
        r = act(self, Action.WORK)
        self.assertTrue(r.ok and r.detail["burnout_active"])

    def test_enters_active_exactly_at_100(self):
        self.set_state(burnout=90)
        self.assertFalse(act(self, Action.WORK).detail["burnout_active"])   # 95
        self.assertTrue(act(self, Action.WORK).detail["burnout_active"])    # 100

    def test_work_and_study_blocked_but_leisure_allowed(self):
        """04 §7.3."""
        self.activate()
        self.assertEqual(act(self, Action.WORK).code, "BURNOUT_ACTIVE")
        self.assertEqual(act(self, Action.STUDY).code, "BURNOUT_ACTIVE")
        self.assertTrue(act(self, Action.LEISURE).ok)

    def test_blocked_actions_cost_nothing(self):
        self.activate()
        before = self.state()
        act(self, Action.WORK); act(self, Action.STUDY)
        after = self.state()
        self.assertEqual((after.energy, after.burnout), (before.energy, before.burnout))

    def test_stays_active_until_burnout_reaches_50_inclusive(self):
        self.activate()                                                   # burnout 100
        seen = []
        for _ in range(5):
            act(self, Action.LEISURE)                                     # -10 cada
            seen.append((self.state().burnout, self.state().burnout_active))
        self.assertEqual(seen, [(90, True), (80, True), (70, True), (60, True), (50, False)])

    def test_does_not_flip_inside_the_band(self):
        self.set_state(burnout=70, burnout_active=False)
        self.assertFalse(self.state().burnout_active)                     # 70 sem nunca ter chegado a 100
        self.set_state(burnout=70, burnout_active=True)
        self.assertTrue(self.state().burnout_active)                      # 70 vindo de 100

    def test_work_unblocks_after_leaving_active(self):
        self.activate()
        for _ in range(5):
            act(self, Action.LEISURE)
        self.assertTrue(act(self, Action.WORK).ok)


class BurnoutNaturalRecoveryTests(PlayerTestCase):
    def test_waits_one_hour_after_the_last_work_then_minus_5_per_cycle(self):
        """04 §7.2."""
        self.set_state(burnout=40, last_work_at=self.clk.now())
        self.clk.advance(seconds=HOUR - CYCLE)                            # 50 min
        self.assertEqual(self.state().burnout, 40)                        # ainda esperando
        self.clk.advance(seconds=CYCLE)                                   # 1 h exata: primeiro ciclo de recuperação
        self.assertEqual(self.state().burnout, 35)
        self.clk.advance(seconds=CYCLE)
        self.assertEqual(self.state().burnout, 30)

    def test_working_again_restarts_the_wait(self):
        act(self, Action.WORK)                                            # burnout 5, last_work = T0
        self.clk.advance(seconds=HOUR - CYCLE)
        act(self, Action.WORK)                                            # reinicia a espera; burnout 10
        self.clk.advance(seconds=HOUR - CYCLE)
        self.assertEqual(self.state().burnout, 10)                        # nada recuperou
        self.clk.advance(seconds=CYCLE)
        self.assertEqual(self.state().burnout, 5)

    def test_study_and_leisure_do_not_restart_the_wait(self):
        self.set_state(burnout=40, last_work_at=self.clk.now() - HOUR)
        act(self, Action.STUDY)                                           # +3 => 43; só trabalho conta
        self.clk.advance(seconds=CYCLE)
        self.assertEqual(self.state().burnout, 38)

    def test_never_worked_recovers_immediately(self):
        self.set_state(burnout=40)
        self.clk.advance(seconds=CYCLE)
        self.assertEqual(self.state().burnout, 35)

    def test_clamped_at_zero(self):
        self.set_state(burnout=3)
        self.clk.advance(days=1)
        self.assertEqual(self.state().burnout, 0)

    def test_recovery_continues_during_active_burnout(self):
        """04 §7.3: 'o Burnout continua podendo ser recuperado'."""
        self.set_state(burnout=100, burnout_active=True, last_work_at=self.clk.now() - 2 * HOUR)
        self.clk.advance(seconds=9 * CYCLE)
        s = self.state()
        self.assertEqual((s.burnout, s.burnout_active), (55, True))
        self.clk.advance(seconds=CYCLE)
        s = self.state()
        self.assertEqual((s.burnout, s.burnout_active), (50, False))      # saiu em <= 50

    def test_heavy_work_reaches_active_burnout_and_moderate_work_does_not(self):
        heavy, light = self.player, self.new_player("light")
        reached = None
        for hour in range(1, 48):
            for p, n in ((heavy, 2), (light, 1)):                         # 2 vs 1 trabalho por hora
                for _ in range(n):
                    self.set_state(p, energy=100)
                    perform_action(p.pk, Action.WORK)
            if reached is None and self.snap(heavy).burnout_active:
                reached = hour
            self.clk.advance(seconds=HOUR)
        self.assertIsNotNone(reached)
        self.assertFalse(self.snap(light).burnout_active)


class BurnoutHealthPenaltyTests(PlayerTestCase):
    @override_settings(POLIS_BALANCE={"health_burnout_penalty": 2})
    def test_burnout_health_penalty_only_while_active(self):
        self.set_state(health=50)
        self.assertEqual(self.snap().health_change_per_cycle.value, 5)
        self.set_state(burnout=100, burnout_active=True)
        c = self.snap().health_change_per_cycle
        self.assertEqual((c.value, c.step("penalty:burnout").amount), (3, -2))
