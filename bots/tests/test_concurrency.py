"""
Concorrência do Bot Test: dois trabalhadores avaliando o mesmo Bot e duas passadas do Population Controller ao mesmo tempo.
O Bot é travado (`SELECT ... FOR UPDATE`, PostgreSQL) e a avaliação confere o vencimento DENTRO da trava: só uma avaliação acontece (nenhuma ação extra,
21 §21.4). A criação serializa pela linha da execução. Em SQLite o banco serializa as escritas; as propriedades marcadas `CROSS_ROW` só valem em PostgreSQL.
A remoção de uma trava só é detectada parcialmente (temporização): a segunda defesa é a restrição única (`bot_unique_index_per_run`, `botdecision_unique_eval`).
"""
import unittest

from django.db import connection
from django.test import TransactionTestCase

from bots import population, runner
from bots.models import Bot, BotActionLog, BotDecisionLog
from bots.policy import Decision
from core.clock import ManualClock, use_clock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger.tests.test_scenario_concurrency import run_together
from players.tests.base import T0

ON_PG = connection.vendor == "postgresql"
CROSS_ROW = unittest.skipUnless(ON_PG, "ordem entre linhas: só o SELECT ... FOR UPDATE (PostgreSQL) a garante")
ROUNDS = 10


class Work:
    model_version = "scripted"

    def decide(self, observation, mask, rng):
        return Decision("work")


class BotConcurrencyTests(TransactionTestCase):
    def setUp(self):
        generate_world(get_scenario(**SMALL))
        self.clk = ManualClock(T0)
        cm = use_clock(self.clk)
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.run_ = population.start_run("c", target_population=50, creation_interval_real_seconds=1, global_seed=3, max_creation_burst=50)

    def at_clock(self, fn):
        def run():
            with use_clock(self.clk):
                return fn()
        return run

    @CROSS_ROW
    def test_two_workers_evaluating_the_same_bot_produce_exactly_one_evaluation(self):
        for _ in range(ROUNDS):
            bot = population.create_bot(self.run_)
            Bot.objects.filter(pk=bot.pk).update(next_eval_at=self.clk.now())
            jobs = run_together(self.at_clock(lambda: runner.evaluate(bot.pk, Work())), self.at_clock(lambda: runner.evaluate(bot.pk, Work())))
            results = [j.result for j in jobs]
            self.assertEqual(sum(r is not None for r in results), 1, results)
            b = Bot.objects.get(pk=bot.pk)
            self.assertEqual(b.eval_count, 1)
            self.assertEqual(BotDecisionLog.objects.filter(bot=b).count(), 1)
            self.assertEqual(BotActionLog.objects.filter(bot=b).count(), 1)

    @CROSS_ROW
    def test_concurrent_creation_passes_never_exceed_the_slots_or_duplicate_an_index(self):
        population.due_creations(self.run_, 1000.0)           # ancora o relógio de criação
        for r in range(ROUNDS):
            run = population.start_run(f"r{r}", target_population=100, creation_interval_real_seconds=1, global_seed=r, max_creation_burst=100)
            population.due_creations(run, 1000.0)
            jobs = run_together(lambda: population.due_creations(run, 1005.0), lambda: population.due_creations(run, 1005.0))
            self.assertEqual(sorted(j.result for j in jobs), [0, 5])            # 5 criações devidas, concedidas uma única vez
        bots = [population.create_bot(self.run_) for _ in range(3)]
        jobs = run_together(lambda: population.create_bot(self.run_), lambda: population.create_bot(self.run_))
        self.assertEqual(len({b.index for b in Bot.objects.filter(run=self.run_)}), Bot.objects.filter(run=self.run_).count())
        del bots, jobs
