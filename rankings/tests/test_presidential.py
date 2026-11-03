"""Presidente com maior percentual de votos (14.4.4): INTERFACE pronta para a Política; nenhuma eleição é inventada."""
from rankings import records
from rankings.constants import Cat
from rankings.models import RankingHistorico

from .base import DAY, T0, RankingsTestCase


class PresidentialRecordTests(RankingsTestCase):
    def rec(self):
        return RankingHistorico.objects.get(category=Cat.PRESIDENT_VOTE_RECORD.value)

    def test_nothing_exists_until_someone_calls_it(self):
        self.assertFalse(RankingHistorico.objects.filter(category=Cat.PRESIDENT_VOTE_RECORD.value).exists())

    def test_design_example_70_percent_is_the_record(self):
        p2, p3 = self.make_player("b"), self.make_player("c")
        records.record_presidential_result(self.player.pk, "E1", 7_000, 10_000, T0)
        out_b = records.record_presidential_result(p2.pk, "E2", 6_000, 10_000, T0 + DAY)
        out_c = records.record_presidential_result(p3.pk, "E3", 5_500, 10_000, T0 + 2 * DAY)
        self.assertEqual((out_b.reason, out_c.reason), ("NOT_GREATER", "NOT_GREATER"))
        r = self.rec()
        self.assertEqual((r.entity_id, r.value), (self.player.pk, 700_000))
        self.assertEqual(r.metadata, {"election": "E1", "votes": 7_000, "total_votes": 10_000, "percent": "70", "election_date": T0})
        self.assertEqual(r.recorded_at, T0)

    def test_stores_all_fields_required_by_the_design(self):
        records.record_presidential_result(self.player.pk, "E1", 1, 3, T0)
        r = self.rec()
        self.assertEqual((r.entity_type, r.entity_id), ("player", self.player.pk))
        self.assertEqual({"election", "votes", "total_votes", "percent", "election_date"}, set(r.metadata))

    def test_exact_comparison_not_floor_ppm(self):
        # 1/3 e 333333,5/1.000.000: mesmos ppm por piso, mas frações diferentes
        p2 = self.make_player("b")
        records.record_presidential_result(self.player.pk, "E1", 333_333, 1_000_000, T0)
        out = records.record_presidential_result(p2.pk, "E2", 1, 3, T0 + DAY)     # 0,3333333… > 0,333333
        self.assertEqual(out.reason, "REPLACED")
        self.assertEqual(self.rec().entity_id, p2.pk)

    def test_equal_percentage_keeps_the_first(self):
        p2 = self.make_player("b")
        records.record_presidential_result(self.player.pk, "E1", 1_000, 2_000, T0)
        out = records.record_presidential_result(p2.pk, "E2", 5_000, 10_000, T0 + DAY)
        self.assertEqual(out.reason, "NOT_GREATER")
        self.assertEqual(self.rec().metadata["election"], "E1")

    def test_higher_percentage_replaces_even_with_fewer_total_votes(self):
        p2 = self.make_player("b")
        records.record_presidential_result(self.player.pk, "E1", 5_500, 10_000, T0)
        records.record_presidential_result(p2.pk, "E2", 80, 100, T0 + DAY)
        r = self.rec()
        self.assertEqual((r.entity_id, r.value, r.metadata["total_votes"]), (p2.pk, 800_000, 100))

    def test_invalid_inputs_are_rejected_and_write_nothing(self):
        bad = [(self.player.pk, "", 1, 2, T0), (self.player.pk, "E", 3, 2, T0), (self.player.pk, "E", -1, 2, T0),
               (self.player.pk, "E", 0, 0, T0), (self.player.pk, "E", 1.5, 2, T0), (self.player.pk, "E", True, 2, T0),
               (None, "E", 1, 2, T0), (self.player.pk, None, 1, 2, T0)]
        for args in bad:
            with self.assertRaises(ValueError, msg=args):
                records.record_presidential_result(*args)
        self.assertFalse(RankingHistorico.objects.exists())

    def test_zero_votes_creates_a_zero_percent_record_only_when_first(self):
        out = records.record_presidential_result(self.player.pk, "E1", 0, 10, T0)
        self.assertEqual((out.reason, self.rec().value), ("CREATED", 0))
