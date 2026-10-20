"""Cargos, mural, candidatura, aprovação só pelo Dono, um emprego por jogador, saída (02 §15-16; GD 2026-10-19)."""
from companies import jobs, params
from companies.constants import ApplicationStatus, EventKind, PositionKind, PositionStatus
from companies.models import Application, CompaniesImmutableError, Position, PositionEvent
from skills.services import ensure_skill_rows

from .base import CompanyTestCase


class JobsBase(CompanyTestCase):
    def setUp(self):
        super().setUp()
        self.boss = self.player                      # p1: Dono
        self.worker = self.other                     # p2: candidato
        self.third = self.new_player("p3")
        self.fund(self.third, 500_000)
        self.company = self.found(self.boss, "industrial", "Fábrica", 2_000)

    def open(self, kind="worker", salary=2_000, requirements=None, company=None, player=None):
        res = jobs.open_position((player or self.boss).pk, company or self.company, kind, salary, requirements)
        self.assertTrue(res.ok, res)
        return res.detail["position"]

    def apply(self, player, position):
        res = jobs.apply_to_position(player.pk, position)
        self.assertTrue(res.ok, res)
        return res.detail["application"]

    def hire(self, player, position=None, **kw):
        position = position or self.open(**kw)
        application = self.apply(player, position)
        res = jobs.approve_application(self.boss.pk, application)
        self.assertTrue(res.ok, res)
        return position, application

    def set_skill(self, player, skill, level):
        from skills.models import PlayerSkill
        ensure_skill_rows(player)
        PlayerSkill.objects.filter(player=player, skill=skill).update(level=level)


class OpenAndCloseTests(JobsBase):
    def test_the_owner_opens_a_vacancy_that_appears_in_the_public_mural_with_everything_a_player_needs(self):
        position = self.open("engineer", 3_000, {"intelligence": 5})
        row = jobs.mural()[0]
        self.assertEqual((row["position"], row["company_name"], row["company_type"], row["stars"], row["kind"], row["salary"],
                          row["relevant_skill"], row["requirements"]),
                         (position, "Fábrica", "industrial", params.INITIAL_STARS, "engineer", 3_000, "intelligence",
                          {"intelligence": 5}))
        self.assertEqual((row["requirements_met"], row["applied"]), (None, None))      # sem observador: desconhecido, não False
        p = Position.objects.get(pk=position)
        self.assertEqual((p.status, p.holder_id), (PositionStatus.OPEN.value, None))
        self.assertEqual(PositionEvent.objects.get(position=p).kind, EventKind.POSITION_OPENED.value)

    def test_only_the_owner_opens_and_the_kind_must_be_one_the_company_type_may_hire(self):
        r = jobs.open_position(self.worker.pk, self.company, "worker", 1_000, {})
        self.assertRefused(r, "NOT_OWNER")
        self.assertRefused(jobs.open_position(self.boss.pk, 10 ** 9, "worker", 1_000, {}), "COMPANY_NOT_FOUND")
        self.assertRefused(jobs.open_position(self.boss.pk, "x", "worker", 1_000, {}), "INVALID_PARAMS")
        self.assertRefused(jobs.open_position(self.boss.pk, self.company, "owner", 1_000, {}), "INVALID_POSITION_KIND")
        self.assertRefused(jobs.open_position(self.boss.pk, self.company, "king", 1_000, {}), "INVALID_POSITION_KIND")
        self.assertRefused(jobs.open_position(self.boss.pk, self.company, "salesperson", 1_000, {}), "POSITION_KIND_NOT_ALLOWED")
        retail = self.found(self.boss, "retail", "Loja", 0)
        self.assertRefused(jobs.open_position(self.boss.pk, retail, "worker", 1_000, {}), "POSITION_KIND_NOT_ALLOWED")
        self.assertTrue(jobs.open_position(self.boss.pk, retail, "salesperson", 1_000, {}).ok)

    def test_salary_and_requirements_are_validated(self):
        for salary in (0, -1, True, "10", 1.5, None, 10 ** 13):
            self.assertRefused(jobs.open_position(self.boss.pk, self.company, "worker", salary, {}), "INVALID_SALARY")
        for req in ({"strength": 1}, {"physical": -1}, {"physical": 1.5}, {"physical": True}, {"physical": 10 ** 7}, [1], "x"):
            self.assertRefused(jobs.open_position(self.boss.pk, self.company, "worker", 1_000, req), "INVALID_REQUIREMENTS")
        self.assertTrue(jobs.open_position(self.boss.pk, self.company, "worker", 1_000, {"physical": 0, "charisma": 3}).ok)
        self.assertEqual(Position.objects.exclude(kind="owner").count(), 1)          # as recusas não deixaram vaga

    def test_closing_removes_it_from_the_mural_and_cancels_pending_applications_with_a_trail(self):
        position = self.open()
        a1, a2 = self.apply(self.worker, position), self.apply(self.third, position)
        self.assertRefused(jobs.close_position(self.worker.pk, position), "NOT_OWNER")
        res = jobs.close_position(self.boss.pk, position)
        self.assertEqual((res.ok, res.detail["cancelled_applications"]), (True, 2))
        self.assertEqual(jobs.mural(), [])
        for a in (a1, a2):
            app = Application.objects.get(pk=a)
            self.assertEqual((app.status, app.reason), (ApplicationStatus.CANCELLED.value, "position_closed"))
        self.assertRefused(jobs.close_position(self.boss.pk, position), "POSITION_NOT_OPEN")
        self.assertRefused(jobs.apply_to_position(self.worker.pk, position), "POSITION_NOT_OPEN")
        kinds = [e.kind for e in PositionEvent.objects.filter(position_id=position)]
        self.assertEqual(kinds.count(EventKind.CANCELLED.value), 2)
        self.assertEqual(kinds[-1], EventKind.POSITION_CLOSED.value)

    def test_the_mural_filters_and_paginates(self):
        other = self.found(self.boss, "matrix", "Fazenda", 0)
        ids = [self.open(), self.open("lawyer"), self.open(company=other)]
        self.assertEqual([r["position"] for r in jobs.mural()], ids)
        self.assertEqual([r["position"] for r in jobs.mural(company_id=other)], ids[2:])
        self.assertEqual([r["position"] for r in jobs.mural(kind="lawyer")], ids[1:2])
        self.assertEqual([r["position"] for r in jobs.mural(after=ids[0], limit=1)], ids[1:2])


class ApplicationTests(JobsBase):
    def test_applying_checks_the_skill_requirements_and_reports_what_is_missing(self):
        position = self.open("engineer", 3_000, {"intelligence": 50, "physical": 5})
        self.set_skill(self.worker, "physical", 5)
        res = jobs.apply_to_position(self.worker.pk, position)
        self.assertRefused(res, "REQUIREMENTS_NOT_MET")
        detail = {d["skill"]: d for d in res.detail["requirements"]["details"]}
        self.assertEqual((detail["intelligence"]["met"], detail["physical"]["met"]), (False, True))
        self.assertEqual(detail["intelligence"]["shortfall"], "50.000000")
        self.set_skill(self.worker, "intelligence", 50)
        self.assertTrue(jobs.apply_to_position(self.worker.pk, position).ok)

    def test_the_mural_tells_the_viewer_whether_they_meet_each_requirement(self):
        self.open("engineer", 3_000, {"intelligence": 50})
        self.open("worker", 1_000, {})
        rows = jobs.mural(self.worker.pk)
        self.assertEqual([(r["requirements_met"], r["applied"]) for r in rows], [(False, False), (True, False)])
        self.assertEqual(rows[0]["requirements_detail"]["details"][0]["shortfall"], "50.000000")
        self.apply(self.worker, rows[1]["position"])
        self.assertEqual([r["applied"] for r in jobs.mural(self.worker.pk)], [False, True])

    def test_a_duplicate_application_is_refused_and_a_withdrawn_one_can_be_redone(self):
        position = self.open()
        a = self.apply(self.worker, position)
        self.assertRefused(jobs.apply_to_position(self.worker.pk, position), "ALREADY_APPLIED")
        self.assertRefused(jobs.withdraw_application(self.third.pk, a), "NOT_APPLICANT")
        self.assertTrue(jobs.withdraw_application(self.worker.pk, a).ok)
        self.assertRefused(jobs.withdraw_application(self.worker.pk, a), "APPLICATION_NOT_PENDING")
        self.assertTrue(jobs.apply_to_position(self.worker.pk, position).ok)
        self.assertEqual(Application.objects.filter(position_id=position).count(), 2)

    def test_unknown_or_malformed_ids_are_refused_without_effect(self):
        for fn in (jobs.apply_to_position, jobs.close_position, jobs.dismiss):
            self.assertRefused(fn(self.boss.pk, "x"), "INVALID_PARAMS")
            self.assertRefused(fn(self.boss.pk, 10 ** 9), "POSITION_NOT_FOUND")
        for fn in (jobs.withdraw_application, jobs.approve_application, jobs.reject_application):
            self.assertRefused(fn(self.boss.pk, None), "INVALID_PARAMS")
            self.assertRefused(fn(self.boss.pk, 10 ** 9), "APPLICATION_NOT_FOUND")
        self.assertRefused(jobs.apply_to_position(10 ** 9, 1), "PLAYER_NOT_FOUND")
        self.assertEqual(Application.objects.count(), 0)


class ApprovalTests(JobsBase):
    def test_only_the_owner_decides_nobody_else_not_even_the_employee_of_the_company(self):
        position = self.open()
        a = self.apply(self.worker, position)
        for who in (self.worker, self.third):
            self.assertRefused(jobs.approve_application(who.pk, a), "NOT_OWNER")
            self.assertRefused(jobs.reject_application(who.pk, a), "NOT_OWNER")
        self.hire(self.third)
        self.assertRefused(jobs.approve_application(self.third.pk, a), "NOT_OWNER")        # empregado não é "pessoa autorizada"
        self.assertEqual(Application.objects.get(pk=a).status, ApplicationStatus.PENDING.value)

    def test_approving_fills_the_position_records_the_event_and_cancels_the_other_applicants(self):
        position = self.open(salary=2_500)
        a1, a2 = self.apply(self.worker, position), self.apply(self.third, position)
        res = jobs.approve_application(self.boss.pk, a1)
        self.assertEqual((res.ok, res.detail["employee"], res.detail["salary"]), (True, self.worker.pk, 2_500))
        p = Position.objects.get(pk=position)
        self.assertEqual((p.status, p.holder_id), (PositionStatus.FILLED.value, self.worker.pk))
        self.assertEqual(Application.objects.get(pk=a1).status, ApplicationStatus.APPROVED.value)
        other = Application.objects.get(pk=a2)
        self.assertEqual((other.status, other.reason), (ApplicationStatus.CANCELLED.value, "position_filled"))
        self.assertEqual(jobs.mural(), [])
        self.assertEqual(jobs.current_job(self.worker.pk).pk, position)
        self.assertRefused(jobs.approve_application(self.boss.pk, a1), "APPLICATION_NOT_PENDING")

    def test_rejecting_keeps_the_vacancy_open(self):
        position = self.open()
        a = self.apply(self.worker, position)
        self.assertTrue(jobs.reject_application(self.boss.pk, a).ok)
        self.assertEqual(Application.objects.get(pk=a).status, ApplicationStatus.REJECTED.value)
        self.assertEqual([r["position"] for r in jobs.mural()], [position])
        self.assertRefused(jobs.reject_application(self.boss.pk, a), "APPLICATION_NOT_PENDING")

    def test_one_hired_job_per_player_other_pending_applications_are_cancelled_on_hire(self):
        other = self.found(self.third, "matrix", "Fazenda", 0)
        p1 = self.open()
        p2 = self.open(company=other, player=self.third)
        a1, a2 = self.apply(self.worker, p1), self.apply(self.worker, p2)
        self.assertTrue(jobs.approve_application(self.boss.pk, a1).ok)
        loser = Application.objects.get(pk=a2)
        self.assertEqual((loser.status, loser.reason), (ApplicationStatus.CANCELLED.value, "hired_elsewhere"))
        self.assertRefused(jobs.approve_application(self.third.pk, a2), "APPLICATION_NOT_PENDING")
        self.assertEqual(Position.objects.get(pk=p2).status, PositionStatus.OPEN.value)

    def test_an_employed_player_may_apply_but_is_only_hired_after_leaving(self):
        other = self.found(self.third, "matrix", "Fazenda", 0)
        self.hire(self.worker)
        p2 = self.open(company=other, player=self.third)
        a = jobs.apply_to_position(self.worker.pk, p2).detail["application"]
        res = jobs.approve_application(self.third.pk, a)
        self.assertRefused(res, "ALREADY_EMPLOYED")
        self.assertTrue(jobs.resign(self.worker.pk).ok)
        self.assertTrue(jobs.approve_application(self.third.pk, a).ok)

    def test_the_owner_position_does_not_count_so_an_owner_can_work_for_someone_else(self):
        other = self.found(self.third, "matrix", "Fazenda", 0)
        position = self.open(company=other, player=self.third)
        a = self.apply(self.boss, position)                       # o Dono da Fábrica vira funcionário da Fazenda (02 §16)
        self.assertTrue(jobs.approve_application(self.third.pk, a).ok)
        self.assertEqual(jobs.current_job(self.boss.pk).company_id, other)
        self.assertEqual(Position.objects.filter(holder=self.boss).count(), 2)       # Dono + funcionário

    def test_the_database_itself_refuses_two_jobs_for_one_player(self):
        from django.db import IntegrityError, transaction
        self.hire(self.worker)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Position.objects.create(company_id=self.company, kind="worker", salary=1, holder=self.worker,
                                    status=PositionStatus.FILLED.value, created_at=1)

    def test_requirements_are_checked_again_at_approval(self):
        position = self.open(requirements={"physical": 10})
        self.set_skill(self.worker, "physical", 10)
        a = self.apply(self.worker, position)
        self.set_skill(self.worker, "physical", 1)                  # (cenário artificial: a skill caiu depois de candidatar)
        res = jobs.approve_application(self.boss.pk, a)
        self.assertRefused(res, "REQUIREMENTS_NOT_MET")
        self.assertEqual(Application.objects.get(pk=a).status, ApplicationStatus.PENDING.value)


class LeavingTests(JobsBase):
    def test_resigning_closes_the_position_and_leaves_the_trail(self):
        position, _ = self.hire(self.worker)
        self.assertRefused(jobs.resign(self.third.pk), "NOT_EMPLOYED")
        self.assertTrue(jobs.resign(self.worker.pk).ok)
        p = Position.objects.get(pk=position)
        self.assertEqual((p.status, p.holder_id), (PositionStatus.CLOSED.value, None))
        self.assertIsNone(jobs.current_job(self.worker.pk))
        self.assertEqual(PositionEvent.objects.filter(position=p).last().kind, EventKind.RESIGNED.value)
        self.assertRefused(jobs.resign(self.worker.pk), "NOT_EMPLOYED")

    def test_the_owner_dismisses_an_employee_but_never_the_owner_position(self):
        position, _ = self.hire(self.worker)
        owner_position = Position.objects.get(company_id=self.company, kind="owner").pk
        self.assertRefused(jobs.dismiss(self.worker.pk, position), "NOT_OWNER")
        self.assertRefused(jobs.dismiss(self.boss.pk, owner_position), "CANNOT_DISMISS_OWNER")
        res = jobs.dismiss(self.boss.pk, position)
        self.assertEqual((res.ok, res.detail["employee"]), (True, self.worker.pk))
        self.assertRefused(jobs.dismiss(self.boss.pk, position), "POSITION_NOT_FILLED")
        event = PositionEvent.objects.filter(position_id=position).last()
        self.assertEqual((event.kind, event.subject, event.actor), (EventKind.DISMISSED.value, self.worker.pk, self.boss.pk))
        self.assertEqual(Position.objects.get(company_id=self.company, kind="owner").holder_id, self.boss.pk)

    def test_after_leaving_the_player_can_be_hired_again_elsewhere(self):
        self.hire(self.worker)
        jobs.resign(self.worker.pk)
        self.hire(self.worker)
        self.assertIsNotNone(jobs.current_job(self.worker.pk))


class TrailTests(JobsBase):
    def test_events_and_pending_lists_are_immutable_or_private(self):
        position, application = self.hire(self.worker)
        event = PositionEvent.objects.first()
        event.kind = "x"
        with self.assertRaises(CompaniesImmutableError):
            event.save()
        with self.assertRaises(CompaniesImmutableError):
            event.delete()
        extra = self.open()
        self.apply(self.third, extra)
        self.assertEqual(len(jobs.pending_applications(self.boss.pk, self.company)), 1)
        self.assertEqual(jobs.pending_applications(self.worker.pk, self.company), [])      # só quem decide as vê

    def test_the_provisional_position_to_skill_mapping_is_complete_and_auditable(self):
        self.assertEqual(set(params.RELEVANT_SKILL), set(PositionKind))
        self.assertEqual(jobs.relevant_skill("worker").value, "physical")
        self.assertEqual(jobs.relevant_skill("salesperson").value, "charisma")
