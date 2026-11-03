"""
Concorrência dos recordes e das sequências. Em PostgreSQL as transações disputam as linhas com `SELECT ... FOR UPDATE`; em SQLite o
próprio banco serializa as escritas. O teste verifica a PROPRIEDADE (uma linha por jogador/categoria, o recorde é o máximo da fonte,
auditoria limpa), que vale nos dois.
"""
import threading
import time

from django.db import OperationalError, close_old_connections, connection
from django.test import TransactionTestCase

from accounts.models import Usuario
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger import services as ledger
from ledger.tests.base import fund_account, install_test_role
from players.services import create_player
from rankings import activity, audit, records
from rankings.constants import Cat
from rankings.models import ActivityStreak, RankingHistorico

T0 = 1_791_212_400
HOUR, DAY = 3600, 86400


def _retry(fn, attempts=80):
    for _ in range(attempts):
        try:
            return fn()
        except OperationalError:           # SQLite: banco bloqueado por outra thread
            time.sleep(0.02)
    raise AssertionError("não conseguiu executar após várias tentativas")


class RankingsConcurrencyTests(TransactionTestCase):
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
