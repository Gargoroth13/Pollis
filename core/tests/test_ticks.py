from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.clock import ManualClock, use_clock
from core.models import WorldClock
from core.ticks import TickRegistry, WORLD, advance_world, catch_up, process_ticks
from core.timeline import SECONDS_PER_DAY, SECONDS_PER_HOUR, SECONDS_PER_WEEK, TickKind, game_ts

H, D, W, M = TickKind.HOURLY, TickKind.DAILY, TickKind.WEEKLY, TickKind.MONTHLY

B = game_ts(2026, 10, 5, tz=__import__("zoneinfo").ZoneInfo("America/Sao_Paulo"))  # segunda 00:00
NEXT_MONDAY = B + SECONDS_PER_WEEK  # 2026-10-12: a semana B..NEXT_MONDAY não contém início de mês
GAME_TZ = override_settings(POLIS_GAME_TIMEZONE="America/Sao_Paulo")


def recorder(reg, scope=WORLD, kinds=(H, D, W)):
    """Registra um handler por kind que anota (kind, at) numa lista."""
    log = []
    for k in kinds:
        reg.register(scope, k, f"rec-{k.name}")(lambda tick, ctx, _log=log: _log.append((tick.kind.name, tick.at)))
    return log


@GAME_TZ
class ProcessTicksTests(TestCase):
    def setUp(self):
        self.reg = TickRegistry()

    def test_runs_handlers_for_each_tick_in_order(self):
        log = recorder(self.reg)
        r = process_ticks(WORLD, B, B + SECONDS_PER_DAY, reg=self.reg)
        self.assertEqual(r.ticks_processed, 25)  # 24 horários + 1 diário
        self.assertEqual((r.processed_until, r.complete), (B + SECONDS_PER_DAY, True))
        self.assertEqual(log[-2:], [("HOURLY", B + SECONDS_PER_DAY), ("DAILY", B + SECONDS_PER_DAY)])
        self.assertEqual(log[0], ("HOURLY", B + SECONDS_PER_HOUR))

    def test_handler_order_priority_then_name(self):
        order = []
        for name, prio in [("b", 100), ("a", 100), ("z", 10), ("m", 200)]:
            self.reg.register(WORLD, H, name, prio)(lambda t, c, n=name: order.append(n))
        process_ticks(WORLD, B, B + SECONDS_PER_HOUR, reg=self.reg)
        self.assertEqual(order, ["z", "a", "b", "m"])

    def test_registration_order_does_not_matter(self):
        def run(names):
            reg, order = TickRegistry(), []
            for n in names:
                reg.register(WORLD, H, n)(lambda t, c, n=n: order.append(n))
            process_ticks(WORLD, B, B + SECONDS_PER_HOUR, reg=reg)
            return order
        self.assertEqual(run(["a", "b", "c"]), run(["c", "a", "b"]))

    def test_duplicate_handler_name_rejected(self):
        self.reg.register(WORLD, H, "x")(lambda t, c: None)
        with self.assertRaises(ValueError):
            self.reg.register(WORLD, H, "x")(lambda t, c: None)

    def test_scopes_are_isolated(self):
        world = recorder(self.reg, WORLD); player = recorder(self.reg, "player")
        process_ticks("player", B, B + SECONDS_PER_HOUR, reg=self.reg)
        self.assertEqual((len(world), len(player)), (0, 1))

    def test_no_handlers_advances_pointer_without_running_anything(self):
        r = process_ticks(WORLD, B, B + 10 * SECONDS_PER_WEEK, reg=self.reg)
        self.assertEqual((r.ticks_processed, r.processed_until, r.complete), (0, B + 10 * SECONDS_PER_WEEK, True))

    def test_end_not_after_start_is_noop(self):
        log = recorder(self.reg)
        r = process_ticks(WORLD, 500, 400, reg=self.reg)
        self.assertEqual((log, r.processed_until, r.ticks_processed), ([], 500, 0))

    def test_only_registered_kinds_are_generated(self):
        log = recorder(self.reg, kinds=(W,))
        process_ticks(WORLD, B, B + 2 * SECONDS_PER_WEEK, reg=self.reg)
        self.assertEqual([k for k, _ in log], ["WEEKLY", "WEEKLY"])

    def test_monthly_handler_fires_once_at_first_of_month_midnight(self):
        log = recorder(self.reg, kinds=(M,))
        process_ticks(WORLD, game_ts(2026, 10, 31, 12), game_ts(2026, 11, 2), reg=self.reg)
        self.assertEqual(log, [("MONTHLY", game_ts(2026, 11, 1))])
        process_ticks(WORLD, game_ts(2026, 11, 1), game_ts(2026, 12, 1), reg=self.reg)
        self.assertEqual(log[-1], ("MONTHLY", game_ts(2026, 12, 1)))  # dezembro: 2º disparo, nenhum repetido
        self.assertEqual(len(log), 2)

    def test_limit_then_resume_equals_single_run(self):
        end = B + 3 * SECONDS_PER_WEEK + 777
        whole = recorder(reg_a := TickRegistry(), kinds=(H, D, W, M))
        process_ticks(WORLD, B, end, reg=reg_a)
        parts = recorder(reg_b := TickRegistry(), kinds=(H, D, W, M))
        pointer, calls = B, 0
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
        Regressão: cortar entre ticks do MESMO instante perderia ticks (o ponteiro
        diria "tudo <= at processado" com o semanal pendente). Varre todos os
        limites, inclusive o que cai dentro do grupo simultâneo da segunda 00:00
        (173 ticks antes dela => limit=174).
        """
        whole = recorder(reg_a := TickRegistry())
        process_ticks(WORLD, B, NEXT_MONDAY, reg=reg_a)
        self.assertEqual(len(whole), 168 + 7 + 1)

        for limit in range(1, 185):
            log = recorder(reg := TickRegistry())
            pointer, guard = B, 0
            while True:
                r = process_ticks(WORLD, pointer, NEXT_MONDAY, limit=limit, reg=reg)
                self.assertTrue(all(at <= r.processed_until for _, at in log), f"limit={limit}")
                pointer, guard = r.processed_until, guard + 1
                if r.complete:
                    break
                self.assertLess(guard, 500)
            self.assertEqual(log, whole, f"limit={limit}")
            self.assertEqual(log.count(("WEEKLY", NEXT_MONDAY)), 1, f"limit={limit}")

    def test_handler_exception_propagates(self):
        self.reg.register(WORLD, H, "boom")(lambda t, c: (_ for _ in ()).throw(RuntimeError("x")))
        with self.assertRaises(RuntimeError):
            process_ticks(WORLD, B, B + SECONDS_PER_HOUR, reg=self.reg)


@GAME_TZ
class AdvanceWorldTests(TestCase):
    def setUp(self):
        self.reg = TickRegistry()
        self.clk = ManualClock(B)
        WorldClock.load()
        WorldClock.objects.filter(pk=1).update(anchor_game=B, world_processed_until=B)

    def run_world(self, **kw):
        with use_clock(self.clk):
            return advance_world(reg=self.reg, **kw)

    def pointer(self):
        return WorldClock.load().world_processed_until

    def test_advances_and_persists_pointer(self):
        log = recorder(self.reg)
        self.clk.advance(days=2)
        r = self.run_world()
        self.assertEqual((r.ticks_processed, self.pointer()), (48 + 2, B + 2 * SECONDS_PER_DAY))
        self.assertEqual(len(log), 50)

    def test_idempotent_second_call_does_nothing(self):
        log = recorder(self.reg)
        self.clk.advance(days=1)
        self.run_world(); n = len(log)
        r = self.run_world()
        self.assertEqual((r.ticks_processed, len(log)), (0, n))

    def test_incremental_calls_equal_one_big_call(self):
        log_a = recorder(ra := TickRegistry()); log_b = recorder(rb := TickRegistry())
        with use_clock(ManualClock(B + 3 * SECONDS_PER_WEEK)):
            advance_world(reg=ra)
        WorldClock.objects.filter(pk=1).update(world_processed_until=B)
        c = ManualClock(B)
        with use_clock(c):
            for _ in range(21):
                c.advance(days=1); advance_world(reg=rb)
        self.assertEqual(log_a, log_b)

    def test_failure_rolls_back_everything(self):
        def bad(tick, ctx):
            if tick.at == B + 3 * SECONDS_PER_HOUR:
                raise RuntimeError("falha no meio")
        self.reg.register(WORLD, H, "bad")(bad)
        self.clk.advance(hours=5)
        with self.assertRaises(RuntimeError):
            self.run_world()
        self.assertEqual(self.pointer(), B)  # nada marcado como processado
        self.reg.clear(); log = recorder(self.reg)
        self.run_world()  # corrigido: reprocessa desde o início, sem pular nada
        self.assertEqual([at for _, at in log], [B + h * SECONDS_PER_HOUR for h in range(1, 6)])
        self.assertEqual(self.pointer(), B + 5 * SECONDS_PER_HOUR)

    def test_db_writes_of_handlers_roll_back_with_failure(self):
        def writer(tick, ctx):
            WorldClock.objects.filter(pk=1).update(real_seconds_per_game_day=999)
            raise RuntimeError
        self.reg.register(WORLD, H, "w")(writer)
        self.clk.advance(hours=1)
        with self.assertRaises(RuntimeError):
            self.run_world()
        self.assertNotEqual(WorldClock.load().real_seconds_per_game_day, 999)

    def test_limit_partial_then_complete(self):
        log = recorder(self.reg)
        self.clk.advance(weeks=1)
        r = self.run_world(limit=50)
        self.assertFalse(r.complete)
        self.assertLess(self.pointer(), NEXT_MONDAY)
        self.assertTrue(self.run_world().complete)
        self.assertEqual((len(log), self.pointer()), (176, NEXT_MONDAY))

    def test_weekly_cycle_fires_exactly_once_on_monday_midnight(self):
        log = recorder(self.reg, kinds=(W,))
        self.clk.set(NEXT_MONDAY - 1); self.run_world()
        self.assertEqual(log, [])
        self.clk.advance(seconds=1); self.run_world()
        self.assertEqual(log, [("WEEKLY", NEXT_MONDAY)])
        self.clk.advance(days=6, hours=23); self.run_world()
        self.assertEqual(len(log), 1)

    def test_monthly_cycle_follows_real_calendar(self):
        log = recorder(self.reg, kinds=(M,))
        self.clk.set(game_ts(2028, 3, 1)); self.run_world()   # cruza fev/2028 (bissexto) e fecha out..mar
        ats = [at for _, at in log]
        self.assertEqual(len(ats), 17)  # 1/nov/2026 .. 1/mar/2028
        self.assertEqual((ats[-1] - ats[-2]) // SECONDS_PER_DAY, 29)  # fevereiro de 2028


@GAME_TZ
class CatchUpTests(TestCase):
    """Escopo por entidade: processamento atrasado ao acessar (design/04)."""

    def test_entity_catch_up_with_own_pointer(self):
        reg = TickRegistry()
        reg.register("player", H, "regen")(lambda t, ctx: ctx.append(t.at))
        entity = []
        r1 = catch_up("player", B, entity, until=B + 3 * SECONDS_PER_HOUR, reg=reg)
        r2 = catch_up("player", r1.processed_until, entity, until=B + 5 * SECONDS_PER_HOUR, reg=reg)
        r3 = catch_up("player", r2.processed_until, entity, until=B + 5 * SECONDS_PER_HOUR, reg=reg)
        self.assertEqual(entity, [B + h * SECONDS_PER_HOUR for h in range(1, 6)])
        self.assertEqual(r3.ticks_processed, 0)

    def test_two_entities_same_absence_get_identical_results(self):
        reg = TickRegistry()
        reg.register("player", H, "x")(lambda t, ctx: ctx.append(t.at))
        a, b = [], []
        catch_up("player", B, a, until=NEXT_MONDAY, reg=reg)
        catch_up("player", B, b, until=NEXT_MONDAY, reg=reg)
        self.assertEqual(a, b)

    def test_default_until_uses_active_clock(self):
        reg = TickRegistry()
        reg.register("player", H, "x")(lambda t, ctx: ctx.append(t.at))
        entity = []
        with use_clock(ManualClock(B + 2 * SECONDS_PER_HOUR)):
            catch_up("player", B, entity, reg=reg)
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
