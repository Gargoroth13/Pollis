from datetime import timedelta
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase, override_settings

from core.timeline import (
    SECONDS_PER_DAY, SECONDS_PER_HOUR, SECONDS_PER_WEEK, Tick, TickKind,
    describe, game_ts, local_dt, next_tick_at, ticks_between, weekday_of,
)

T, H, D, W, M = (TickKind.TEN_MINUTES, TickKind.HOURLY, TickKind.DAILY, TickKind.WEEKLY, TickKind.MONTHLY)
SP = ZoneInfo("America/Sao_Paulo")
NY = ZoneInfo("America/New_York")
IN = ZoneInfo("Asia/Kolkata")

MONDAY = game_ts(2026, 10, 5, tz=SP)        # segunda, sem início de mês na semana
NEXT_MONDAY = game_ts(2026, 10, 12, tz=SP)


@override_settings(POLIS_GAME_TIMEZONE="America/Sao_Paulo")
class CalendarTests(SimpleTestCase):
    def test_game_time_is_real_unix_time(self):
        """Tempo de jogo = segundos reais: 2026-09-30 12:00 -03:00 == 15:00 UTC."""
        from datetime import datetime, timezone
        self.assertEqual(game_ts(2026, 9, 30, 12), int(datetime(2026, 9, 30, 15, tzinfo=timezone.utc).timestamp()))

    def test_weekday_and_describe(self):
        self.assertEqual(weekday_of(game_ts(2026, 9, 28)), 0)   # segunda
        self.assertEqual(weekday_of(game_ts(2026, 9, 30)), 2)   # quarta
        self.assertEqual(describe(game_ts(2026, 9, 30, 14, 30)), "2026-09-30 (quarta) 14:30")

    def test_game_timezone_not_user_or_project_timezone(self):
        t = game_ts(2026, 9, 30, 23, 30)  # ainda dia 30 no fuso do jogo (São Paulo)
        with override_settings(TIME_ZONE="Asia/Tokyo"):  # outro fuso "do sistema"/usuário
            self.assertEqual(local_dt(t).date().isoformat(), "2026-09-30")
        with override_settings(POLIS_GAME_TIMEZONE="Asia/Tokyo"):  # só mudar o fuso do JOGO muda o calendário
            self.assertEqual(local_dt(t).date().isoformat(), "2026-10-01")

    def test_next_tick_at_is_strictly_after(self):
        self.assertEqual(next_tick_at(MONDAY, H), MONDAY + SECONDS_PER_HOUR)
        self.assertEqual(next_tick_at(MONDAY - 1, H), MONDAY)
        self.assertEqual(next_tick_at(MONDAY, D), MONDAY + SECONDS_PER_DAY)
        self.assertEqual(next_tick_at(MONDAY, W), NEXT_MONDAY)            # segunda exata -> próxima segunda
        self.assertEqual(next_tick_at(MONDAY - 1, W), MONDAY)             # domingo 23:59:59 -> segunda
        self.assertEqual(next_tick_at(game_ts(2026, 10, 7, 10), W), NEXT_MONDAY)

    def test_monthly_rollover_december_to_january(self):
        self.assertEqual(next_tick_at(game_ts(2026, 12, 15), M), game_ts(2027, 1, 1))
        self.assertEqual(next_tick_at(game_ts(2026, 1, 1), M), game_ts(2026, 2, 1))   # dia 1 exato -> mês seguinte
        self.assertEqual(next_tick_at(game_ts(2026, 1, 31, 23, 59, 59), M), game_ts(2026, 2, 1))


@override_settings(POLIS_GAME_TIMEZONE="America/Sao_Paulo")
class TicksBetweenTests(SimpleTestCase):
    def test_start_exclusive_end_inclusive(self):
        t = MONDAY + SECONDS_PER_HOUR
        self.assertEqual(list(ticks_between(MONDAY, t, [H])), [Tick(t, H)])
        self.assertEqual(list(ticks_between(t, t + SECONDS_PER_HOUR, [H])), [Tick(t + SECONDS_PER_HOUR, H)])

    def test_ten_minute_ticks_are_every_600_absolute_seconds(self):
        ts = [t.at for t in ticks_between(MONDAY, MONDAY + 3600, [T])]
        self.assertEqual(ts, [MONDAY + 600 * i for i in range(1, 7)])
        self.assertEqual(next_tick_at(MONDAY + 599, T), MONDAY + 600)
        self.assertEqual(next_tick_at(MONDAY + 600, T), MONDAY + 1200)

    def test_empty_when_end_not_after_start(self):
        self.assertEqual(list(ticks_between(100, 100)), [])
        self.assertEqual(list(ticks_between(100, 50)), [])

    def test_one_week_counts(self):
        ts = list(ticks_between(MONDAY, NEXT_MONDAY))
        by = lambda k: sum(1 for t in ts if t.kind == k)
        self.assertEqual((by(T), by(H), by(D), by(W), by(M)), (1008, 168, 7, 1, 0))

    def test_weekly_tick_is_monday_midnight_local(self):
        weekly = list(ticks_between(MONDAY, MONDAY + 13 * SECONDS_PER_WEEK, [W]))
        self.assertEqual(len(weekly), 13)
        for t in weekly:
            d = local_dt(t.at)
            self.assertEqual((d.weekday(), d.hour, d.minute, d.second), (0, 0, 0, 0))

    def test_daily_tick_is_local_midnight(self):
        for t in ticks_between(MONDAY, MONDAY + 40 * SECONDS_PER_DAY, [D]):
            d = local_dt(t.at)
            self.assertEqual((d.hour, d.minute, d.second), (0, 0, 0))

    def test_monthly_is_real_calendar_month(self):
        start, end = game_ts(2025, 12, 31, 23, 59), game_ts(2027, 1, 1)
        ms = list(ticks_between(start, end, [M]))
        self.assertEqual(len(ms), 13)  # jan/2026 .. jan/2027
        for t in ms:
            d = local_dt(t.at)
            self.assertEqual((d.day, d.hour, d.minute), (1, 0, 0))

    def test_months_have_real_lengths_including_leap_year(self):
        def days_in(y, m):
            n_y, n_m = (y + 1, 1) if m == 12 else (y, m + 1)
            return len(list(ticks_between(game_ts(y, m, 1), game_ts(n_y, n_m, 1), [D])))
        self.assertEqual([days_in(2026, m) for m in range(1, 13)], [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
        self.assertEqual(days_in(2028, 2), 29)   # bissexto
        self.assertEqual(days_in(2100, 2), 28)   # século não bissexto

    def test_all_four_kinds_coincide_ordered_small_to_large(self):
        t = game_ts(2026, 6, 1)  # 1º de junho de 2026 é segunda-feira
        self.assertEqual(weekday_of(t), 0)
        ts = list(ticks_between(t - 1, t))
        self.assertEqual([x.kind for x in ts], [T, H, D, W, M])
        self.assertTrue(all(x.at == t for x in ts))

    def test_output_is_globally_sorted(self):
        ts = list(ticks_between(MONDAY, MONDAY + 120 * SECONDS_PER_DAY))
        self.assertEqual(ts, sorted(ts))

    def test_is_lazy_generator(self):
        it = ticks_between(game_ts(2026, 1, 1), game_ts(5000, 1, 1), [H])  # ~24 milhões de ticks
        first = [next(it).at for _ in range(2)]
        self.assertEqual(first[1] - first[0], SECONDS_PER_HOUR)

    def test_splitting_the_interval_loses_and_repeats_nothing(self):
        start, end = game_ts(2026, 9, 20), game_ts(2026, 11, 3, 5, 17)
        whole = list(ticks_between(start, end))
        for cut in (start + 1, start + 3599, start + 3600, game_ts(2026, 10, 1) - 1, game_ts(2026, 10, 1),
                    game_ts(2026, 10, 1) + 1, game_ts(2026, 10, 5), game_ts(2026, 11, 1)):
            self.assertEqual(list(ticks_between(start, cut)) + list(ticks_between(cut, end)), whole, f"corte em {cut}")

    def test_kind_filter(self):
        self.assertTrue(all(t.kind == D for t in ticks_between(MONDAY, NEXT_MONDAY, [D])))


class TimezoneRobustnessTests(SimpleTestCase):
    """O jogo usa a sua própria time zone; DST e offsets fracionários não quebram os ticks."""

    def test_dst_spring_forward_daily_and_hourly(self):
        # New York: 2026-03-08 tem 23h. Um tick diário por data local, à meia-noite local.
        start, end = game_ts(2026, 3, 6, 12, tz=NY), game_ts(2026, 3, 11, tz=NY)
        ds = [t.at for t in ticks_between(start, end, [D], tz=NY)]
        self.assertEqual([local_dt(a, NY).date().isoformat() for a in ds],
                         ["2026-03-07", "2026-03-08", "2026-03-09", "2026-03-10", "2026-03-11"])
        self.assertTrue(all(local_dt(a, NY).hour == 0 for a in ds))
        self.assertEqual(ds[2] - ds[1], 23 * SECONDS_PER_HOUR)  # dia curto
        # hora a hora continua a cada 3600 s absolutos
        hs = [t.at for t in ticks_between(ds[1], ds[2], [H], tz=NY)]
        self.assertEqual(len(hs), 23)
        self.assertTrue(all(b - a == SECONDS_PER_HOUR for a, b in zip(hs, hs[1:])))

    def test_dst_fall_back_has_25h_day_and_no_duplicate_ticks(self):
        start, end = game_ts(2026, 10, 30, 12, tz=NY), game_ts(2026, 11, 4, tz=NY)
        ts = [t for t in ticks_between(start, end, [D, W, M], tz=NY)]
        self.assertEqual(ts, sorted(set(ts)))
        ds = [t.at for t in ts if t.kind == D]
        self.assertEqual(ds[2] - ds[1], 25 * SECONDS_PER_HOUR)  # 1 → 2 nov

    def test_fractional_offset_zone(self):
        ds = list(ticks_between(game_ts(2026, 9, 30, tz=IN), game_ts(2026, 10, 4, tz=IN), [D], tz=IN))
        self.assertEqual(len(ds), 4)
        for t in ds:
            d = local_dt(t.at, IN)
            self.assertEqual((d.hour, d.minute), (0, 0))
            self.assertEqual((t.at % SECONDS_PER_DAY), 18 * SECONDS_PER_HOUR + 30 * 60)  # 18:30 UTC
