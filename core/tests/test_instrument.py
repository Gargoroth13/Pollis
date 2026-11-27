from django.db import connection
from django.test import TestCase

from accounts.models import Usuario
from core.instrument import QueryCounter, stopwatch


class QueryCounterTests(TestCase):
    def test_counts_queries_and_db_time_without_debug_or_test_utilities(self):
        with QueryCounter() as q:
            list(Usuario.objects.all())
            Usuario.objects.count()
        self.assertEqual(q.count, 2)
        self.assertEqual(len(q), 2)
        self.assertGreaterEqual(q.db_seconds, 0)

    def test_does_not_count_outside_the_block_and_nests(self):
        with QueryCounter() as outer:
            Usuario.objects.count()
            with QueryCounter() as inner:
                Usuario.objects.count()
        Usuario.objects.count()
        self.assertEqual((outer.count, inner.count), (2, 1))

    def test_stops_counting_even_when_the_block_raises(self):
        q = QueryCounter()
        try:
            with q:
                Usuario.objects.count()
                raise RuntimeError
        except RuntimeError:
            pass
        Usuario.objects.count()
        self.assertEqual(q.count, 1)
        self.assertEqual(connection.execute_wrappers, [])

    def test_stopwatch(self):
        with stopwatch() as t:
            pass
        self.assertGreaterEqual(t(), 0)

    def test_runtime_code_does_not_import_django_test_utilities(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[2]
        offenders = []
        for f in root.rglob("*.py"):
            rel = f.relative_to(root).parts
            if "tests" in rel or f.name.startswith("test_") or "migrations" in rel or ".venv" in rel or "venv" in rel:
                continue
            if "django.test" in f.read_text(encoding="utf-8", errors="ignore"):
                offenders.append(str(f.relative_to(root)))
        self.assertEqual(offenders, [])
