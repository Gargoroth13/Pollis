from django.contrib.auth.hashers import is_password_usable

from bots import params, population
from bots.constants import ARCHETYPE_DEFAULTS, Archetype, BotStatus, Goal, Personality, RunStatus, Specialization
from bots.models import Bot, BotRun
from bots.tests.base import BotsBase
from bots import admin_tools
from ledger import services as ledger
from players.models import Player


class RunTests(BotsBase):
    def test_run_records_versions_seed_speed_and_configuration(self):
        run = self.run_
        self.assertEqual((run.target_population, run.creation_interval_real_seconds, run.global_seed, run.status), (20, 60, 7, RunStatus.RUNNING.value))
        self.assertEqual((run.game_version, run.model_version), ("0.1-dev", params.BASELINE_MODEL_VERSION))
        self.assertIsNotNone(run.clock_real_seconds_per_game_day)
        self.assertEqual(run.started_game_at, self.clk.now())
        self.assertEqual(set(run.config["coverage_specializations"]), {s.value for s in Specialization if s is not Specialization.NONE})

    def test_invalid_configuration_is_refused(self):
        for kwargs in ({"target_population": -1}, {"creation_interval_real_seconds": 0}, {"max_creation_burst": 0}, {"coverage_specializations": ["astronaut"]}):
            with self.assertRaises(ValueError):
                population.start_run("x", **kwargs)

    def test_design_defaults(self):
        run = population.start_run("padrão")
        self.assertEqual((run.target_population, run.creation_interval_real_seconds), (1000, 60))        # 21 §21.2

    def test_parameter_table_marks_provisional_values(self):
        table = {r.parameter: r for r in params.parameter_table()}
        self.assertEqual(table["target_population"].status, "DESIGN")
        self.assertEqual(table["eval_idle_seconds"].status, "PROV")


class BotCreationTests(BotsBase):
    def test_a_bot_is_a_normal_player_account_with_an_unusable_password(self):
        bot = self.make_bot(archetype="casual")
        player = Player.objects.get(pk=bot.player_id)
        self.assertFalse(is_password_usable(player.user.password))
        self.assertEqual(player.user.username, f"bot-{self.run_.pk}-1")
        self.assertEqual(player.created_at_game, self.clk.now())
        self.assertEqual((bot.personality, bot.goal), ("casual", "wealth"))

    def test_creating_a_bot_creates_no_money(self):
        before = ledger.balance_of(ledger.player_account(self.player.pk).pk)
        bot = self.make_bot()
        self.assertEqual(ledger.balance_of(ledger.player_account(bot.player_id).pk), 0)
        self.assertEqual(ledger.balance_of(ledger.player_account(self.player.pk).pk), before)

    def test_personality_goal_and_specialization_combine_freely(self):
        bot = self.make_bot(personality="optimizer", goal="presidency", specialization="law")
        self.assertEqual((bot.personality, bot.goal, bot.specialization, bot.archetype), ("optimizer", "presidency", "law", "custom"))

    def test_invalid_profile_values_are_refused(self):
        for bad in ({"personality": "lazy"}, {"goal": "fame"}, {"specialization": "magic"}, {"archetype": "hero"}):
            with self.assertRaises(ValueError):
                self.make_bot(**bad)
        self.assertEqual(Bot.objects.count(), 0)
        self.assertEqual(BotRun.objects.get(pk=self.run_.pk).bots_created, 0)

    def test_the_ten_base_archetypes_follow_the_design_table(self):
        self.assertEqual(len(ARCHETYPE_DEFAULTS), 10)
        self.assertEqual(ARCHETYPE_DEFAULTS[Archetype.POLITICIAN], (Personality.OPTIMIZER, Goal.PRESIDENCY))
        self.assertEqual(ARCHETYPE_DEFAULTS[Archetype.EXPLORER], (Personality.EXPLORER, Goal.DISCOVERY))
        self.assertEqual(ARCHETYPE_DEFAULTS[Archetype.SOCIAL], (Personality.SOCIAL, Goal.ORGANIZATIONS))

    def test_each_bot_has_a_stable_seed_independent_of_other_runs(self):
        a = self.make_bot()
        other = population.start_run("outra", global_seed=7)
        b = population.create_bot(other)
        self.assertEqual(a.seed, b.seed)                                  # mesma seed global e mesmo índice → mesma seed
        c = self.make_bot()
        self.assertNotEqual(a.seed, c.seed)


class CreationRateTests(BotsBase):
    def test_first_bot_is_due_at_once_then_one_per_interval(self):
        self.assertEqual(population.due_creations(self.run_, 1000.0), 1)
        self.assertEqual(population.due_creations(self.run_, 1030.0), 0)
        self.assertEqual(population.due_creations(self.run_, 1060.0), 1)
        self.assertEqual(population.due_creations(self.run_, 1060.0), 0)

    def test_catch_up_after_a_pause_is_capped_by_the_burst_limit(self):
        population.due_creations(self.run_, 1000.0)
        n = population.due_creations(self.run_, 1000.0 + 60 * 50)
        self.assertEqual(n, self.run_.max_creation_burst)

    def test_never_exceeds_the_target_population(self):
        run = population.start_run("pequena", target_population=3, creation_interval_real_seconds=1, global_seed=1)
        total = 0
        for t in range(0, 50):
            total += len(population.step(run, 1000.0 + t))
        self.assertEqual((total, population.active_count(run)), (3, 3))

    def test_reaching_the_target_stops_the_accumulation_of_late_creations(self):
        run = population.start_run("pequena", target_population=1, creation_interval_real_seconds=10, global_seed=1)
        population.step(run, 1000.0)
        population.step(run, 5000.0)                                       # meta atingida há muito tempo
        bots = Bot.objects.filter(run=run).first()
        admin_tools.retire(bots.pk)
        self.assertEqual(len(population.step(run, 5005.0)), 0)             # não cria "atrasados" de uma vez
        self.assertEqual(len(population.step(run, 5010.0)), 1)

    def test_stopped_run_creates_nothing(self):
        admin_tools.stop_run(self.run_.pk)
        self.assertEqual(population.due_creations(self.run_, 10 ** 6), 0)

    def test_creation_rate_is_configurable(self):
        run = population.start_run("rápida", target_population=100, creation_interval_real_seconds=5, global_seed=2)
        population.step(run, 100.0)
        self.assertEqual(len(population.step(run, 115.0)), 3)


class CoverageTests(BotsBase):
    def test_profiles_fill_the_least_covered_specializations_and_archetypes(self):
        for _ in range(16):
            self.make_bot_auto()
        cov = population.coverage(self.run_)
        counts = cov["specialization"].values()
        self.assertLessEqual(max(counts) - min(counts), 1)                  # nenhuma especialização fica para trás
        self.assertLessEqual(max(cov["archetype"].values()) - min(cov["archetype"].values()), 1)

    def make_bot_auto(self):
        return population.create_bot(self.run_)

    def test_gaps_list_the_values_below_the_mean_most_needy_first(self):
        for _ in range(3):
            self.make_bot(archetype="casual", specialization="mining")
        gaps = population.gaps(self.run_)
        self.assertTrue(gaps)
        self.assertEqual(gaps[0]["count"], 0)
        self.assertNotIn(("specialization", "mining"), {(g["dimension"], g["value"]) for g in gaps})
        self.assertNotIn(("archetype", "casual"), {(g["dimension"], g["value"]) for g in gaps})

    def test_profile_choice_is_reproducible_for_the_same_seed_and_state(self):
        a = population.choose_profile(self.run_, 1)
        b = population.choose_profile(self.run_, 1)
        self.assertEqual(a, b)
        other = population.start_run("o", global_seed=8)
        self.assertEqual(population.coverage(other)["archetype"], population.coverage(self.run_)["archetype"])

    def test_retired_bots_leave_the_coverage_but_keep_their_account(self):
        bot = self.make_bot(archetype="casual", specialization="law")
        self.assertEqual(population.coverage(self.run_)["specialization"]["law"], 1)
        self.assertTrue(admin_tools.retire(bot.pk))
        self.assertEqual(population.coverage(self.run_)["specialization"]["law"], 0)
        self.assertTrue(Player.objects.filter(pk=bot.player_id).exists())
        self.assertEqual(BotRun.objects.get(pk=self.run_.pk).bots_removed, 1)
        self.assertFalse(admin_tools.retire(bot.pk))                        # idempotente: não conta duas vezes

    def test_daily_population_snapshot_is_one_per_game_day(self):
        self.make_bot()
        a = population.snapshot_population(self.run_)
        b = population.snapshot_population(self.run_)
        self.assertEqual((a.pk, b.total_active), (b.pk, 1))
        self.go(86400)
        c = population.snapshot_population(self.run_)
        self.assertNotEqual(c.pk, a.pk)


class ScenarioEndowmentTests(BotsBase):
    """21.60 (cenário): a dotação inicial é a MESMA do jogador humano, um lançamento explícito de emissão do cenário ativo; o Bot não recebe nada à parte."""

    audit_at_end = True

    def test_a_bot_receives_exactly_the_player_endowment_of_the_active_scenario(self):
        ledger.create_scenario("dotacao", {"player": 500})
        self.assertTrue(ledger.activate_scenario("dotacao", ["player"]).ok)
        human = self.new_player("humano")
        bot = self.make_bot()
        for pid in (human.pk, bot.player_id):
            self.assertEqual(ledger.balance_of(ledger.player_account(pid).pk), 500)

    def test_a_scenario_without_the_player_line_refuses_bot_creation_instead_of_inventing_money(self):
        ledger.create_scenario("sem-linha", {"player": None})
        res = ledger.activate_scenario("sem-linha", [])
        self.assertTrue(res.ok, res)
        with self.assertRaises(ledger.LedgerRefusal):
            self.make_bot()
        self.assertEqual(Bot.objects.count(), 0)
        self.assertEqual(BotRun.objects.get(pk=self.run_.pk).bots_created, 0)
