"""
Medição (não é teste de regressão; não é coletado pela descoberta padrão): custo adicional por ação e desempenho do processador
da outbox de atividade. Executar: `manage.py test rankings.tests.bench_outbox --noinput` (PostgreSQL para números realistas).
Imprime uma linha `BENCH {json}` por medição.
"""
import json
import statistics
import time

from django.db import connection
from django.test import TransactionTestCase

from accounts.models import Usuario
from core.clock import ManualClock, use_clock
from core.instrument import QueryCounter
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger.tests.base import install_test_role
from players import registry
from players.models import Player
from players.services import create_player
from rankings import outbox, params, wiring
from rankings.models import ActivityEvent

T0 = 1_791_212_400


def out(name, **kw):
    print("BENCH " + json.dumps({"name": name, "vendor": connection.vendor, **kw}, default=str))


class OutboxBench(TransactionTestCase):
    def setUp(self):
        generate_world(get_scenario(**SMALL))
        install_test_role(self)
        self.clk = ManualClock(T0)
        cm = use_clock(self.clk)
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)

    def players(self, n):
        return [create_player(Usuario.objects.create_user(f"b{i}")) for i in range(n)]

    def _one(self, pid):
        Player.objects.filter(pk=pid).update(energy=100)
        with QueryCounter() as q:
            t = time.perf_counter()
            res = registry.execute_action(pid, "leisure")           # TransactionTestCase: commit real; on_commit RODA
            dt = time.perf_counter() - t
        assert res.ok
        return q.count, dt * 1000

    def _series(self, label, ps, n):
        qs, ms = [], []
        for i in range(n):
            self.clk.advance(seconds=60)
            q, t = self._one(ps[i % len(ps)].pk)
            qs.append(q)
            ms.append(t)
        out(label, actions=n, queries_median=statistics.median(qs), queries_mean=round(statistics.mean(qs), 2),
            ms_median=round(statistics.median(ms), 2), ms_p95=round(sorted(ms)[int(len(ms) * 0.95) - 1], 2))
        return statistics.median(qs), statistics.median(ms)

    def test_cost_per_action(self):
        ps = self.players(10)
        saved_rec = dict(registry._recorders)
        # A) sem gravador (custo anterior à outbox, sem observer de atividade)
        registry._recorders.clear()
        base = self._series("A_baseline_no_recorder", ps, 200)
        # B) gravador, sem passada imediata (só o INSERT na transação da ação)
        registry._recorders.update(saved_rec)
        params_inline = params.ACTIVITY_INLINE_PROCESSING
        params.ACTIVITY_INLINE_PROCESSING = False
        try:
            rec = self._series("B_recorder_only", ps, 200)
        finally:
            params.ACTIVITY_INLINE_PROCESSING = params_inline
        while outbox.process_pending().events_processed:      # esvazia o que o cenário B deixou pendente (não contaminar C)
            pass
        # C) gravador + passada imediata do jogador após o commit (configuração padrão)
        full = self._series("C_recorder_plus_inline_pass", ps, 200)
        out("extra_per_action", recorder_queries=rec[0] - base[0], recorder_ms=round(rec[1] - base[1], 2),
            recorder_plus_inline_queries=full[0] - base[0], recorder_plus_inline_ms=round(full[1] - base[1], 2))
        outbox.process_pending()

    def test_processor_performance(self):
        n_players, per_player = 100, 100
        ps = self.players(n_players)
        for per, label in ((1, "tick_drain_1_event_per_player"), (per_player, "backlog_100_events_per_player")):
            ActivityEvent.objects.all().delete()
            ActivityEvent.objects.bulk_create([ActivityEvent(player_id=p.pk, action_id="leisure", at=T0 + i * 60)
                                                for p in ps for i in range(per)])
            s = outbox.process_pending(max_players=n_players)
            d = s.to_dict()
            out(label, players=d["players"], events=d["events_processed"], duration_ms=d["duration_ms"], queries=d["queries"],
                db_ms=d["db_ms"], events_per_second=d["events_per_second"],
                queries_per_event=round(d["queries"] / max(1, d["events_processed"]), 2), failures=d["events_failed"],
                pending_after=d["pending_after"])
        # varredura de jogadores pendentes com atraso grande (200 mil seria o extremo; 10 mil já mostra o custo da consulta)
        ActivityEvent.objects.all().delete()
        ActivityEvent.objects.bulk_create([ActivityEvent(player_id=ps[i % n_players].pk, action_id="leisure", at=T0 + i)
                                            for i in range(10_000)], batch_size=2000)
        t = time.perf_counter()
        s = outbox.process_pending(max_players=n_players)
        out("backlog_10000_events_100_players", duration_ms=round((time.perf_counter() - t) * 1000, 1),
            events=s.events_processed, queries=s.queries, db_ms=s.db_ms, pending_after=s.pending_after)
