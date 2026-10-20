"""Cargos e mural no Action Registry: bots e jogadores usam o mesmo caminho, com as mesmas recusas (CLAUDE.md §5.4)."""
from companies import jobs
from companies.models import Application, Position
from players import registry

from .test_jobs import JobsBase

OPEN = {"company": None, "kind": "worker", "salary_cents": 2_000, "requirements": {}}


class JobRegistryTests(JobsBase):
    def target(self, **kw):
        return {**OPEN, "company": self.company, **kw}

    def test_the_actions_have_stable_descriptors_and_resign_has_no_target(self):
        ids = {d.id: d for d in registry.list_descriptors()}
        for action in ("open_position", "close_position", "apply_position", "withdraw_application", "approve_application",
                       "reject_application", "dismiss_employee"):
            self.assertEqual(ids[action].target, registry.TargetSpec(registry.TARGET_PARAMS, True), action)
        self.assertEqual(ids["resign"].target, registry.TargetSpec(registry.TARGET_NONE, False))
        self.assertEqual(registry.execute_action(self.worker.pk, "resign", {"x": 1}).code, "TARGET_NOT_ALLOWED")

    def test_the_whole_flow_runs_through_the_registry_like_for_a_bot(self):
        opened = registry.execute_action(self.boss.pk, "open_position", self.target())
        self.assertTrue(opened.ok, opened)
        position = opened.detail["position"]
        applied = registry.execute_action(self.worker.pk, "apply_position", {"position": position})
        self.assertTrue(applied.ok, applied)
        approved = registry.execute_action(self.boss.pk, "approve_application", {"application": applied.detail["application"]})
        self.assertTrue(approved.ok, approved)
        self.assertEqual(jobs.current_job(self.worker.pk).pk, position)
        self.assertTrue(registry.execute_action(self.worker.pk, "resign").ok)
        self.assertIsNone(jobs.current_job(self.worker.pk))
        again = registry.execute_action(self.boss.pk, "open_position", self.target())
        closed = registry.execute_action(self.boss.pk, "close_position", {"position": again.detail["position"]})
        self.assertTrue(closed.ok, closed)

    def test_availability_and_execution_give_the_same_refusal(self):
        position = jobs.open_position(self.boss.pk, self.company, "worker", 2_000, {"physical": 99}).detail["position"]
        cases = (
            (self.worker, "open_position", self.target(), "NOT_OWNER"),
            (self.boss, "open_position", self.target(kind="owner"), "INVALID_POSITION_KIND"),
            (self.worker, "apply_position", {"position": position}, "REQUIREMENTS_NOT_MET"),
            (self.worker, "apply_position", {"position": 10 ** 9}, "POSITION_NOT_FOUND"),
            (self.worker, "approve_application", {"application": 10 ** 9}, "APPLICATION_NOT_FOUND"),
            (self.worker, "close_position", {"position": position}, "NOT_OWNER"),
            (self.boss, "dismiss_employee", {"position": position}, "POSITION_NOT_FILLED"),
            (self.worker, "resign", None, "NOT_EMPLOYED"),
        )
        for player, action, target, code in cases:
            check = registry.check_action(player.pk, action, target)
            run = registry.execute_action(player.pk, action, target)
            self.assertEqual((check.available, check.code, run.ok, run.code), (False, code, False, code), (action, code))
        self.assertEqual(Application.objects.count(), 0)
        self.assertEqual(Position.objects.exclude(kind="owner").count(), 1)

    def test_invalid_targets_are_invalid_params_never_ignored(self):
        for action, bad in (("open_position", {"company": self.company}), ("open_position", "x"),
                            ("apply_position", {"position": 1, "extra": 2}), ("apply_position", {"pos": 1}),
                            ("approve_application", {}), ("dismiss_employee", [1])):
            self.assertEqual(registry.execute_action(self.boss.pk, action, bad).code, "INVALID_PARAMS", (action, bad))
            self.assertEqual(registry.check_action(self.boss.pk, action, bad).code, "INVALID_PARAMS", (action, bad))
        self.assertEqual(registry.execute_action(self.boss.pk, "apply_position").code, "TARGET_REQUIRED")

    def test_the_general_availability_without_a_target_is_ok_for_everyone(self):
        for action in ("open_position", "apply_position", "approve_application"):
            self.assertEqual(registry.check_action(self.worker.pk, action).code, "OK")
