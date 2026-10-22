"""Materiais, decaimento e qualidade diária (design/03 §7-§13): o estoque do ciclo anterior define a Qualidade Base do dia."""
from decimal import Decimal

from django.db import IntegrityError, transaction

from ledger.money import competence_day_of
from market.rollup import day_bounds
from players.tests.base import T0
from schools import materials, params, quality
from schools.audit import audit_schools
from schools.constants import SchoolKind
from schools.models import MaterialMovement, QualityDay, SchoolsImmutableError

from .base import SchoolBase

D = Decimal


class MaterialsTests(SchoolBase):
    def credit(self, school, quantity, key="buy:1", **kw):
        return materials.credit_materials(school.pk, quantity, key=key, reference_kind="test", reference_id=key, origin="test", **kw)

    def test_the_limit_per_star_is_the_provisional_line_through_the_documented_example(self):
        self.assertEqual(params.MATERIALS_MAX_PER_STAR, {1: 333, 2: 667, 3: 1000, 4: 1333, 5: 1667})   # 03 §8: 3★ = 1.000
        self.assertEqual(materials.max_materials(3), 1000)

    def test_credit_stores_up_to_the_limit_and_refuses_the_whole_entry_above_it(self):
        school = self.make_school(stars=3)
        self.assertTrue(self.credit(school, 900).ok)
        res = self.credit(school, 101, key="buy:2")
        self.assertRefused(res, "MATERIALS_FULL", limit=1000, stored=900, free=100)
        self.assertTrue(self.credit(school, 100, key="buy:3").ok)
        school.refresh_from_db()
        self.assertEqual(school.materials, 1000)
        self.assertEqual(MaterialMovement.objects.filter(school=school).count(), 2)

    def test_credit_is_idempotent_and_a_different_content_with_the_same_key_conflicts(self):
        school = self.make_school(stars=3)
        self.assertTrue(self.credit(school, 50).ok)
        again = self.credit(school, 50)
        self.assertTrue(again.ok and again.detail["already_applied"])
        self.assertRefused(self.credit(school, 60), "IDEMPOTENCY_CONFLICT")
        other = self.make_school(stars=3, name="Outra")
        self.assertRefused(self.credit(other, 50), "IDEMPOTENCY_CONFLICT")
        school.refresh_from_db()
        self.assertEqual(school.materials, 50)

    def test_invalid_input_changes_nothing(self):
        school = self.make_school(stars=3)
        for bad in (0, -1, True, 1.5, "5", None, 10 ** 9 + 1):
            self.assertRefused(self.credit(school, bad), "INVALID_QUANTITY")
        self.assertRefused(materials.credit_materials(0, 5, key="k", reference_kind="t", reference_id=1, origin="t"), "INVALID_PARAMS")
        self.assertRefused(materials.credit_materials(school.pk, 5, key="", reference_kind="t", reference_id=1, origin="t"), "INVALID_PARAMS")
        self.assertRefused(materials.credit_materials(10 ** 9, 5, key="k", reference_kind="t", reference_id=1, origin="t"), "SCHOOL_NOT_FOUND")
        self.assertEqual(MaterialMovement.objects.count(), 0)

    def test_decay_is_rounded_once_with_half_even(self):
        self.assertEqual([materials.decay_of(n) for n in (0, 1, 25, 75, 1000)], [0, 0, 0, 2, 20])     # 0,5→0 e 1,5→2 (HALF_EVEN)

    def test_the_trail_is_immutable_and_nonsense_is_blocked_by_the_database(self):
        school = self.make_school(stars=3)
        self.credit(school, 10)
        m = MaterialMovement.objects.get()
        m.delta = 5
        with self.assertRaises(SchoolsImmutableError):
            m.save()
        with self.assertRaises(SchoolsImmutableError):
            m.delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            MaterialMovement.objects.filter(pk=m.pk).update(delta=0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(school).objects.filter(pk=school.pk).update(materials=-1)


class DailyCycleTests(SchoolBase):
    def setUp(self):
        super().setUp()
        self.school = self.make_school(stars=3, name="Escola 3★")
        self.day0 = competence_day_of(T0)

    def buy(self, quantity, key):
        res = materials.credit_materials(self.school.pk, quantity, key=key, reference_kind="test", reference_id=key, origin="test")
        self.assertTrue(res.ok, res)

    def row(self, offset):
        return QualityDay.objects.get(school=self.school, day=self.day0 + offset)

    def stock(self):
        self.school.refresh_from_db()
        return self.school.materials

    def test_the_quality_of_a_day_comes_from_the_stock_of_the_previous_cycle_then_the_stock_decays(self):
        self.buy(1000, "b1")                                   # dia 0
        self.midnight_tick(1)
        d1 = self.row(1)
        self.assertEqual((d1.materials_snapshot, d1.base_quality, d1.teacher_bonus, d1.quality), (1000, D(1000), D(0), D(1000)))
        self.assertEqual(self.stock(), 980)                    # 2% de 1.000 sumiram DEPOIS do retrato
        self.midnight_tick(2)
        d2 = self.row(2)
        self.assertEqual((d2.materials_snapshot, d2.quality), (980, D(980)))       # o dia 2 usa o estoque registrado no dia 1
        self.assertEqual(self.stock(), 960)                    # round(19,6) = 20
        self.assertTrue(audit_schools().ok)

    def test_a_purchase_made_after_the_snapshot_only_counts_for_the_next_day(self):
        self.midnight_tick(1)
        self.assertEqual(self.row(1).quality, 0)               # sem materiais no ciclo anterior: qualidade base 0
        self.clk.set(self.clk.now() + 3600)
        self.buy(500, "late")                                  # dia 1, depois da virada
        self.assertEqual(self.row(1).quality, 0)               # a linha do dia 1 não muda (imutável)
        self.midnight_tick(2)
        self.assertEqual(self.row(2).materials_snapshot, 500)

    def test_a_purchase_at_the_exact_second_of_the_turn_belongs_to_the_new_day_regardless_of_order(self):
        self.buy(800, "b1")
        start = day_bounds(self.day0 + 1)[0]
        self.clk.set(start)
        self.buy(200, "edge")                                  # no segundo exato da virada, ANTES do tick
        self.midnight_tick(1)                                  # o relógio vai a 00:05; o ciclo usa o início do dia
        self.assertEqual(self.row(1).materials_snapshot, 800)                       # a compra de 00:00:00 não entra no retrato
        self.assertEqual(self.stock(), 800 + 200 - 16)
        self.assertTrue(audit_schools().ok)

    def test_the_cycle_is_idempotent_and_never_decays_twice(self):
        self.buy(1000, "b1")
        self.midnight_tick(1)
        stock = self.stock()
        again = quality.run_cycle(day_bounds(self.day0 + 1)[0])
        self.assertEqual((again["schools"], again["decayed"]), (0, 0))
        self.assertEqual(self.stock(), stock)
        self.assertEqual(QualityDay.objects.filter(school=self.school).count(), 2)

    def test_without_new_materials_the_quality_falls_back_with_decay_down_to_zero(self):
        self.buy(30, "b1")
        for day in range(1, 8):
            self.midnight_tick(day)
        values = [self.row(d).materials_snapshot for d in range(1, 8)]
        self.assertEqual(values[0], 30)
        self.assertTrue(all(a >= b for a, b in zip(values, values[1:])), values)     # nunca sobe sem compra
        self.assertGreaterEqual(self.stock(), 0)
        self.assertTrue(audit_schools().ok)

    def test_a_school_created_in_the_middle_of_the_day_has_a_zero_quality_row_for_that_day(self):
        self.assertEqual(self.row(0).quality, 0)
        info = quality.quality_of(self.school.pk)
        self.assertEqual((info["quality"], info["materials_snapshot"], info["teacher_bonus"]), (0, 0, 0))
        self.assertIsNone(quality.quality_of(10 ** 9))

    def test_the_stars_limit_the_base_quality_and_the_breakdown_says_so(self):
        self.buy(900, "b1")
        type(self.school).objects.filter(pk=self.school.pk).update(stars=1)          # limite 333: o estoque está acima dele
        self.midnight_tick(1)
        d1 = self.row(1)
        self.assertEqual(d1.base_quality, D(333))
        steps = {s["key"]: s for s in d1.explained["steps"]}
        self.assertEqual([s["key"] for s in d1.explained["steps"]], ["materials_snapshot", "quality_per_material", "stars_materials_limit",
                                                                     "teacher_bonus"])
        self.assertTrue(steps["stars_materials_limit"]["binding"])
        self.audit_schools_at_end = False                    # o teste adulterou a estrela de propósito (estoque > limite)

    def test_the_quality_rows_are_immutable_and_unique_per_school_and_day(self):
        self.midnight_tick(1)
        row = self.row(1)
        row.quality = D(5)
        with self.assertRaises(SchoolsImmutableError):
            row.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            QualityDay.objects.create(school=self.school, day=row.day, materials_snapshot=0, base_quality=0, quality=0, computed_at=0)

    def test_every_school_is_processed_and_only_the_decayed_ones_lose_materials(self):
        poor = self.make_school(SchoolKind.PUBLIC, name="Sem materiais")
        self.buy(1000, "b1")
        res = self.midnight_tick(1)
        self.assertIsNotNone(res)
        poor.refresh_from_db()
        self.assertEqual(poor.materials, 0)
        self.assertEqual(QualityDay.objects.filter(day=self.day0 + 1).count(), 3)       # origem + as duas criadas aqui
        self.assertEqual(MaterialMovement.objects.filter(operation="decay").count(), 1)


class AuditTests(SchoolBase):
    def setUp(self):
        super().setUp()
        self.audit_schools_at_end = False
        self.school = self.make_school(stars=3)
        materials.credit_materials(self.school.pk, 500, key="b1", reference_kind="t", reference_id=1, origin="t")
        self.midnight_tick(1)

    def codes(self):
        return {f["code"] for f in audit_schools().findings}

    def test_a_healthy_world_is_clean(self):
        self.assertEqual(self.codes(), set())

    def test_it_detects_cache_chain_and_quality_tampering(self):
        type(self.school).objects.filter(pk=self.school.pk).update(materials=999)
        self.assertEqual(self.codes(), {"MATERIALS_CACHE_MISMATCH"})
        type(self.school).objects.filter(pk=self.school.pk).update(materials=490)
        self.assertEqual(self.codes(), set())
        MaterialMovement.objects.filter(key="b1").update(quantity_after=7)
        self.assertEqual(self.codes(), {"MOVEMENT_CHAIN_BROKEN"})
        MaterialMovement.objects.filter(key="b1").update(quantity_after=500)
        QualityDay.objects.filter(school=self.school).exclude(day=competence_day_of(T0)).update(quality=D(1))
        self.assertEqual(self.codes(), {"QUALITY_MISMATCH"})

    def test_it_detects_a_missing_or_wrong_decay_and_a_wrong_snapshot(self):
        MaterialMovement.objects.filter(operation="decay", school=self.school).update(delta=-1, quantity_after=499)
        type(self.school).objects.filter(pk=self.school.pk).update(materials=499)
        self.assertIn("DECAY_MISMATCH", self.codes())
        QualityDay.objects.filter(school=self.school).exclude(day=competence_day_of(T0)).update(materials_snapshot=1)
        self.assertIn("SNAPSHOT_MISMATCH", self.codes())

    def test_it_detects_enrollment_problems(self):
        from schools.models import Enrollment
        from schools import services
        other = self.make_school(SchoolKind.PUBLIC, neighborhood=self.other_neighborhood(), name="Longe")
        Enrollment.objects.filter(player=self.player, ended_at__isnull=True).update(ended_at=self.clk.now(), end_reason="transfer")
        Enrollment.objects.create(player=self.player, school=other, started_at=self.clk.now())
        self.assertEqual(self.codes(), {"TRANSFER_ACROSS_NEIGHBORHOODS"})
        Enrollment.objects.all().delete()
        self.assertEqual(self.codes(), {"PLAYER_WITHOUT_SCHOOL"})
        self.assertIsNone(services.current_enrollment(self.player.pk))

    def test_the_cli_exits_with_an_error_on_violations_and_exports_json(self):
        from io import StringIO
        from django.core.management import call_command
        from django.core.management.base import CommandError
        out = StringIO()
        call_command("audit_schools", "--json", stdout=out)
        self.assertIn('"ok": true', out.getvalue())
        type(self.school).objects.filter(pk=self.school.pk).update(materials=1)
        with self.assertRaises(CommandError):
            call_command("audit_schools", stdout=StringIO())
