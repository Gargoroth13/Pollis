from django.test import SimpleTestCase

from core.timeline import (
    SECONDS_PER_DAY, SECONDS_PER_HOUR, SECONDS_PER_WEEK, Tick, TickKind,
    day_of, describe, hour_of_day, next_tick_at, ticks_between, week_of, weekday_of,
)

H, D, W = TickKind.HOURLY, TickKind.DAILY, TickKind.WEEKLY


class CalendarTests(SimpleTestCase):
    def test_epoch_is_monday_midnight(self):
        self.assertEqual((day_of(0), hour_of_day(0), weekday_of(0), week_of(0)), (0, 0, 0, 0))

    def test_weekday_cycle(self):
        self.assertEqual([weekday_of(d * SECONDS_PER_DAY) for d in range(8)], [0, 1, 2, 3, 4, 5, 6, 0])

    def test_boundaries(self):
        self.assertEqual(hour_of_day(SECONDS_PER_DAY - 1), 23)
        self.assertEqual(hour_of_day(SECONDS_PER_DAY), 0)
        self.assertEqual(week_of(SECONDS_PER_WEEK - 1), 0)
        self.assertEqual(week_of(SECONDS_PER_WEEK), 1)

    def test_describe(self):
        self.assertEqual(describe(SECONDS_PER_DAY + 14 * SECONDS_PER_HOUR + 30 * 60), "dia 1 (terça) 14:30")

    def test_next_tick_at_is_strictly_after(self):
        self.assertEqual(next_tick_at(0, H), SECONDS_PER_HOUR)
        self.assertEqual(next_tick_at(SECONDS_PER_HOUR, H), 2 * SECONDS_PER_HOUR)
        self.assertEqual(next_tick_at(SECONDS_PER_HOUR - 1, H), SECONDS_PER_HOUR)
        self.assertEqual(next_tick_at(0, W), SECONDS_PER_WEEK)


class TicksBetweenTests(SimpleTestCase):
    def test_start_exclusive_end_inclusive(self):
        t = SECONDS_PER_HOUR
        self.assertEqual(list(ticks_between(0, t, [H])), [Tick(t, H)])   # end inclusivo
        self.assertEqual(list(ticks_between(t, 2 * t, [H])), [Tick(2 * t, H)])  # start exclusivo

    def test_empty_when_end_not_after_start(self):
        self.assertEqual(list(ticks_between(100, 100)), [])
        self.assertEqual(list(ticks_between(100, 50)), [])

    def test_no_tick_at_epoch(self):
        self.assertEqual(list(ticks_between(-1, 0)), [])

    def test_one_week_counts(self):
        ts = list(ticks_between(0, SECONDS_PER_WEEK))
        by = lambda k: sum(1 for t in ts if t.kind == k)
        self.assertEqual((by(H), by(D), by(W)), (168, 7, 1))

    def test_weekly_tick_is_monday_midnight(self):
        weekly = [t for t in ticks_between(0, 3 * SECONDS_PER_WEEK, [W])]
        self.assertEqual(len(weekly), 3)
        for t in weekly:
            self.assertEqual((weekday_of(t.at), hour_of_day(t.at)), (0, 0))

    def test_simultaneous_ticks_ordered_hourly_daily_weekly(self):
        ts = list(ticks_between(SECONDS_PER_WEEK - 1, SECONDS_PER_WEEK))
        self.assertEqual([t.kind for t in ts], [H, D, W])
        self.assertTrue(all(t.at == SECONDS_PER_WEEK for t in ts))

    def test_output_is_globally_sorted(self):
        ts = list(ticks_between(0, 3 * SECONDS_PER_WEEK))
        self.assertEqual(ts, sorted(ts))

    def test_is_lazy_generator(self):
        # ~95 milhões de ticks horários: só funciona se não materializar.
        it = ticks_between(0, 10_000 * 365 * SECONDS_PER_DAY, [H])
        self.assertEqual([next(it).at for _ in range(3)], [3600, 7200, 10800])

    def test_splitting_the_interval_loses_and_repeats_nothing(self):
        end = 5 * SECONDS_PER_WEEK + 12345
        whole = list(ticks_between(0, end))
        for cut in (1, 3599, 3600, 3601, SECONDS_PER_DAY, SECONDS_PER_WEEK, 2 * SECONDS_PER_WEEK + 7):
            parts = list(ticks_between(0, cut)) + list(ticks_between(cut, end))
            self.assertEqual(parts, whole, f"corte em {cut}")

    def test_kind_filter(self):
        self.assertTrue(all(t.kind == D for t in ticks_between(0, SECONDS_PER_WEEK, [D])))
