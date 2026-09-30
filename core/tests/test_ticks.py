from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core import clock, ticks
from core.clock import ManualClock, use_clock
from core.models import WorldClock
from core.ticks import TickRegistry, WORLD, advance_world, catch_up, process_ticks
from core.timeline import SECONDS_PER_DAY, SECONDS_PER_HOUR, SECONDS_PER_WEEK, TickKind

H, D, W = TickKind.HOURLY, TickKind.DAILY, TickKind.WEEKLY


def recorder(reg, scope=WORLD, kinds=(H, D, W)):
    """Registra um handler por kind que anota (kind, at) numa lista."""
    log = []
    for k in kinds:
        reg.register(scope, k, f"rec-{k.name}")(lambda tick, ctx, _log=log: _log.append((tick.kind.name, tick.at)))
    return log


class ProcessTicksTests(TestCase):
    def setUp(self):
        self.reg = TickRegistry()

    def test_runs_handlers_for_each_tick_in_order(self):
        log = recorder(self.reg)
        r = process_ticks(WORLD, 0, SECONDS_PER_DAY, reg=self.reg)
        self.assertEqual(r.ticks_processed, 25)  # 24 horários + 1 diário
        self.assertEqual(r.processed_until, SECONDS_PER_DAY)
        self.assertTrue(r.complete)
        self.assertEqual(log[-2:], [("HOURLY", SECONDS_PER_DAY), ("DAILY", SECONDS_PER_DAY)])
        self.assertEqual(log[0], ("HOURLY", SECONDS_PER_HOUR))

    def test_handler_order_priority_then_name(self):
        order = []
        for name, prio in [("b", 100), ("a", 100), ("z", 10), ("m", 200)]:
            self.reg.register(WORLD, H, name, prio)(lambda t, c, n=name: order.append(n))
        process_ticks(WORLD, 0, SECONDS_PER_HOUR, reg=self.reg)
        self.assertEqual(order, ["z", "a", "b", "m"])

    def test_registration_order_does_not_matter(self):
        def run(names):
            reg, order = TickRegistry(), []
            for n in names:
                reg.register(WORLD, H, n)(lambda t, c, n=n: order.append(n))
            process_ticks(WORLD, 0, SECONDS_PER_HOUR, reg=reg)
            return order
        self.assertEqual(run(["a", "b", "c"]), run(["c", "a", "b"]))

    def test_duplicate_handler_name_rejected(self):
        self.reg.register(WORLD, H, "x")(lambda t, c: None)
        with self.assertRaises(ValueError):
            self.reg.register(WORLD, H, "x")(lambda t, c: None)

    def test_scopes_are_isolated(self):
        world = recorder(self.reg, WORLD); player = recorder(self.reg, "player")
        process_ticks("player", 0, SECONDS_PER_HOUR, reg=self.reg)
        self.assertEqual((len(world), len(player)), (0, 1))

    def test_no_handlers_advances_pointer_without_running_anything(self):
        r = process_ticks(WORLD, 0, 10 * SECONDS_PER_WEEK, reg=self.reg)
        self.assertEqual((r.ticks_processed, r.processed_until, r.complete), (0, 10 * SECONDS_PER_WEEK, True))

    def test_end_not_after_start_is_noop(self):
        log = recorder(self.reg)
        r = process_ticks(WORLD, 500, 400, reg=self.reg)
        self.assertEqual((log, r.processed_until, r.ticks_processed), ([], 500, 0))

    def test_only_registered_kinds_are_generated(self):
        log = recorder(self.reg, kinds=(W,))
        process_ticks(WORLD, 0, 2 * SECONDS_PER_WEEK, reg=self.reg)
        self.assertEqual([k for k, _ in log], ["WEEKLY", "WEEKLY"])

    def test_limit_then_resume_equals_single_run(self):
        end = 3 * SECONDS_PER_WEEK + 777
        whole = recorder(reg_a := TickRegistry())
        process_ticks(WORLD, 0, end, reg=reg_a)

        parts = recorder(reg_b := TickRegistry())
        pointer, calls = 0, 0
        while True:
            r = process_ticks(WORLD, pointer, end, limit=100, reg=reg_b)
            pointer, calls = r.processed_until, calls + 1
            if r.complete:
                break
            self.assertLess(calls, 1000)
        self.assertGreater(calls, 1)
        self.assertEqual(parts, whole)  # nada perdido, nada repetido

    def test_limit_never_splits_simultaneous_ticks(self):
        """
        Regressão: cortar entre HOURLY/DAILY/WEEKLY do MESMO instante perderia
        ticks (o ponteiro diria "tudo <= at processado" com o semanal pendente).
        Varre todos os limites possíveis, inclusive o que cai dentro do grupo
        simultâneo (173 ticks antes da segunda-feira => limit=174).
        """
        whole = recorder(reg_a := TickRegistry())
        process_ticks(WORLD, 0, SECONDS_PER_WEEK, reg=reg_a)
        self.assertEqual(len(whole), 168 + 7 + 1)

        for limit in range(1, 185):
            log = recorder(reg := TickRegistry())
            pointer, guard = 0, 0
            while True:
                r = process_ticks(WORLD, pointer, SECONDS_PER_WEEK, limit=limit, reg=reg)
                # invariante do ponteiro: nada processado além dele, tudo até ele processado
                self.assertTrue(all(at <= r.processed_until for _, at in log), f"limit={limit}")
                pointer, guard = r.processed_until, guard + 1
                if r.complete:
                    break
                self.assertLess(guard, 500)
            self.assertEqual(log, whole, f"limit={limit}")
            self.assertEqual(log.count(("WEEKLY", SECONDS_PER_WEEK)), 1, f"limit={limit}")

    def test_handler_exception_propagates(self):
        self.reg.register(WORLD, H, "boom")(lambda t, c: (_ for _ in ()).throw(RuntimeError("x")))
        with self.assertRaises(RuntimeError):
            process_ticks(WORLD, 0, SECONDS_PER_HOUR, reg=self.reg)


class AdvanceWorldTests(TestCase):
    def setUp(self):
        self.reg = TickRegistry()
        self.clk = ManualClock()
        WorldClock.load()

    def run_world(self, **kw):
        with use_clock(self.clk):
            return advance_world(reg=self.reg, **kw)

    def pointer(self):
        return WorldClock.load().world_processed_until

    def test_advances_and_persists_pointer(self):
        log = recorder(self.reg)
        self.clk.advance(days=2)
        r = self.run_world()
        self.assertEqual((r.ticks_processed, self.pointer()), (48 + 2, 2 * SECONDS_PER_DAY))
        self.assertEqual(len(log), 50)

    def test_idempotent_second_call_does_nothing(self):
        log = recorder(self.reg)
        self.clk.advance(days=1)
        self.run_world(); n = len(log)
        r = self.run_world()
        self.assertEqual((r.ticks_processed, len(log)), (0, n))

    def test_incremental_calls_equal_one_big_call(self):
        log_a = recorder(ra := TickRegistry()); log_b = recorder(rb := TickRegistry())
        WorldClock.objects.filter(pk=1).update(world_processed_until=0)
        with use_clock(ManualClock(3 * SECONDS_PER_WEEK)):
            advance_world(reg=ra)
        WorldClock.objects.filter(pk=1).update(world_processed_until=0)
        c = ManualClock()
        with use_clock(c):
            for _ in range(21):
                c.advance(days=1); advance_world(reg=rb)
        self.assertEqual(log_a, log_b)

    def test_failure_rolls_back_everything(self):
        side_effects = []
        def bad(tick, ctx):
            side_effects.append(tick.at)
            if tick.at == 3 * SECONDS_PER_HOUR:
                raise RuntimeError("falha no meio")
        self.reg.register(WORLD, H, "bad")(bad)
        self.clk.advance(hours=5)
        with self.assertRaises(RuntimeError):
            self.run_world()
        self.assertEqual(self.pointer(), 0)  # nada marcado como processado
        # corrige o handler e tenta de novo: reprocessa desde o início, sem pular nada
        self.reg.clear(); log = recorder(self.reg)
        self.run_world()
        self.assertEqual([at for _, at in log], [h * SECONDS_PER_HOUR for h in range(1, 6)])
        self.assertEqual(self.pointer(), 5 * SECONDS_PER_HOUR)

    def test_db_writes_of_handlers_roll_back_with_failure(self):
        def writer(tick, ctx):
            WorldClock.objects.filter(pk=1).update(anchor_game=999)
            raise RuntimeError
        self.reg.register(WORLD, H, "w")(writer)
        self.clk.advance(hours=1)
        with self.assertRaises(RuntimeError):
            self.run_world()
        self.assertEqual(WorldClock.load().anchor_game, 0)

    def test_limit_partial_then_complete(self):
        log = recorder(self.reg)
        self.clk.advance(weeks=1)
        r = self.run_world(limit=50)
        self.assertFalse(r.complete)
        self.assertLess(self.pointer(), SECONDS_PER_WEEK)
        r = self.run_world()
        self.assertTrue(r.complete)
        self.assertEqual((len(log), self.pointer()), (176, SECONDS_PER_WEEK))

    def test_weekly_law_cycle_fires_exactly_once_on_monday_midnight(self):
        log = recorder(self.reg, kinds=(W,))
        self.clk.set(SECONDS_PER_WEEK - 1); self.run_world()
        self.assertEqual(log, [])
        self.clk.advance(seconds=1); self.run_world()
        self.assertEqual(log, [("WEEKLY", SECONDS_PER_WEEK)])
        self.clk.advance(days=6, hours=23); self.run_world()
        self.assertEqual(len(log), 1)


class CatchUpTests(TestCase):
    """Escopo por entidade: processamento atrasado ao acessar (design/04)."""

    def test_entity_catch_up_with_own_pointer(self):
        reg = TickRegistry()
        reg.register("player", H, "regen")(lambda t, ctx: ctx.append(t.at))
        entity = []
        r1 = catch_up("player", 0, entity, until=3 * SECONDS_PER_HOUR, reg=reg)
        r2 = catch_up("player", r1.processed_until, entity, until=5 * SECONDS_PER_HOUR, reg=reg)
        r3 = catch_up("player", r2.processed_until, entity, until=5 * SECONDS_PER_HOUR, reg=reg)
        self.assertEqual(entity, [h * SECONDS_PER_HOUR for h in range(1, 6)])
        self.assertEqual(r3.ticks_processed, 0)

    def test_two_entities_same_absence_get_identical_results(self):
        reg = TickRegistry()
        reg.register("player", H, "x")(lambda t, ctx: ctx.append(t.at))
        a, b = [], []
        catch_up("player", 0, a, until=SECONDS_PER_WEEK, reg=reg)
        catch_up("player", 0, b, until=SECONDS_PER_WEEK, reg=reg)
        self.assertEqual(a, b)

    def test_default_until_uses_active_clock(self):
        reg = TickRegistry()
        reg.register("player", H, "x")(lambda t, ctx: ctx.append(t.at))
        entity = []
        with use_clock(ManualClock(2 * SECONDS_PER_HOUR)):
            catch_up("player", 0, entity, reg=reg)
        self.assertEqual(len(entity), 2)


class CommandTests(TestCase):
    def test_world_clock_show_and_set_speed(self):
        out = StringIO()
        call_command("world_clock", "set-speed", "120", stdout=out)
        self.assertIn("1 dia de jogo = 120s", out.getvalue())
        self.assertEqual(WorldClock.load().real_seconds_per_game_day, 120)

    def test_world_clock_rejects_invalid_speed(self):
        with self.assertRaises(CommandError):
            call_command("world_clock", "set-speed", "0", stdout=StringIO())

    def test_advance_world_command_runs(self):
        out = StringIO()
        call_command("advance_world", stdout=out)
        self.assertIn("(completo)", out.getvalue())
