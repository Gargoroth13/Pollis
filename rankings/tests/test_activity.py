"""Maior tempo ativo (14.3.11) e seu recorde (14.4.3): intervalo < 72 h, sequência encerrada, melhor já alcançada, idempotência."""
from rankings import activity, records
from rankings.constants import Cat
from rankings.models import ActivityStreak, RankingHistorico

from .base import DAY, HOUR, T0, RankingsTestCase


class StreakTests(RankingsTestCase):
    def act(self, at, player=None):
        return activity.record_action((player or self.player).pk, at)

    def test_first_action_starts_a_streak_of_zero_length(self):
        s = self.act(T0)
        self.assertEqual((s.current_start, s.last_action_at, s.best_length), (T0, T0, 0))

    def test_gap_under_72h_continues(self):
        self.act(T0)
        s = self.act(T0 + 71 * HOUR + 59 * 60 + 59)
        self.assertEqual((s.current_start, s.best_length), (T0, 71 * HOUR + 59 * 60 + 59))

    def test_gap_of_exactly_72h_ends_the_streak(self):
        """14.3.11: "3 dias ou mais" encerra; só continua com intervalo INFERIOR a 72 h."""
        self.act(T0)
        s = self.act(T0 + 72 * HOUR)
        self.assertEqual((s.current_start, s.best_length), (T0 + 72 * HOUR, 0))

    def test_design_example_monday_wednesday_saturday(self):
        mon = T0 + 10 * HOUR - 12 * HOUR           # segunda 10:00 (T0 é segunda 12:00)
        wed = mon + 47 * HOUR                       # quarta 09:00 → continua
        sat = wed + 73 * HOUR                       # sábado 10:00 → 73 h: encerra
        self.act(mon)
        s = self.act(wed)
        self.assertEqual((s.current_start, s.best_length), (mon, 47 * HOUR))
        s = self.act(sat)
        self.assertEqual((s.current_start, s.last_action_at), (sat, sat))
        self.assertEqual((s.best_start, s.best_end, s.best_length), (mon, wed, 47 * HOUR))     # a anterior segue como a melhor

    def test_best_survives_reset_and_is_replaced_only_when_exceeded(self):
        self.act(T0)
        self.act(T0 + 2 * DAY)                                         # melhor = 2 dias
        self.act(T0 + 6 * DAY)                                         # intervalo 4 dias: nova sequência
        s = self.act(T0 + 7 * DAY)                                     # 1 dia < 2 dias
        self.assertEqual((s.best_start, s.best_length), (T0, 2 * DAY))
        s = self.act(T0 + 8 * DAY + 3600)                              # 2 dias + 1 h > 2 dias
        self.assertEqual((s.best_start, s.best_end, s.best_length), (T0 + 6 * DAY, T0 + 8 * DAY + 3600, 2 * DAY + 3600))

    def test_equal_length_does_not_replace_best(self):
        self.act(T0)
        self.act(T0 + DAY)
        self.act(T0 + 5 * DAY)
        s = self.act(T0 + 6 * DAY)                                     # também 1 dia: empate, fica a primeira
        self.assertEqual(s.best_start, T0)

    def test_same_instant_and_earlier_instant_change_nothing(self):
        self.act(T0)
        s1 = self.act(T0 + DAY)
        before = ActivityStreak.objects.values().get(pk=s1.pk)
        self.act(T0 + DAY)
        self.act(T0)
        self.assertEqual(ActivityStreak.objects.values().get(pk=s1.pk), before)

    def test_one_row_per_player_and_players_are_independent(self):
        other = self.make_player("p2")
        self.act(T0)
        self.act(T0 + DAY)
        self.act(T0 + 10 * DAY, other)
        self.assertEqual(ActivityStreak.objects.count(), 2)
        self.assertEqual(ActivityStreak.objects.get(player=other).best_length, 0)
        self.assertEqual(ActivityStreak.objects.get(player=self.player).best_length, DAY)

    def test_default_time_is_the_game_clock(self):
        self.clk.advance(hours=5)
        s = activity.record_action(self.player.pk)
        self.assertEqual(s.last_action_at, T0 + 5 * HOUR)


class ActiveTimeRecordTests(RankingsTestCase):
    def act(self, at, player=None):
        return activity.record_action((player or self.player).pk, at)

    def rec(self):
        return RankingHistorico.objects.get(category=Cat.ACTIVE_TIME_RECORD.value)

    def test_no_record_row_content_invented_before_any_action(self):
        self.assertFalse(RankingHistorico.objects.exists())

    def test_first_action_with_zero_length_is_not_a_record(self):
        self.act(T0)
        self.assertFalse(RankingHistorico.objects.exists())

    def test_record_is_created_and_extended_with_metadata(self):
        self.act(T0)
        self.act(T0 + DAY)
        r = self.rec()
        self.assertEqual((r.entity_type, r.entity_id, r.value, r.recorded_at), ("player", self.player.pk, DAY, T0 + DAY))
        self.assertEqual(r.metadata, {"start": T0, "end": T0 + DAY, "length_seconds": DAY})
        self.act(T0 + 2 * DAY)
        r = self.rec()
        self.assertEqual((r.value, r.metadata["end"]), (2 * DAY, T0 + 2 * DAY))

    def test_record_persists_after_the_streak_ends_and_activity_falls(self):
        self.act(T0)
        self.act(T0 + 2 * DAY)
        self.act(T0 + 30 * DAY)                      # sequência encerrada; a atual é de 0 s
        r = self.rec()
        self.assertEqual((r.value, r.metadata["start"]), (2 * DAY, T0))

    def test_another_player_replaces_only_with_strictly_greater(self):
        other = self.make_player("p2")
        self.act(T0)
        self.act(T0 + DAY)
        self.act(T0, other)
        self.act(T0 + DAY, other)                    # empate: fica o primeiro
        self.assertEqual(self.rec().entity_id, self.player.pk)
        self.act(T0 + DAY + HOUR, other)             # maior: substitui
        r = self.rec()
        self.assertEqual((r.entity_id, r.value), (other.pk, DAY + HOUR))

    def test_record_row_is_unique_per_category(self):
        self.act(T0)
        self.act(T0 + DAY)
        self.act(T0 + 2 * DAY)
        self.assertEqual(RankingHistorico.objects.filter(category=Cat.ACTIVE_TIME_RECORD.value).count(), 1)


class RecordsOfferTests(RankingsTestCase):
    def test_non_positive_or_non_int_values_are_never_records(self):
        for bad in (0, -5):
            out = records.offer_value_record(Cat.NET_WORTH_RECORD, "player", self.player.pk, bad, T0)
            self.assertFalse(out.changed)
        self.assertFalse(RankingHistorico.objects.exists())
        self.assertFalse(records.offer_value_record(Cat.NET_WORTH_RECORD, "player", 1, True, T0).changed)

    def test_replacement_updates_time_fields_and_keeps_one_row(self):
        a = records.offer_value_record(Cat.NET_WORTH_RECORD, "player", self.player.pk, 100, T0)
        self.assertEqual(a.reason, "CREATED")
        self.clk.advance(hours=1)
        b = records.offer_value_record(Cat.NET_WORTH_RECORD, "player", self.player.pk, 101, T0 + HOUR)
        self.assertEqual((b.reason, b.record.recorded_at, b.record.updated_at), ("REPLACED", T0 + HOUR, T0 + HOUR))
        c = records.offer_value_record(Cat.NET_WORTH_RECORD, "player", self.player.pk, 101, T0 + 2 * HOUR)
        self.assertEqual(c.reason, "NOT_GREATER")
        self.assertEqual(RankingHistorico.objects.count(), 1)
