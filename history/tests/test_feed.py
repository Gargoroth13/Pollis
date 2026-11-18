"""Página pública (12.1), arquivo permanente (12.10), prioridade (12.13) e performance (12.15)."""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from history import views
from history.constants import Category, Priority
from history.models import NewsItem
from history.publish import publish
from core.timeline import game_ts
from players.tests.base import T0, PlayerTestCase

from .base import AuditMixin

DAY = 86400


def news(at, category=Category.ECONOMY, priority=Priority.MINOR_ECONOMIC, n=[0], **kw):
    n[0] += 1
    return publish("economy.price_up", {"product": f"p{n[0]}", "pct": "9"}, category=category, priority=priority, at=at, **kw).item


class FeedTests(AuditMixin, PlayerTestCase):
    def test_newest_first_and_the_five_categories_plus_all_are_filters(self):
        for i in range(4):
            news(T0 + i * 60)
        items = views.feed()["items"]
        self.assertEqual([i["at"] for i in items], sorted((i["at"] for i in items), reverse=True))
        self.assertEqual([f["label"] for f in views.filters()], ["Todas", "Política", "Economia", "Conflito", "Sociedade", "Marco"])

    def test_simultaneous_news_are_ordered_by_priority_without_exposing_it(self):
        low = news(T0, priority=Priority.MINOR_ECONOMIC)
        high = news(T0, category=Category.POLITICS, priority=Priority.GOVERNMENT_CHANGE)
        mid = news(T0, priority=Priority.BANKRUPTCY)
        items = views.feed()["items"]
        self.assertEqual([i["id"] for i in items], [high.pk, mid.pk, low.pk])
        self.assertNotIn("priority", items[0])

    def test_each_category_filter_returns_only_that_category(self):
        for cat in Category:
            news(T0, category=cat)
        for cat in Category:
            got = views.feed(category=cat.value)["items"]
            self.assertEqual({i["category"] for i in got}, {cat.value})
            self.assertEqual(len(got), 1)
        self.assertEqual(views.feed(category=Category.MILESTONE.value)["items"][0]["category_label"], "Marco")

    def test_invalid_filter_and_limit_are_errors_not_an_empty_feed(self):
        with self.assertRaises(ValueError):
            views.feed(category="sports")
        for bad in (0, -1, True, "3"):
            with self.assertRaises(ValueError):
                views.feed(limit=bad)

    def test_the_cursor_walks_every_item_exactly_once_even_with_ties_and_new_arrivals(self):
        made = []
        for i in range(23):
            made.append(news(T0 + (i // 3) * 60, priority=Priority(1 + i % 7)))
        seen, page = [], views.feed(limit=5)
        seen += [i["id"] for i in page["items"]]
        news(T0 + 10_000)                                       # chega notícia nova no meio da leitura: não desloca as páginas já lidas
        while page["next"] is not None:
            page = views.feed(limit=5, after=page["next"])
            seen += [i["id"] for i in page["items"]]
        self.assertEqual(sorted(seen), sorted(m.pk for m in made))
        self.assertEqual(len(seen), len(set(seen)))

    def test_the_last_page_has_no_cursor_and_an_exact_page_does_not_invent_one(self):
        for i in range(5):
            news(T0 + i)
        page = views.feed(limit=5)
        self.assertEqual((len(page["items"]), page["next"]), (5, None))
        self.assertEqual(views.feed()["items"][0]["id"], page["items"][0]["id"])

    def test_the_page_size_is_capped(self):
        for i in range(3):
            news(T0 + i)
        self.assertEqual(len(views.feed(limit=10_000)["items"]), 3)

    def test_the_reference_links_to_a_page_only_when_the_page_exists(self):
        news(T0, ref=("product", "steel"))
        self.assertEqual(views.feed()["items"][0]["ref"], {"kind": "product", "id": "steel", "path": None})
        views.register_ref_resolver("product", lambda ref_id: f"/mercado/{ref_id}")
        self.assertEqual(views.feed()["items"][0]["ref"]["path"], "/mercado/steel")
        news(T0 + 1)
        self.assertIsNone(views.feed()["items"][0]["ref"])


class ArchiveTests(AuditMixin, PlayerTestCase):
    def test_old_news_stay_available_after_many_new_ones_and_the_archive_groups_by_month(self):
        old = news(game_ts(2026, 3, 15, 10), category=Category.MILESTONE)
        for i in range(60):
            news(game_ts(2027, 1, 1 + i % 28, 12) + i)
        self.assertEqual(views.archive_month(2026, 3)[0]["id"], old.pk)
        self.assertEqual(views.archive_index()[-1], {"year": 2026, "month": 3, "count": 1})
        self.assertEqual(views.archive_index()[0], {"year": 2027, "month": 1, "count": 60})
        self.assertEqual([m["id"] for m in views.milestones()], [old.pk])
        self.assertEqual(NewsItem.objects.count(), 61)

    def test_the_month_is_the_game_calendar_month_at_the_event_instant(self):
        a = news(game_ts(2026, 10, 31, 23, 59))
        b = news(game_ts(2026, 11, 1, 0, 0))
        self.assertEqual([i["id"] for i in views.archive_month(2026, 10)], [a.pk])
        self.assertEqual([i["id"] for i in views.archive_month(2026, 11)], [b.pk])

    def test_archive_month_is_chronological_and_filterable(self):
        x = news(game_ts(2026, 10, 3), category=Category.POLITICS)
        y = news(game_ts(2026, 10, 2), category=Category.ECONOMY)
        self.assertEqual([i["id"] for i in views.archive_month(2026, 10)], [y.pk, x.pk])
        self.assertEqual([i["id"] for i in views.archive_month(2026, 10, "politics")], [x.pk])
        with self.assertRaises(ValueError):
            views.archive_month(2026, 10, "x")


class PerformanceTests(AuditMixin, PlayerTestCase):
    """12.15: o feed e o arquivo usam só as notícias já prontas; não percorrem transações, lançamentos nem estoque."""

    def test_feed_pages_cost_one_query_and_never_touch_raw_history_tables(self):
        for i in range(120):
            news(T0 + i)
        with CaptureQueriesContext(connection) as ctx:
            page = views.feed(limit=20)
            views.feed(limit=20, after=page["next"])
            views.feed(category="economy")
            views.archive_index()
            views.milestones()
        self.assertEqual(len(ctx.captured_queries), 5)
        for q in ctx.captured_queries:
            self.assertIn("history_newsitem", q["sql"])
            for raw in ("market_", "ledger_", "companies_", "inventory_"):
                self.assertNotIn(raw, q["sql"])

    def test_the_query_count_does_not_grow_with_the_number_of_news(self):
        counts = []
        for total in (5, 80):
            NewsItem.objects.all()            # lê
            for i in range(total):
                news(T0 + 1_000_000 + len(counts) * 10_000 + i)
            with CaptureQueriesContext(connection) as ctx:
                views.feed(limit=20)
            counts.append(len(ctx.captured_queries))
        self.assertEqual(counts[0], counts[1])
