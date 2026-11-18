"""
Concorrência do Histórico. A unicidade do marco e da chave de idempotência é garantida pelo BANCO (restrição única parcial), então vale em
SQLite e PostgreSQL; a corrida real entre transações abertas ao mesmo tempo (a segunda espera a primeira e recebe o conflito) só ocorre em
PostgreSQL (`CROSS_ROW`).
"""
import unittest

from django.db import connection
from django.test import TransactionTestCase

from accounts.models import Usuario
from companies import services
from core.models import WorldClock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from history import news
from history.audit import audit_history
from history.models import NewsItem
from ledger import services as ledger
from ledger.tests.base import fund_account, install_test_role
from ledger.tests.test_scenario_concurrency import run_together
from players.services import create_player
from players.tests.base import T0

ON_PG = connection.vendor == "postgresql"
CROSS_ROW = unittest.skipUnless(ON_PG, "corrida entre transações abertas: só PostgreSQL a reproduz")
REAL = 100


class HistoryConcurrencyTests(TransactionTestCase):
    def setUp(self):
        install_test_role(self)
        generate_world(get_scenario(**SMALL))
        WorldClock.load()
        self.players = [create_player(Usuario.objects.create_user(f"h{n}")) for n in range(4)]
        for p in self.players:
            fund_account(ledger.player_account(p.pk), 200_000 * REAL)

    def assertClean(self):
        report = audit_history()
        self.assertTrue(report.ok, report.findings)

    def test_simultaneous_first_foundings_of_a_type_publish_exactly_one_milestone(self):
        for round_ in range(3):
            kind = ("industrial", "services", "matrix")[round_]
            jobs = run_together(*[lambda p=p, n=n: services.found_company(p.pk, kind, f"E{round_}{n}", 0) for n, p in enumerate(self.players)])
            self.assertTrue(all(j.result.ok for j in jobs), [j.result for j in jobs])
            self.assertEqual(NewsItem.objects.filter(dedupe_key=f"milestone:first_company:{kind}").count(), 1)
        self.assertEqual(NewsItem.objects.filter(category="milestone").count(), 3)
        self.assertClean()

    @CROSS_ROW
    def test_simultaneous_publication_of_the_same_event_is_idempotent(self):
        for _ in range(5):
            jobs = run_together(*[lambda: news.company_bankrupt(42, "Atlas", 5, T0) for _ in range(6)])
            self.assertEqual(sorted(j.result.status for j in jobs).count("published"), 1, [j.result for j in jobs])
            self.assertEqual(NewsItem.objects.filter(dedupe_key="bankruptcy:42").count(), 1)
            with connection.cursor() as cur:                       # limpa para a próxima rodada (SQL: o ORM recusa apagar, de propósito)
                cur.execute("DELETE FROM history_newsitem")
        self.assertClean()
