"""Concorrência das Escolas: última vaga, escola de origem única, materiais no limite e ciclo diário repetido. Vale em PG e SQLite."""
import time
from unittest import mock

from django.test import TransactionTestCase

from accounts.models import Usuario
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger.tests.test_scenario_concurrency import run_together
from players.services import create_player
from schools import materials, quality, services
from schools.audit import audit_schools
from schools.constants import SchoolKind
from schools.models import Enrollment, MaterialMovement, QualityDay, School


class SchoolConcurrencyTests(TransactionTestCase):
    def setUp(self):
        generate_world(get_scenario(**SMALL))
        self.players = [create_player(Usuario.objects.create_user(f"s{n}")) for n in range(4)]
        self.home = School.objects.get(initial=True)
        self.addCleanup(services.unregister_residence_provider, "t")

    def make(self, name="Outra", stars=3):
        res = services.create_school(neighborhood_id=self.home.neighborhood_id, kind=SchoolKind.PUBLIC, name=name, stars=stars)
        self.assertTrue(res.ok, res)
        return School.objects.get(pk=res.detail["school"])

    def assertClean(self):
        report = audit_schools()
        self.assertTrue(report.ok, report.findings)

    def test_the_last_seat_goes_to_exactly_one_player(self):
        target = self.make()
        services.register_residence_provider("t", lambda n: 1)             # 1 vaga por escola
        real = services.enrolled_count

        def slow_count(school_id):                                          # alarga a janela entre contar e matricular
            value = real(school_id)
            time.sleep(0.05)
            return value

        with mock.patch.object(services, "enrolled_count", slow_count):
            jobs = run_together(*[lambda p=p: services.change_school(p.pk, target.pk) for p in self.players])
        wins = [j for j in jobs if j.result.ok]
        self.assertEqual(len(wins), 1, [j.result for j in jobs])
        self.assertTrue(all(j.result.code == "SCHOOL_FULL" for j in jobs if not j.result.ok))
        self.assertEqual(services.enrolled_count(target.pk), 1)
        self.assertClean()

    def test_the_same_player_changing_twice_at_once_ends_with_one_active_enrollment_and_a_continuous_history(self):
        a, b = self.make("A"), self.make("B")
        jobs = run_together(*[lambda s=s: services.change_school(self.players[0].pk, s.pk) for s in (a, b, a, b)])
        self.assertGreaterEqual(sum(1 for j in jobs if j.result.ok), 1)
        self.assertEqual(Enrollment.objects.filter(player=self.players[0], ended_at__isnull=True).count(), 1)
        self.assertClean()

    def test_many_simultaneous_requests_for_a_new_neighborhoods_public_school_create_one(self):
        from geography.models import Neighborhood
        other = Neighborhood.objects.exclude(pk=self.home.neighborhood_id).order_by("id").first().pk
        jobs = run_together(*[lambda: services.ensure_public_school(other).pk for _ in range(6)])
        self.assertEqual(len({j.result for j in jobs}), 1)
        self.assertEqual(School.objects.filter(neighborhood_id=other, initial=True).count(), 1)
        self.assertClean()

    def test_simultaneous_purchases_never_exceed_the_limit_and_the_same_key_counts_once(self):
        school = self.make(stars=1)                                           # limite 333
        calls = [lambda n=n: materials.credit_materials(school.pk, 100, key=f"k{n}", reference_kind="t", reference_id=n, origin="t")
                 for n in range(6)]
        jobs = run_together(*calls)
        self.assertEqual(sum(1 for j in jobs if j.result.ok), 3)                 # 3 × 100 ≤ 333 < 4 × 100
        school.refresh_from_db()
        self.assertEqual(school.materials, 300)
        same = run_together(*[lambda: materials.credit_materials(school.pk, 10, key="same", reference_kind="t", reference_id=1, origin="t")
                              for _ in range(4)])
        self.assertTrue(all(j.result.ok for j in same))
        self.assertEqual(MaterialMovement.objects.filter(key="same").count(), 1)
        self.assertClean()

    def test_the_daily_cycle_run_by_many_workers_decays_and_records_once(self):
        school = self.make(stars=3)
        materials.credit_materials(school.pk, 1000, key="b", reference_kind="t", reference_id=1, origin="t")
        from ledger.money import competence_day_of
        from market.rollup import day_bounds
        from core import clock as game_clock
        start = day_bounds(competence_day_of(game_clock.now()) + 1)[0]
        jobs = run_together(*[lambda: quality.run_cycle(start) for _ in range(5)])
        self.assertLessEqual(sum(j.result["schools"] for j in jobs), School.objects.count())     # nenhuma escola processada duas vezes
        self.assertEqual(QualityDay.objects.filter(day=QualityDay.objects.order_by("-day").first().day).count(), School.objects.count())
        self.assertEqual(MaterialMovement.objects.filter(operation="decay").count(), 1)
        school.refresh_from_db()
        self.assertEqual(school.materials, 980)
        self.assertEqual(QualityDay.objects.filter(school=school).count(), 2)
        self.assertClean()
