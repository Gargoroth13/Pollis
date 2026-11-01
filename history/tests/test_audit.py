from decimal import Decimal

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection

from history import news
from history.audit import audit_history
from history.constants import Office
from history.models import NewsItem
from players.tests.base import T0, PlayerTestCase

from .base import AuditMixin


class AuditTests(AuditMixin, PlayerTestCase):
    audit_history_at_end = False

    def corrupt(self, pk, **fields):
        cols = ", ".join(f"{k} = %s" for k in fields)
        with connection.cursor() as c:                         # o ORM recusa o update de propósito (12.10); só o SQL adultera
            c.execute(f"UPDATE history_newsitem SET {cols} WHERE id = %s", [*fields.values(), pk])

    def test_clean_history_passes_and_the_command_reports_it(self):
        news.election_concluded(Office.PRESIDENT, 1, "A", 534, 1000, T0)
        news.company_bankrupt(1, "X", 5, T0)
        self.assertTrue(audit_history().ok)
        call_command("audit_history", stdout=StringIO())

    def test_a_wrong_election_percentage_is_found(self):
        n = news.election_concluded(Office.PRESIDENT, 1, "A", 534, 1000, T0).item
        self.corrupt(n.pk, body="A venceu com 99% dos votos.")
        codes = {f["code"] for f in audit_history().findings}
        self.assertEqual(codes, {"ELECTION_PCT_MISMATCH"})
        with self.assertRaises(CommandError):
            call_command("audit_history", stdout=StringIO())

    def test_a_bankruptcy_below_the_minimum_stars_is_found(self):
        n = news.company_bankrupt(1, "X", 5, T0).item
        self.corrupt(n.pk, data='{"stars": 3}')
        self.assertIn("BANKRUPTCY_BELOW_MIN_STARS", {f["code"] for f in audit_history().findings})

    def test_a_wrong_archive_month_and_an_unknown_template_are_found(self):
        n = news.company_bankrupt(1, "X", 5, T0).item
        self.corrupt(n.pk, month=3, template_key="gone")
        self.assertEqual({f["code"] for f in audit_history().findings}, {"ARCHIVE_MONTH_MISMATCH", "UNKNOWN_TEMPLATE"})

    def test_a_milestone_outside_its_category_is_found(self):
        n = news.company_founded(1, "X", "retail", T0).item
        self.corrupt(n.pk, category="economy")
        self.assertIn("MILESTONE_NOT_IN_MILESTONE_CATEGORY", {f["code"] for f in audit_history().findings})
