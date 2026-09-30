from datetime import datetime, timedelta, timezone as dt_tz

from django.test import TestCase

from core import clock
from core.clock import ManualClock, RealtimeClock, use_clock
from core.models import WorldClock
from core.timeline import SECONDS_PER_DAY, SECONDS_PER_HOUR

T0 = datetime(2026, 9, 30, 12, 0, 0, tzinfo=dt_tz.utc)


class FakeReal:
    """Relógio real falso e controlável."""

    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t

    def tick(self, **kw):
        self.t += timedelta(**kw)


def make_world(real_seconds_per_game_day=600, anchor_game=0):
    WorldClock.objects.all().delete()
    return WorldClock.objects.create(
        pk=1, anchor_real=T0, anchor_game=anchor_game,
        real_seconds_per_game_day=real_seconds_per_game_day,
    )


class ManualClockTests(TestCase):
    def test_advance_and_units(self):
        c = ManualClock()
        c.advance(hours=1)
        self.assertEqual(c.now(), SECONDS_PER_HOUR)
        c.advance(days=1, seconds=5)
        self.assertEqual(c.now(), SECONDS_PER_HOUR + SECONDS_PER_DAY + 5)

    def test_never_goes_back(self):
        c = ManualClock(100)
        with self.assertRaises(ValueError):
            c.set(99)
        with self.assertRaises(ValueError):
            c.advance(seconds=-1)
        self.assertEqual(c.now(), 100)

    def test_use_clock_overrides_and_restores(self):
        make_world()
        manual = ManualClock(42)
        with use_clock(manual):
            self.assertEqual(clock.now(), 42)
            manual.advance(seconds=8)
            self.assertEqual(clock.now(), 50)
        self.assertIsInstance(clock.get_clock(), RealtimeClock)

    def test_use_clock_restores_after_exception(self):
        with self.assertRaises(RuntimeError):
            with use_clock(ManualClock()):
                raise RuntimeError
        self.assertIsInstance(clock.get_clock(), RealtimeClock)


class RealtimeClockTests(TestCase):
    def test_ten_real_minutes_is_one_game_day(self):
        make_world(600)
        real = FakeReal()
        rc = RealtimeClock(real)
        self.assertEqual(rc.now(), 0)
        real.tick(minutes=10)
        self.assertEqual(rc.now(), SECONDS_PER_DAY)
        real.tick(seconds=25)  # 25s reais = 1h de jogo (600s/24)
        self.assertEqual(rc.now(), SECONDS_PER_DAY + SECONDS_PER_HOUR)

    def test_other_speeds(self):
        make_world(86_400)  # tempo real: 1s real = 1s jogo
        real = FakeReal(); rc = RealtimeClock(real); real.tick(seconds=90)
        self.assertEqual(rc.now(), 90)

    def test_clock_before_anchor_never_negative_gain(self):
        make_world(); real = FakeReal(T0 - timedelta(seconds=30))
        self.assertEqual(RealtimeClock(real).now(), 0)

    def test_monotonic_over_many_small_steps(self):
        make_world(600); real = FakeReal(); rc = RealtimeClock(real)
        seen = []
        for _ in range(200):
            real.tick(milliseconds=317); seen.append(rc.now())
        self.assertEqual(seen, sorted(seen))

    def test_set_speed_keeps_continuity(self):
        make_world(600)
        real = FakeReal()
        real.tick(minutes=5)  # meio dia de jogo
        before = RealtimeClock(real).now()
        clock.set_speed(60, real_now=real)   # 10x mais rápido
        self.assertEqual(RealtimeClock(real).now(), before)  # sem salto
        real.tick(seconds=60)                 # agora 60s reais = 1 dia
        self.assertEqual(RealtimeClock(real).now(), before + SECONDS_PER_DAY)

    def test_set_speed_rejects_invalid(self):
        make_world()
        with self.assertRaises(ValueError):
            clock.set_speed(0)

    def test_world_created_lazily_from_settings(self):
        WorldClock.objects.all().delete()
        with self.settings(POLIS_REAL_SECONDS_PER_GAME_DAY=300):
            wc = WorldClock.load()
        self.assertEqual((wc.pk, wc.real_seconds_per_game_day, wc.anchor_game), (1, 300, 0))
        self.assertEqual(WorldClock.objects.count(), 1)
        self.assertEqual(WorldClock.load().pk, 1)  # idempotente
