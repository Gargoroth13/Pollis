"""Escolas (design/03 §2-§6): escola pública do bairro, matrícula inicial, capacidade e troca de escola."""
from django.db import IntegrityError, transaction

from players import registry
from schools import services
from schools.audit import audit_schools
from schools.constants import EnrollmentEnd, SchoolKind
from schools.models import Enrollment, QualityDay, School

from .base import SchoolBase


class InitialSchoolTests(SchoolBase):
    def test_a_new_player_is_enrolled_in_the_public_school_of_the_neighborhood_and_the_school_exists_once(self):
        enrollment = services.current_enrollment(self.player.pk)
        self.assertEqual((enrollment.school_id, enrollment.started_at, enrollment.ended_at), (self.home.pk, self.clk.now(), None))
        self.assertEqual((self.home.kind, self.home.stars, self.home.owner_id, self.home.initial, self.home.materials),
                         ("public", 1, None, True, 0))
        second = self.new_player("p2")                                          # mesmo bairro (capital): mesma escola, uma só
        self.assertEqual(services.current_enrollment(second.pk).school_id, self.home.pk)
        self.assertEqual(School.objects.count(), 1)
        self.assertEqual(services.enrolled_count(self.home.pk), 2)
        self.assertEqual(QualityDay.objects.filter(school=self.home).count(), 1)         # a linha do dia de criação (retrato 0)

    def test_the_initial_enrollment_is_never_refused_even_without_seats_and_the_overflow_is_visible(self):
        self.provide_residences(0)
        for n in range(3):
            self.new_player(f"x{n}")
        status = services.school_status(self.home.pk)
        self.assertEqual((status["seats"], status["enrolled"], status["free_seats"], status["over_capacity"]), (0, 4, -4, True))

    def test_with_several_public_schools_the_first_one_with_a_free_seat_is_chosen_and_private_schools_never(self):
        self.provide_residences(1)                                              # 1 × 1,5 = 1 vaga por escola
        second = self.make_school(SchoolKind.PUBLIC, name="Pública 2")
        self.make_school(SchoolKind.PRIVATE, name="Particular")
        a = self.new_player("a")                                                # a casa do p1 já tem 1 aluno (cheia)
        self.assertEqual(services.current_enrollment(a.pk).school_id, second.pk)
        b = self.new_player("b")                                                # todas cheias: vai para a de origem
        self.assertEqual(services.current_enrollment(b.pk).school_id, self.home.pk)

    def test_ensure_public_school_is_idempotent_and_the_database_allows_one_origin_school_per_neighborhood(self):
        self.assertEqual(services.ensure_public_school(self.nb).pk, self.home.pk)
        self.assertEqual(School.objects.filter(neighborhood_id=self.nb).count(), 1)
        other = self.other_neighborhood()
        created = services.ensure_public_school(other)
        self.assertEqual((created.neighborhood_id, created.initial, created.kind), (other, True, "public"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            School.objects.create(neighborhood_id=self.nb, kind="public", name="x", stars=1, initial=True, created_at=0)


class CreateSchoolTests(SchoolBase):
    def test_validation_and_ownership_rules(self):
        ok = dict(neighborhood_id=self.nb, kind=SchoolKind.PUBLIC, name="Escola X")
        self.assertRefused(services.create_school(**{**ok, "neighborhood_id": 0}), "INVALID_PARAMS")
        self.assertRefused(services.create_school(**{**ok, "neighborhood_id": True}), "INVALID_PARAMS")
        self.assertRefused(services.create_school(**{**ok, "kind": "public"}), "INVALID_PARAMS")
        for bad in ("", "   ", "x" * 81, None, 7):
            self.assertRefused(services.create_school(**{**ok, "name": bad}), "INVALID_NAME")
        for bad in (0, 6, -1, True, "3", 2.5):
            self.assertRefused(services.create_school(**ok, stars=bad), "INVALID_STARS")
        self.assertRefused(services.create_school(**ok, owner_id=self.player.pk), "OWNER_NOT_ALLOWED")
        self.assertRefused(services.create_school(**{**ok, "kind": SchoolKind.PRIVATE}), "OWNER_REQUIRED")
        self.assertRefused(services.create_school(**{**ok, "kind": SchoolKind.PRIVATE}, owner_id=10 ** 9), "PLAYER_NOT_FOUND")
        self.assertRefused(services.create_school(**{**ok, "neighborhood_id": 10 ** 9}), "NEIGHBORHOOD_NOT_FOUND")
        self.assertEqual(School.objects.count(), 1)                              # nada foi criado (só a de origem)

    def test_a_private_school_has_an_owner_and_more_than_one_school_may_share_a_neighborhood(self):
        private = self.make_school(SchoolKind.PRIVATE, name="  Colégio Particular  ", stars=3)
        self.assertEqual((private.name, private.owner_id, private.stars, private.initial), ("Colégio Particular", self.player.pk, 3, False))
        self.make_school(SchoolKind.PUBLIC, name="Outra pública")
        self.assertEqual(School.objects.filter(neighborhood_id=self.nb).count(), 3)

    def test_the_database_enforces_owner_kind_and_star_range(self):
        for kwargs in ({"kind": "public", "owner_id": self.player.pk}, {"kind": "private", "owner_id": None},
                       {"kind": "public", "stars": 6}, {"kind": "private", "owner_id": self.player.pk, "initial": True}):
            data = dict(neighborhood_id=self.nb, kind="public", name="x", stars=1, created_at=0, owner_id=None)
            data.update(kwargs)
            with self.assertRaises(IntegrityError), transaction.atomic():
                School.objects.create(**data)


class CapacityTests(SchoolBase):
    def test_without_the_residences_system_capacity_is_unknown_not_zero_and_not_unlimited(self):
        self.assertIsNone(services.residences_in(self.nb))
        self.assertIsNone(services.seats_of(self.home))
        status = services.school_status(self.home.pk)
        self.assertEqual((status["seats"], status["free_seats"], status["over_capacity"]), (None, None, None))
        self.assertIsNone(services.school_status(10 ** 9))

    def test_seats_are_residences_times_the_multiplier_with_the_breakdown(self):
        self.provide_residences(20)
        seats = services.seats_of(self.home)
        self.assertEqual(int(seats.value), 30)                                   # exemplo do 03 §4: 20 residências → 30 alunos
        self.assertEqual([s.key for s in seats.steps], ["neighborhood_residences", "capacity_multiplier"])
        self.provide_residences(21)
        self.assertEqual(services.seat_count(self.home), 31)                     # 31,5: não existe meia vaga
        self.provide_residences(0)
        self.assertEqual(services.seat_count(self.home), 0)                      # zero residências: zero vagas (dado real)

    def test_providers_add_up_and_a_provider_that_does_not_know_is_ignored(self):
        self.provide_residences(10)
        services.register_residence_provider("test_residences_b", lambda n: 6)
        self.addCleanup(services.unregister_residence_provider, "test_residences_b")
        services.register_residence_provider("test_residences_c", lambda n: None)
        self.addCleanup(services.unregister_residence_provider, "test_residences_c")
        self.assertEqual(services.residences_in(self.nb), 16)
        with self.assertRaises(ValueError):
            services.register_residence_provider("test_residences_b", lambda n: 1)


class ChangeSchoolTests(SchoolBase):
    def setUp(self):
        super().setUp()
        self.second = self.make_school(SchoolKind.PUBLIC, name="Pública 2")

    def test_changing_to_another_school_of_the_same_neighborhood_keeps_a_continuous_history(self):
        self.clk.advance(hours=1)
        res = services.change_school(self.player.pk, self.second.pk)
        self.assertTrue(res.ok, res)
        self.assertEqual(services.current_enrollment(self.player.pk).school_id, self.second.pk)
        old, new = Enrollment.objects.order_by("id")
        self.assertEqual((old.ended_at, old.end_reason, new.started_at, new.ended_at), (self.clk.now(), EnrollmentEnd.TRANSFER.value,
                                                                                         self.clk.now(), None))
        self.assertTrue(audit_schools().ok)

    def test_each_refusal_has_a_code_and_changes_nothing(self):
        before = list(Enrollment.objects.values_list("id", "school_id", "ended_at"))
        other = self.make_school(SchoolKind.PUBLIC, neighborhood=self.other_neighborhood(), name="Longe")
        self.assertRefused(services.change_school(self.player.pk, "x"), "INVALID_PARAMS")
        self.assertRefused(services.change_school(True, self.second.pk), "INVALID_PARAMS")
        self.assertRefused(services.change_school(10 ** 9, self.second.pk), "PLAYER_NOT_FOUND")
        self.assertRefused(services.change_school(self.player.pk, 10 ** 9), "SCHOOL_NOT_FOUND")
        self.assertRefused(services.change_school(self.player.pk, self.home.pk), "ALREADY_ENROLLED_HERE")
        self.assertRefused(services.change_school(self.player.pk, other.pk), "SCHOOL_IN_OTHER_NEIGHBORHOOD")
        self.provide_residences(0)
        self.assertRefused(services.change_school(self.player.pk, self.second.pk), "SCHOOL_FULL", seats=0)
        self.assertEqual(list(Enrollment.objects.values_list("id", "school_id", "ended_at")), before)

    def test_a_school_with_a_free_seat_accepts_and_the_last_seat_goes_to_one_player(self):
        other_player = self.new_player("p2")                                     # entra na escola de origem
        self.provide_residences(1)                                               # 1 vaga por escola
        self.assertTrue(services.change_school(self.player.pk, self.second.pk).ok)
        self.assertRefused(services.change_school(other_player.pk, self.second.pk), "SCHOOL_FULL")
        self.assertEqual(services.school_status(self.second.pk)["free_seats"], 0)
        self.assertTrue(audit_schools().ok)

    def test_a_player_without_a_school_cannot_change(self):
        self.audit_schools_at_end = False
        Enrollment.objects.all().delete()
        self.assertRefused(services.change_school(self.player.pk, self.second.pk), "NOT_ENROLLED")

    def test_the_action_registry_uses_the_same_rules(self):
        self.assertIsNotNone(registry.get_descriptor("change_school"))
        res = registry.execute_action(self.player.pk, "change_school", {"school": self.second.pk})
        self.assertTrue(res.ok, res)
        self.assertRefused(registry.execute_action(self.player.pk, "change_school", {"school": self.home.pk, "x": 1}), "INVALID_PARAMS")
        self.assertRefused(registry.execute_action(self.player.pk, "change_school", None), "TARGET_REQUIRED")
        self.assertRefused(registry.execute_action(self.player.pk, "change_school", {"school": self.second.pk}), "ALREADY_ENROLLED_HERE")
        avail = registry.check_action(self.player.pk, "change_school", {"school": self.home.pk})
        self.assertTrue(avail.available, avail)
