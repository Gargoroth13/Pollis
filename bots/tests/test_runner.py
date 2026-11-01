from decimal import Decimal
from unittest import mock

from bots import admin_tools, masking, observation, population, runner, scheduler
from bots.constants import BotStatus, WakeReason
from bots.models import Bot, BotActionLog, BotDecisionLog, BotTickMetric
from bots.policy import Decision, UniformMaskedPolicy
from bots.seeds import derive_seed
from bots.tests.base import BotsBase
from players import registry


class ScriptedPolicy:
    model_version = "scripted_test"

    def __init__(self, *decisions):
        self.decisions, self.calls = list(decisions), []

    def decide(self, observation, mask, rng):
        self.calls.append((observation, mask, rng))
        return self.decisions.pop(0) if self.decisions else None


class SchedulerTests(BotsBase):
    def test_first_evaluations_are_spread_and_reproducible(self):
        bots = [self.make_bot() for _ in range(12)]
        offsets = [b.next_eval_at - b.created_game_at for b in bots]
        self.assertTrue(all(0 <= o <= 3600 for o in offsets))
        self.assertGreater(len(set(offsets)), 6)                          # sem acordar em bloco (21 §21.4)
        other = population.start_run("clone", global_seed=self.run_.global_seed)
        again = [population.create_bot(other, {"archetype": b.archetype, "specialization": b.specialization}) for b in bots[:3]]
        self.assertEqual([b.next_eval_at - b.created_game_at for b in again], offsets[:3])

    def test_due_lists_only_active_bots_whose_time_has_come_most_late_first(self):
        a, b, c = (self.make_bot() for _ in range(3))
        Bot.objects.filter(pk=a.pk).update(next_eval_at=self.clk.now() + 10)
        Bot.objects.filter(pk=b.pk).update(next_eval_at=self.clk.now() - 50)
        Bot.objects.filter(pk=c.pk).update(next_eval_at=self.clk.now() - 10)
        self.assertEqual(scheduler.due(self.clk.now()), [b.pk, c.pk])
        self.assertEqual(scheduler.due(self.clk.now(), limit=1), [b.pk])
        admin_tools.freeze(b.pk)
        admin_tools.retire(c.pk)
        self.assertEqual(scheduler.due(self.clk.now()), [])
        self.assertEqual(scheduler.backlog(self.clk.now()), 0)

    def test_wake_only_anticipates_never_postpones(self):
        bot = self.make_bot()
        Bot.objects.filter(pk=bot.pk).update(next_eval_at=self.clk.now() + 5000)
        self.assertTrue(scheduler.wake(bot.pk, WakeReason.OPPORTUNITY, self.clk.now() + 100))
        b = self.fresh(bot)
        self.assertEqual((b.next_eval_at, b.wake_reason), (self.clk.now() + 100, "opportunity"))
        self.assertFalse(scheduler.wake(bot.pk, WakeReason.PLANNED, self.clk.now() + 9000))
        self.assertEqual(self.fresh(bot).next_eval_at, self.clk.now() + 100)


class EvaluationTests(BotsBase):
    def setUp(self):
        super().setUp()
        self.bot = self.make_bot(archetype="casual")
        Bot.objects.filter(pk=self.bot.pk).update(next_eval_at=self.clk.now())

    def test_a_bot_that_is_not_due_is_not_evaluated_and_gets_no_extra_action(self):
        Bot.objects.filter(pk=self.bot.pk).update(next_eval_at=self.clk.now() + 1)
        pol = ScriptedPolicy(Decision("work"))
        self.assertIsNone(runner.evaluate(self.bot.pk, pol))
        self.assertEqual(pol.calls, [])
        self.assertEqual(BotActionLog.objects.count(), 0)

    def test_one_evaluation_makes_at_most_one_action_and_schedules_the_next(self):
        pol = ScriptedPolicy(Decision("work"), Decision("work"))
        res = runner.evaluate(self.bot.pk, pol)
        self.assertEqual((res["eval"], res["action"], res["acted"]), (1, "work", True))
        self.assertIsNone(runner.evaluate(self.bot.pk, pol))               # imediatamente depois não há nova avaliação
        self.assertEqual(BotActionLog.objects.count(), 1)
        self.assertGreaterEqual(self.fresh(self.bot).next_eval_at, self.clk.now() + 600)

    def test_the_action_goes_through_the_shared_registry_and_has_normal_consequences(self):
        pol = ScriptedPolicy(Decision("work"))
        with mock.patch.object(registry, "execute_action", wraps=registry.execute_action) as spy:
            runner.evaluate(self.bot.pk, pol)
        spy.assert_called_once_with(self.bot.player_id, "work", None)
        log = BotActionLog.objects.get()
        self.assertTrue(log.success, log.detail)
        self.assertGreater(Decimal(log.energy_before), Decimal(log.energy_after))      # a Energia normal foi gasta (04)
        self.assertEqual((log.money_before, log.money_after), (0, 0))

    def test_decision_log_has_everything_required_by_the_design(self):
        pol = ScriptedPolicy(Decision("work", score=0.5, exploration={"epsilon": 0.1}))
        runner.evaluate(self.bot.pk, pol)
        d = BotDecisionLog.objects.get()
        self.assertEqual((d.eval_no, d.model_version, d.game_version, d.goal, d.chosen_action, d.score, d.exploration, d.result_code),
                         (1, "scripted_test", "0.1-dev", "wealth", "work", 0.5, {"epsilon": 0.1}, "OK"))
        self.assertEqual(d.decision_seed, derive_seed(self.bot.seed, "decision", 1))
        self.assertEqual(set(d.observation), observation.ALLOWED_KEYS)
        self.assertIn("work", d.available_actions)
        self.assertIsNone(d.reward)                                           # o reward vem depois, nunca antes da ação (21 §21.17)

    def test_next_observation_is_stored_as_experience_on_the_following_evaluation(self):
        pol = ScriptedPolicy(Decision("work"), Decision("leisure"))
        runner.evaluate(self.bot.pk, pol)
        self.assertIsNone(BotDecisionLog.objects.get(eval_no=1).next_observation)
        self.go(10 * 3600)
        Bot.objects.filter(pk=self.bot.pk).update(next_eval_at=self.clk.now())
        runner.evaluate(self.bot.pk, pol)
        first = BotDecisionLog.objects.get(eval_no=1)
        self.assertEqual(first.next_observation, BotDecisionLog.objects.get(eval_no=2).observation)

    def test_the_policy_receives_only_the_observation_the_mask_and_the_rng(self):
        pol = ScriptedPolicy(None)
        runner.evaluate(self.bot.pk, pol)
        obs, mask, rng = pol.calls[0]
        self.assertEqual(set(obs), observation.ALLOWED_KEYS)
        self.assertTrue(all(set(m) == {"available", "target_required", "code"} for m in mask.values()))
        self.assertNotIn("seed", obs)
        flat = repr(obs) + repr(mask)
        for forbidden in ("goal", "archetype", "personality", "reward", "next_eval", "bot"):
            self.assertNotIn(forbidden, flat)

    def test_an_action_outside_the_mask_is_never_executed(self):
        # Trabalhar sem Energia / ação inexistente: a máscara é lei (21 §21.21)
        pol = ScriptedPolicy(Decision("teleport"), )
        res = runner.evaluate(self.bot.pk, pol)
        self.assertEqual((res["result"], res["acted"]), ("POLICY_ILLEGAL_ACTION", False))
        self.assertEqual(BotActionLog.objects.count(), 0)
        d = BotDecisionLog.objects.get()
        self.assertEqual((d.chosen_action, d.result_code), ("teleport", "POLICY_ILLEGAL_ACTION"))
        self.assertIn("ação fora da máscara", d.exploration["error"])

    def test_a_policy_that_raises_is_recorded_as_an_anomaly_not_hidden(self):
        class Boom:
            model_version = "boom"

            def decide(self, *a):
                raise RuntimeError("falhou")
        with self.assertLogs("bots.runner", "ERROR"):
            res = runner.evaluate(self.bot.pk, Boom())
        self.assertEqual(res["result"], "POLICY_EXCEPTION")
        d = BotDecisionLog.objects.get()
        self.assertIn("RuntimeError: falhou", d.exploration["error"])
        self.assertGreater(self.fresh(self.bot).next_eval_at, self.clk.now())      # continua agendado

    def test_an_execution_that_raises_is_recorded_with_the_error_text(self):
        with mock.patch.object(registry, "execute_action", side_effect=RuntimeError("quebrou")), self.assertLogs("bots.runner", "ERROR"):
            res = runner.evaluate(self.bot.pk, ScriptedPolicy(Decision("work")))
        self.assertEqual((res["result"], res["acted"]), ("EXCEPTION", False))
        log = BotActionLog.objects.get()
        self.assertEqual((log.success, log.code), (False, "EXCEPTION"))
        self.assertIn("quebrou", log.detail["error"])

    def test_a_refused_action_is_a_normal_failed_record(self):
        # Fundar empresa sem alvo → recusada pelo registro normal (TARGET_REQUIRED), registrada como falha
        res = runner.evaluate(self.bot.pk, ScriptedPolicy(Decision("found_company")))
        log = BotActionLog.objects.get()
        self.assertFalse(log.success)
        self.assertEqual(res["acted"], False)
        self.assertGreater(self.fresh(self.bot).next_eval_at, self.clk.now() + 1799)        # sem ação: intervalo ocioso

    def test_frozen_and_retired_bots_are_never_evaluated(self):
        for tool in (admin_tools.freeze, admin_tools.retire):
            bot = self.make_bot()
            Bot.objects.filter(pk=bot.pk).update(next_eval_at=self.clk.now())
            tool(bot.pk)
            self.assertIsNone(runner.evaluate(bot.pk, ScriptedPolicy(Decision("work"))))

    def test_unfreezing_makes_the_bot_eligible_without_giving_extra_actions(self):
        admin_tools.freeze(self.bot.pk)
        self.assertTrue(admin_tools.unfreeze(self.bot.pk))
        b = self.fresh(self.bot)
        self.assertEqual((b.status, b.wake_reason), (BotStatus.ACTIVE.value, "admin"))
        self.assertEqual(runner.evaluate(self.bot.pk, ScriptedPolicy(Decision("work")))["acted"], True)
        self.assertFalse(admin_tools.unfreeze(self.bot.pk))                 # só quem está congelado

    def test_decisions_are_reproducible_from_bot_seed_and_state(self):
        mask = masking.action_mask(self.bot.player_id)
        obs = observation.observe(self.bot.player_id)
        picks = []
        for _ in range(2):
            from bots.seeds import rng_for
            picks.append(UniformMaskedPolicy().decide(obs, mask, rng_for(derive_seed(self.bot.seed, "decision", 1))))
        self.assertEqual(picks[0], picks[1])


class RunDueTests(BotsBase):
    def test_a_pass_evaluates_due_bots_measures_time_and_leaves_the_backlog(self):
        bots = [self.make_bot() for _ in range(5)]
        Bot.objects.update(next_eval_at=self.clk.now())
        m = runner.run_due(self.run_, UniformMaskedPolicy(), limit=3)
        self.assertEqual((m.evaluated, m.backlog_after), (3, 2))
        self.assertGreater(m.real_seconds, 0)
        self.assertGreater(m.db_queries, 10)                              # CLAUDE.md §9: tempo de banco, CPU e RAM medidos por passada
        self.assertGreater(m.db_seconds, 0)
        self.assertGreater(m.rss_mb, 1)
        self.assertGreaterEqual(m.cpu_seconds, 0)
        m2 = runner.run_due(self.run_, UniformMaskedPolicy())
        self.assertEqual((m2.evaluated, m2.backlog_after), (2, 0))
        self.assertEqual(BotTickMetric.objects.count(), 2)
        del bots

    def test_an_infrastructure_failure_in_one_bot_does_not_stop_the_pass(self):
        for _ in range(3):
            self.make_bot()
        Bot.objects.update(next_eval_at=self.clk.now())
        real = observation.observe
        calls = {"n": 0}

        def flaky(pid):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("banco")
            return real(pid)
        with mock.patch.object(observation, "observe", flaky), self.assertLogs("bots.runner", "ERROR"):
            m = runner.run_due(self.run_, UniformMaskedPolicy())
        self.assertEqual((m.evaluated, m.errors), (2, 1))
