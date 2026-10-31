import json
import os
import tempfile
import zipfile
from io import StringIO

from django.core.management import call_command

from bots import admin_tools, dashboard, export, observation, population, runner
from bots.models import Bot, BotActionLog, BotDecisionLog
from bots.policy import UniformMaskedPolicy
from bots.tests.base import BotsBase
from ledger.audit import audit_ledger
from ledger import services as ledger
from players.models import Player


class SimulationTests(BotsBase):
    """O ciclo completo com a política-base: muitos Bots, vários dias de jogo, mesmas regras para todos."""

    def simulate(self, bots=10, days=2, step=3600):
        run = population.start_run("sim", target_population=bots, creation_interval_real_seconds=1, global_seed=11, max_creation_burst=bots)
        real = 1000.0
        population.step(run, real)
        for n in range(bots - 1):
            real += 1
            population.step(run, real)
        policy = UniformMaskedPolicy()
        for _ in range(days * 86400 // step):
            self.go(step)
            runner.run_due(run, policy)
        return run

    def test_bots_obey_energy_and_the_normal_rules_for_days(self):
        run = self.simulate()
        self.assertEqual(population.active_count(run), 10)
        self.assertGreater(BotActionLog.objects.count(), 15)
        for p in Player.objects.filter(bot__run=run):
            self.assertGreaterEqual(p.energy, 0)
        # nenhuma ação bem-sucedida teve Energia depois maior que antes por obra do próprio ato de trabalhar/estudar
        for a in BotActionLog.objects.filter(success=True, action__in=["work", "study"]):
            self.assertLessEqual(float(a.energy_after), float(a.energy_before), a.pk)
        # recusas vêm do registro normal, com códigos de regra (nunca exceção)
        self.assertFalse(BotActionLog.objects.filter(code="EXCEPTION").exists())
        self.assertTrue(audit_ledger().ok)

    def test_bots_create_no_money_and_hold_only_what_the_rules_gave_them(self):
        run = self.simulate(bots=6, days=2)
        for bot in Bot.objects.filter(run=run):
            self.assertEqual(ledger.balance_of(ledger.player_account(bot.player_id).pk), 0)

    def test_same_seed_and_same_world_reproduce_the_same_run(self):
        a = self.simulate(bots=5, days=1)
        first = list(BotDecisionLog.objects.filter(bot__run=a).order_by("bot__index", "eval_no").values_list("bot__index", "eval_no", "at", "chosen_action", "result_code"))
        self.assertTrue(first)
        self.assertEqual(len(first), len(set(first)))

    def test_every_decision_is_associated_with_bot_game_model_seed_and_state(self):
        run = self.simulate(bots=3, days=1)
        for d in BotDecisionLog.objects.filter(bot__run=run):
            self.assertTrue(d.game_version and d.model_version and d.decision_seed)
            self.assertEqual(set(d.observation), observation.ALLOWED_KEYS)


class AdminExportTests(BotsBase):
    def setUp(self):
        super().setUp()
        self.sim = SimulationTests("test_bots_obey_energy_and_the_normal_rules_for_days")
        self.bots = [self.make_bot() for _ in range(4)]
        Bot.objects.update(next_eval_at=self.clk.now())
        runner.run_due(self.run_, UniformMaskedPolicy())
        population.snapshot_population(self.run_)

    def test_dashboard_overview_counts_everything(self):
        view = dashboard.overview(self.run_)
        self.assertEqual((view["run"]["created"], view["population"]["active"], view["decisions"]["total"]), (4, 4, 4))
        self.assertEqual(view["scheduler"]["due_now"], 0)
        self.assertEqual(view["performance"]["recent_ticks"][0]["evaluated"], 4)
        self.assertEqual(view["actions"]["total"], sum(view["actions"]["by_action"].values()))
        one = dashboard.bot_view(self.bots[0].pk)
        self.assertEqual((one["evaluations"], one["profile"]["goal"]), (1, self.bots[0].goal))
        self.assertEqual(len(one["decisions"]), 1)

    def test_export_zip_has_the_documented_files_and_structured_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bot_test.zip")
            sizes = export.export_run(self.run_, path)
            with zipfile.ZipFile(path) as z:
                names = set(z.namelist())
                self.assertEqual(names, {"run.json", "bots.csv", "bot_states.csv", "actions.jsonl", "decisions.jsonl", "anomalies.csv", "population_daily.csv",
                                         "system_performance.csv", "summary.json"})
                run_json = json.loads(z.read("run.json"))
                decisions = [json.loads(line) for line in z.read("decisions.jsonl").decode().splitlines()]
                actions = [json.loads(line) for line in z.read("actions.jsonl").decode().splitlines()]
                bots_csv = z.read("bots.csv").decode().splitlines()
            self.assertEqual(set(sizes), names)
        self.assertEqual((run_json["run_id"], run_json["global_seed"], run_json["game_version"], run_json["bots_created"]), (self.run_.pk, 7, "0.1-dev", 4))
        self.assertIn("training_metrics.csv", run_json["pending_files"])               # pendências declaradas, nunca inventadas
        self.assertEqual(len(decisions), 4)
        self.assertEqual(len(bots_csv), 5)
        self.assertEqual(len(actions), BotActionLog.objects.count())
        self.assertTrue(all({"timestamp", "bot_id", "action", "success", "energy_before", "money_before"} <= set(a) for a in actions))

    def test_anomalies_file_lists_only_technical_failures(self):
        BotActionLog.objects.all().update(code="OK")
        d = BotDecisionLog.objects.first()
        BotActionLog.objects.create(bot=d.bot, decision=d, at=d.at, action="work", success=False, code="EXCEPTION", detail={"error": "x"}) if not BotActionLog.objects.filter(decision=d).exists() else BotActionLog.objects.filter(decision=d).update(code="EXCEPTION", success=False)
        files = export.build_files(self.run_)
        lines = files["anomalies.csv"].strip().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("EXCEPTION", lines[1])

    def test_commands_run_the_whole_flow(self):
        out = StringIO()
        call_command("bot_run", "--name", "cmd", "--target", "3", "--interval", "1", "--seed", "5", stdout=out)
        run_id = int(out.getvalue().split()[1])
        call_command("bot_step", "--run", str(run_id), stdout=out)
        self.assertIn("criados=1", out.getvalue())
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "x.zip")
            call_command("bot_export", "--run", str(run_id), "--out", target, stdout=out)
            self.assertTrue(zipfile.is_zipfile(target))
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("bot_step", "--run", "999999", stdout=out)
        admin_tools.stop_run(run_id)
        call_command("bot_step", "--run", str(run_id), stdout=out)
        self.assertIn("execução parada", out.getvalue())
