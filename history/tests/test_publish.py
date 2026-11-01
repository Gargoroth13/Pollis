from decimal import Decimal

from django.db import IntegrityError, transaction

from history import texts
from history.constants import Category, Priority, Status
from history.models import NewsImmutableError, NewsItem
from history.publish import jsonable, publish
from history.texts import TemplateError
from players.tests.base import T0, PlayerTestCase

from .base import AuditMixin

DAY = 86400


def up(seed="a", **kw):
    kw.setdefault("at", T0)
    return publish("economy.price_up", {"product": "aço", "pct": "8"}, category=Category.ECONOMY, priority=Priority.MINOR_ECONOMIC, **kw)


class PublishTests(AuditMixin, PlayerTestCase):
    def test_a_news_item_has_the_fields_of_12_1(self):
        res = publish("economy.price_up", {"product": "aço", "pct": "8"}, category=Category.ECONOMY, priority=Priority.MINOR_ECONOMIC, at=T0,
                      ref=("product", "steel"), structured={"pct": Decimal("8.000000")})
        self.assertEqual(res.status, Status.PUBLISHED)
        n = res.item
        self.assertEqual((n.at, n.category, n.ref_kind, n.ref_id), (T0, "economy", "product", "steel"))
        self.assertIn("aço", n.headline)
        self.assertIn("8%", n.headline + n.body)
        self.assertEqual(n.data, {"pct": "8.000000"})               # Decimal exato, nunca float
        self.assertEqual((n.year, n.month), (2026, 10))
        self.assertEqual(NewsItem.objects.count(), 1)

    def test_at_defaults_to_the_game_clock_and_published_at_is_the_clock(self):
        n = publish("economy.price_up", {"product": "x", "pct": "9"}, category=Category.ECONOMY, priority=Priority.MINOR_ECONOMIC).item
        self.assertEqual((n.at, n.published_at), (T0, T0))
        late = publish("economy.price_up", {"product": "x", "pct": "9"}, category=Category.ECONOMY, priority=Priority.MINOR_ECONOMIC, at=T0 - DAY).item
        self.assertEqual((late.at, late.published_at), (T0 - DAY, T0))      # acontecimento passado: o instante lógico é o do fato

    def test_same_input_gives_the_same_text_and_different_seeds_use_every_variation(self):
        a = up(dedupe_key="k1").item
        self.assertEqual(texts.render("economy.price_up", {"product": "aço", "pct": "8"}, "k1")[0], a.variant)
        seen = {texts.pick_variant("economy.price_up", f"seed{i}") for i in range(200)}
        self.assertEqual(seen, set(range(texts.variant_count("economy.price_up"))))

    def test_every_template_has_at_least_one_variant_and_all_fields_render(self):
        sample = {"product": "p", "pct": "1", "company": "C", "type_phrase": "Industrial", "stars": 5, "office": "Presidente", "winner": "J", "where": "",
                  "seats": 5, "office_phrase": "presidencial", "deposed": "A", "new": "B", "law": "L", "what": "alteração em", "what_short": "alteração",
                  "what_the": "a alteração", "yes": 3, "required": 3, "in_force_text": "t", "faction": "F", "target": "T"}
        for key in texts.keys():
            for i in range(texts.variant_count(key)):
                headline, body = texts._TEMPLATES[key][i]
                self.assertTrue(headline.format(**sample) and body.format(**sample), key)

    def test_a_missing_template_field_is_an_error_never_half_a_text(self):
        with self.assertRaises(TemplateError):
            publish("economy.price_up", {"product": "aço"}, category=Category.ECONOMY, priority=Priority.MINOR_ECONOMIC)
        with self.assertRaises(TemplateError):
            publish("nope", {}, category=Category.ECONOMY, priority=Priority.MINOR_ECONOMIC)
        self.assertEqual(NewsItem.objects.count(), 0)

    def test_category_and_priority_must_be_the_enums(self):
        with self.assertRaises(ValueError):
            publish("economy.price_up", {"product": "a", "pct": "1"}, category="economy", priority=Priority.MINOR_ECONOMIC)
        with self.assertRaises(ValueError):
            publish("economy.price_up", {"product": "a", "pct": "1"}, category=Category.ECONOMY, priority=7)

    def test_percent_format_is_ptbr_with_at_most_one_decimal_and_commercial_rounding(self):
        f = texts.fmt_pct
        self.assertEqual([f(Decimal(v)) for v in ("8", "8.0", "53.4", "53.45", "53.449", "100", "0.05", "12.04")], ["8", "8", "53,4", "53,5", "53,4", "100", "0,1", "12"])


class IdempotencyTests(AuditMixin, PlayerTestCase):
    def test_the_same_dedupe_key_publishes_once(self):
        first = up(dedupe_key="m:1")
        again = up(dedupe_key="m:1", at=T0 + DAY)
        self.assertEqual((first.status, again.status), (Status.PUBLISHED, Status.DUPLICATE))
        self.assertEqual(again.item.pk, first.item.pk)
        self.assertEqual(NewsItem.objects.count(), 1)

    def test_the_database_itself_refuses_a_duplicate_key(self):
        up(dedupe_key="m:1")
        with self.assertRaises(IntegrityError), transaction.atomic():
            NewsItem.objects.create(at=T0, published_at=T0, year=2026, month=10, category="economy", priority=7, template_key="economy.price_up",
                                    variant=0, headline="x", body="y", dedupe_key="m:1")

    def test_news_without_a_key_may_repeat(self):
        up(), up()
        self.assertEqual(NewsItem.objects.count(), 2)


class MinIntervalTests(AuditMixin, PlayerTestCase):
    def pub(self, at, indicator="price_trend:steel"):
        return up(at=at, indicator=indicator, min_interval=3 * DAY)

    def test_a_second_news_of_the_same_indicator_inside_the_interval_is_suppressed(self):
        self.assertTrue(self.pub(T0).ok)
        res = self.pub(T0 + 3 * DAY - 1)
        self.assertEqual((res.status, res.reason), (Status.SUPPRESSED, "min_interval"))
        self.assertEqual(NewsItem.objects.count(), 1)

    def test_exactly_the_interval_later_is_allowed(self):
        self.pub(T0)
        self.assertTrue(self.pub(T0 + 3 * DAY).ok)

    def test_the_interval_also_protects_against_a_late_event_before_a_published_one(self):
        self.pub(T0)
        self.assertEqual(self.pub(T0 - 3 * DAY + 1).status, Status.SUPPRESSED)
        self.assertTrue(self.pub(T0 - 3 * DAY).ok)

    def test_other_indicators_are_independent(self):
        self.pub(T0)
        self.assertTrue(self.pub(T0 + 60, indicator="price_trend:wheat").ok)


class PermanenceTests(AuditMixin, PlayerTestCase):
    def test_news_cannot_be_edited_or_deleted_one_by_one_or_in_bulk(self):
        n = up().item
        original = n.headline
        n.headline = "outra"
        with self.assertRaises(NewsImmutableError):
            n.save()
        with self.assertRaises(NewsImmutableError):
            n.delete()
        with self.assertRaises(NewsImmutableError):
            NewsItem.objects.all().update(headline="x")
        with self.assertRaises(NewsImmutableError):
            NewsItem.objects.all().delete()
        self.assertEqual(NewsItem.objects.get().headline, original)

    def test_the_database_refuses_an_empty_headline_and_an_invalid_priority_or_month(self):
        base = dict(at=T0, published_at=T0, year=2026, month=10, category="economy", priority=7, template_key="economy.price_up", variant=0, headline="h", body="b")
        for bad in ({"headline": ""}, {"priority": 0}, {"priority": 8}, {"month": 13}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                NewsItem.objects.create(**{**base, **bad})


class JsonableTests(PlayerTestCase):
    def test_decimals_become_exact_text_recursively(self):
        self.assertEqual(jsonable({"a": [Decimal("1.50"), {"b": Decimal("0.1")}], "c": 3}), {"a": ["1.50", {"b": "0.1"}], "c": 3})
