"""
Concorrência dos recordes e das sequências. Em PostgreSQL as transações disputam as linhas com `SELECT ... FOR UPDATE`; em SQLite o
próprio banco serializa as escritas. O teste verifica a PROPRIEDADE (uma linha por jogador/categoria, o recorde é o máximo da fonte,
auditoria limpa), que vale nos dois.
"""
import threading
import time
import unittest

from django.db import OperationalError, close_old_connections, connection
from django.test import TransactionTestCase

from accounts.models import Usuario
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger import obligations, services as ledger
from ledger.audit import audit_ledger
from ledger.constants import AccountKind, Nature
from ledger.tests.base import fund_account, install_test_role
from players.services import create_player
from rankings import activity, audit, records
from rankings.constants import Cat
from rankings.models import ActivityStreak, NetWorthCandidate, RankingHistorico

T0 = 1_791_212_400
HOUR, DAY = 3600, 86400


def _retry(fn, attempts=80):
    for _ in range(attempts):
        try:
            return fn()
        except OperationalError:           # SQLite: banco bloqueado por outra thread
            time.sleep(0.02)
    raise AssertionError("não conseguiu executar após várias tentativas")


class _ConcurrencyBase(TransactionTestCase):
    def setUp(self):
        generate_world(get_scenario(**SMALL))
        install_test_role(self)
        self.players = [create_player(Usuario.objects.create_user(f"c{i}")) for i in range(4)]

    def _run(self, jobs):
        barrier = threading.Barrier(len(jobs))
        results, errors = [None] * len(jobs), []

        def worker(i, job):
            try:
                barrier.wait(timeout=10)
                results[i] = _retry(job)
            except Exception as exc:          # noqa: BLE001
                errors.append(exc)
            finally:
                close_old_connections()
                connection.close()

        threads = [threading.Thread(target=worker, args=(i, j)) for i, j in enumerate(jobs)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        self.assertEqual(errors, [])
        return results


class RankingsConcurrencyTests(_ConcurrencyBase):
    def test_first_action_race_for_one_player_creates_a_single_consistent_row(self):
        p = self.players[0]
        self._run([lambda i=i: activity.record_action(p.pk, T0 + i * HOUR) for i in range(6)])
        self.assertEqual(ActivityStreak.objects.filter(player=p).count(), 1)
        s = ActivityStreak.objects.get(player=p)
        self.assertEqual(s.last_action_at, T0 + 5 * HOUR)
        self.assertEqual(s.best_length, s.best_end - s.best_start)
        self.assertTrue(audit.audit_rankings()["ok"], audit.audit_rankings()["findings"])

    def test_active_time_record_ends_as_the_maximum_of_all_players(self):
        def job(p, days):
            def run():
                activity.record_action(p.pk, T0)
                activity.record_action(p.pk, T0 + days * DAY)
            return run
        self._run([job(p, d) for p, d in zip(self.players, (1, 2, 1, 2))])
        self.assertEqual(RankingHistorico.objects.filter(category=Cat.ACTIVE_TIME_RECORD.value).count(), 1)
        rec = RankingHistorico.objects.get(category=Cat.ACTIVE_TIME_RECORD.value)
        self.assertEqual(rec.value, 2 * DAY)
        self.assertEqual(rec.entity_id, ActivityStreak.objects.get(player_id=rec.entity_id).player_id)
        self.assertTrue(audit.audit_rankings(at=T0 + 3 * DAY)["ok"], audit.audit_rankings(at=T0 + 3 * DAY)["findings"])

    def test_net_worth_record_race_keeps_the_greatest(self):
        for p, amount in zip(self.players, (1_000, 5_000, 3_000, 5_000)):
            fund_account(ledger.player_account(p.pk), amount)
        self._run([lambda p=p: records.check_net_worth_record(p.pk, T0) for p in self.players])
        self.assertEqual(RankingHistorico.objects.filter(category=Cat.NET_WORTH_RECORD.value).count(), 1)
        rec = RankingHistorico.objects.get(category=Cat.NET_WORTH_RECORD.value)
        self.assertEqual(rec.value, 5_000)
        self.assertIn(rec.entity_id, (self.players[1].pk, self.players[3].pk))      # empate: quem chegou primeiro; ambos válidos

    def test_presidential_record_race_keeps_the_greatest_percentage(self):
        data = [(7_000, 10_000), (6_000, 10_000), (55, 100), (9, 10)]
        self._run([lambda p=p, d=d, i=i: records.record_presidential_result(p.pk, f"E{i}", d[0], d[1], T0)
                   for i, (p, d) in enumerate(zip(self.players, data))])
        rec = RankingHistorico.objects.get(category=Cat.PRESIDENT_VOTE_RECORD.value)
        self.assertEqual((rec.value, rec.metadata["election"]), (900_000, "E3"))


class NetWorthLedgerConcurrencyTests(_ConcurrencyBase):
    """Operações do ledger em paralelo (o gancho grava o recorde dentro de cada transação): sem deadlock, sem perda."""

    def test_parallel_payments_to_different_players_end_with_the_greatest_peak(self):
        company = ledger.get_or_create_account(AccountKind.COMPANY, 1)
        fund_account(company, 100_000)
        amounts = (1_000, 9_000, 4_000, 9_000)

        def pay(p, amount, i):
            return lambda: ledger.transfer(company.pk, ledger.player_account(p.pk).pk, amount, Nature.SALE, key=f"c{i}",
                                           reference_kind="t", reference_id=i, at=T0 + i)
        results = self._run([pay(p, a, i) for i, (p, a) in enumerate(zip(self.players, amounts))])
        self.assertTrue(all(r.ok for r in results), [r.code for r in results])
        rec = RankingHistorico.objects.get(category=Cat.NET_WORTH_RECORD.value)
        self.assertEqual(rec.value, 9_000)
        self.assertEqual(rec.entity_id, self.players[1].pk)                    # empate em 9.000: chegou antes (T0+1 < T0+3)
        self.assertEqual(RankingHistorico.objects.filter(category=Cat.NET_WORTH_RECORD.value).count(), 1)
        self.assertEqual(NetWorthCandidate.objects.count(), 0)
        self.assertTrue(audit_ledger().ok)

    def test_parallel_obligation_and_payment_traffic_on_the_same_player_keeps_the_record_consistent(self):
        company = ledger.get_or_create_account(AccountKind.COMPANY, 1)
        fund_account(company, 100_000)
        p = self.players[0]
        acct = ledger.player_account(p.pk)

        def open_ob(i):
            return lambda: obligations.open_obligation(company.pk, acct.pk, 1_000 * (i + 1), Nature.WAGE, key=f"o{i}",
                                                       reference_kind="t", reference_id=i, at=T0 + i)

        def pay(i):
            return lambda: ledger.transfer(company.pk, acct.pk, 500, Nature.SALE, key=f"p{i}", reference_kind="t",
                                           reference_id=i, at=T0 + i)
        self._run([open_ob(0), open_ob(1), pay(0), pay(1), open_ob(2), pay(2)])
        from rankings import live
        final = live.net_worth_of(p.pk)["value"]
        self.assertEqual(final, 1_000 + 2_000 + 3_000 + 1_500)
        rec = RankingHistorico.objects.get(category=Cat.NET_WORTH_RECORD.value)
        self.assertEqual(rec.value, final)                                      # o último estado é também o maior (só sobe)
        self.assertTrue(audit_ledger().ok)
        self.assertTrue(audit.audit_rankings()["ok"], audit.audit_rankings()["findings"])

    def test_player_actions_and_ledger_operations_in_parallel(self):
        """Ações do jogador (sequência de atividade) e operações financeiras (recorde de patrimônio) ao mesmo tempo."""
        company = ledger.get_or_create_account(AccountKind.COMPANY, 1)
        fund_account(company, 100_000)
        jobs = []
        for i, p in enumerate(self.players):
            jobs.append(lambda p=p: activity.record_action(p.pk, T0 + 3 * HOUR))
            jobs.append(lambda p=p, i=i: ledger.transfer(company.pk, ledger.player_account(p.pk).pk, 1_000 * (i + 1), Nature.SALE,
                                                         key=f"c{i}", reference_kind="t", reference_id=i, at=T0))
        self._run(jobs)
        self.assertEqual(RankingHistorico.objects.get(category=Cat.NET_WORTH_RECORD.value).value, 4_000)
        self.assertEqual(ActivityStreak.objects.count(), 4)
        self.assertTrue(audit.audit_rankings(at=T0 + 4 * HOUR)["ok"])


class QolSnapshotConcurrencyTests(TransactionTestCase):
    """Ações de jogadores (que mudam a QoL DEPOIS da referência) em paralelo com a finalização da snapshot."""

    N = 6

    def setUp(self):
        from decimal import Decimal
        from core.clock import ManualClock, use_clock
        from players import qol
        generate_world(get_scenario(**SMALL))
        install_test_role(self)
        self.clk = ManualClock(T0)
        with use_clock(self.clk):
            self.players = [create_player(Usuario.objects.create_user(f"q{i}")) for i in range(self.N)]
        qol.register_qol_base_provider("per_player", lambda p, at: Decimal(p.pk % 7) / Decimal(10))
        self.addCleanup(qol.clear_qol_base_providers)
        self.ref = T0 + HOUR
        from rankings import qol_snapshots
        qol_snapshots.ensure_open(T0)

    def _expected(self, p):
        from decimal import Decimal
        return Decimal("0.5") + Decimal(p.pk % 7) / Decimal(10)

    def _run(self, jobs):
        from core.clock import use_clock
        barrier = threading.Barrier(len(jobs))
        errors, results = [], [None] * len(jobs)

        def worker(i, job):
            try:
                with use_clock(self.clk):
                    barrier.wait(timeout=10)
                    results[i] = _retry(job)
            except Exception as exc:          # noqa: BLE001
                errors.append(exc)
            finally:
                close_old_connections()
                connection.close()
        threads = [threading.Thread(target=worker, args=(i, j)) for i, j in enumerate(jobs)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=90)
        self.assertEqual(errors, [])
        return results

    def test_actions_after_the_reference_in_parallel_with_finalize_keep_every_value_exact(self):
        from decimal import Decimal
        from players.actions import Action
        from players.services import EffectSpec, perform_action
        from rankings import qol_snapshots
        from rankings.models import QolSnapshot, QolSnapshotEntry
        self.clk.advance(seconds=HOUR + 20 * 60)
        act = [lambda p=p: perform_action(p.pk, Action.LEISURE, effect=EffectSpec("leisure:t", Decimal("0.5"), 5 * HOUR))
               for p in self.players[: self.N // 2]]                         # metade age (a QoL de AGORA muda: +0,5)
        fin = [lambda: qol_snapshots.finalize(self.ref, self.clk.now()) for _ in range(2)]     # duas varreduras concorrentes
        self._run(act + fin)
        snap = QolSnapshot.objects.get(reference_at=self.ref)
        self.assertEqual((snap.status, snap.eligible, snap.represented, snap.missing), ("complete", self.N, self.N, 0))
        self.assertEqual(QolSnapshotEntry.objects.filter(snapshot=snap).count(), self.N)      # uma entrada por jogador
        for p in self.players:
            e = QolSnapshotEntry.objects.get(snapshot=snap, player=p)
            self.assertEqual(e.qol, self._expected(p).quantize(Decimal("1e-12")), p.pk)       # valor DA referência, não o atual
            self.assertEqual(e.explained["computed_at"], self.ref)
        self.assertEqual({e.source for e in snap.entries.all()} - {"advance", "sweep"}, set())

    def test_actions_racing_with_the_sweep_never_produce_a_complete_snapshot_with_wrong_values(self):
        """Repetição: a ordem entre ações e varredura varia; o invariante vale em qualquer ordem."""
        from decimal import Decimal
        from players.actions import Action
        from players.services import EffectSpec, perform_action
        from rankings import qol_snapshots
        from rankings.models import QolSnapshot, QolSnapshotEntry
        self.clk.advance(seconds=HOUR + 5 * 60)
        jobs = []
        for p in self.players:
            jobs.append(lambda p=p: perform_action(p.pk, Action.LEISURE, effect=EffectSpec("leisure:t", Decimal("1"), 5 * HOUR)))
        jobs.append(lambda: qol_snapshots.finalize(self.ref, self.clk.now()))
        self._run(jobs)
        snap = QolSnapshot.objects.get(reference_at=self.ref)
        self.assertIn(snap.status, ("complete", "incomplete"))
        for e in QolSnapshotEntry.objects.filter(snapshot=snap):
            self.assertEqual(e.qol, self._expected(e.player).quantize(Decimal("1e-12")))     # nunca um valor de outro instante
        if snap.status == "complete":
            self.assertEqual(snap.represented, self.N)
        self.assertEqual(snap.status, "complete")                           # a captura no avanço torna o caso comum completo


ON_PG = connection.vendor == "postgresql"


class OutboxConcurrencyTests(TransactionTestCase):
    """Outbox de atividade: processadores concorrentes não duplicam nem invertem a ordem por jogador; ações e processadores juntos."""

    def setUp(self):
        from core.clock import ManualClock, use_clock
        generate_world(get_scenario(**SMALL))
        install_test_role(self)
        self.clk = ManualClock(T0)
        with use_clock(self.clk):
            self.players = [create_player(Usuario.objects.create_user(f"o{i}")) for i in range(4)]
        self.calls, self.calls_lock = [], threading.Lock()

    def _seed(self, p, instants):
        from rankings.models import ActivityEvent
        for at in instants:
            ActivityEvent.objects.create(player_id=p.pk, action_id="leisure", at=at)

    def _logging_record_action(self):
        original = activity.record_action

        def wrapper(pid, at=None):
            with self.calls_lock:
                self.calls.append(("start", pid, at))
            out = original(pid, at)
            with self.calls_lock:
                self.calls.append(("end", pid, at))
            return out
        return wrapper

    def _run(self, jobs):
        from core.clock import use_clock
        barrier = threading.Barrier(len(jobs))
        errors, results = [], [None] * len(jobs)

        def worker(i, job):
            try:
                with use_clock(self.clk):
                    barrier.wait(timeout=10)
                    results[i] = _retry(job)
            except Exception as exc:          # noqa: BLE001
                errors.append(exc)
            finally:
                close_old_connections()
                connection.close()

        threads = [threading.Thread(target=worker, args=(i, j)) for i, j in enumerate(jobs)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=90)
        self.assertEqual(errors, [])
        return results

    def test_concurrent_processors_handle_each_event_once_and_in_order(self):
        from unittest import mock
        from rankings import outbox
        from rankings.models import ActivityEvent
        for k, p in enumerate(self.players[:3]):
            instants = [T0 - (20 - k) * HOUR + i * HOUR for i in range(6)]
            self._seed(p, instants[::-1])                       # ids em ordem INVERSA da cronológica
        with mock.patch.object(activity, "record_action", self._logging_record_action()):
            self._run([lambda: outbox.process_pending() for _ in range(4)])
        starts = [(pid, at) for kind, pid, at in self.calls if kind == "start"]
        if ON_PG:        # a trava por jogador só existe em PostgreSQL; em SQLite o banco serializa escritas e há retentativas
            self.assertEqual(len(starts), 18)                   # cada evento processado UMA vez
            self.assertEqual(len(set(starts)), 18)
            for p in self.players[:3]:
                seq = [at for pid, at in starts if pid == p.pk]
                self.assertEqual(seq, sorted(seq), "inversão de ordem no jogador")
        outbox.process_pending()                                # em SQLite, o que perdeu para um bloqueio é retomado
        self.assertEqual(ActivityEvent.objects.filter(processed_at__isnull=True).count(), 0)
        if ON_PG:
            self.assertEqual(ActivityEvent.objects.filter(attempts__gt=0).count(), 0)
        for k, p in enumerate(self.players[:3]):
            st = ActivityStreak.objects.get(player=p)
            self.assertEqual((st.current_start, st.last_action_at), (T0 - (20 - k) * HOUR, T0 - (15 - k) * HOUR))
        self.assertTrue(audit.audit_rankings(at=T0)["ok"], audit.audit_rankings(at=T0)["findings"])

    @unittest.skipUnless(ON_PG, "exclusão por trava de linha do jogador (SELECT ... FOR UPDATE): só tem efeito em PostgreSQL")
    def test_a_later_event_waits_for_the_earlier_one_still_being_processed(self):
        """O processador A segura o evento 1 (no meio do processamento); o B, no MESMO jogador, não pode andar para o evento 2."""
        from unittest import mock
        from core.clock import use_clock
        from rankings import outbox
        p = self.players[0]
        self._seed(p, [T0 - 2 * HOUR, T0 - HOUR])
        in_first, release = threading.Event(), threading.Event()
        original = activity.record_action

        def slow_first(pid, at=None):
            with self.calls_lock:
                self.calls.append(("start", pid, at))
            if at == T0 - 2 * HOUR and not in_first.is_set():
                in_first.set()
                release.wait(timeout=20)
            out = original(pid, at)
            with self.calls_lock:
                self.calls.append(("end", pid, at))
            return out

        errors = []

        def runner():
            try:
                with use_clock(self.clk):
                    _retry(lambda: outbox.process_player(p.pk))
            except Exception as exc:    # noqa: BLE001
                errors.append(exc)
            finally:
                close_old_connections()
                connection.close()

        with mock.patch.object(activity, "record_action", slow_first):
            a = threading.Thread(target=runner)
            b = threading.Thread(target=runner)
            try:
                a.start()
                self.assertTrue(in_first.wait(timeout=20))
                b.start()
                time.sleep(0.5)                                 # B tem tempo de sobra para (indevidamente) andar
                with self.calls_lock:
                    started_during_hold = [c for c in self.calls if c[0] == "start"]
                self.assertEqual(started_during_hold, [("start", p.pk, T0 - 2 * HOUR)])   # nada posterior com o anterior preso
            finally:
                release.set()                                   # nunca deixa a thread presa segurando o banco
                a.join(timeout=30)
                if b.is_alive() or b.ident:
                    b.join(timeout=30)
        self.assertEqual(errors, [])
        starts = [(pid, at) for kind, pid, at in self.calls if kind == "start"]
        self.assertEqual(starts, [(p.pk, T0 - 2 * HOUR), (p.pk, T0 - HOUR)])        # ordem, uma vez cada
        self.assertEqual(ActivityStreak.objects.get(player=p).last_action_at, T0 - HOUR)

    def test_actions_and_processors_running_together_leave_every_event_processed(self):
        from players import registry
        from players.models import Player
        from rankings import outbox
        from rankings.models import ActivityEvent
        Player.objects.update(energy=100)

        def act(p):
            return lambda: registry.execute_action(p.pk, "leisure").ok
        jobs = [act(p) for p in self.players] + [lambda: outbox.process_pending() for _ in range(3)]
        results = self._run(jobs)
        self.assertEqual(results[:4], [True] * 4)
        self.assertEqual(ActivityEvent.objects.count(), 4)                      # uma ação confirmada = um evento
        outbox.process_pending()                                                # o que sobrou de corrida é recuperável
        self.assertEqual(ActivityEvent.objects.filter(processed_at__isnull=True).count(), 0)
        self.assertEqual(ActivityStreak.objects.count(), 4)
        self.assertTrue(audit.audit_rankings(at=T0)["ok"], audit.audit_rankings(at=T0)["findings"])

    def test_two_actions_of_the_same_player_in_parallel_both_record_in_order(self):
        from players import registry
        from players.models import Player
        from rankings import outbox
        from rankings.models import ActivityEvent
        p = self.players[0]
        Player.objects.filter(pk=p.pk).update(energy=100)
        res = self._run([lambda: registry.execute_action(p.pk, "leisure").ok for _ in range(2)])
        self.assertEqual(sorted(res), [True, True])
        self.assertEqual(ActivityEvent.objects.filter(player=p).count(), 2)
        outbox.process_pending()
        self.assertEqual(ActivityEvent.objects.filter(processed_at__isnull=True).count(), 0)
        self.assertEqual(ActivityStreak.objects.get(player=p).last_action_at, T0)
