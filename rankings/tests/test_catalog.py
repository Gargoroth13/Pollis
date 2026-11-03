"""Catálogo das 15 categorias: numeração (ao vivo 1–11, históricas 12–15), estados explícitos, nada removido e sem dados inventados."""
from django.test import SimpleTestCase

from rankings import params
from rankings.constants import CATEGORIES, HISTORICAL, LIVE, Cat, Group, Status, spec


class CatalogTests(SimpleTestCase):
    def test_fifteen_categories_numbered_in_document_order(self):
        self.assertEqual([c.number for c in CATEGORIES], list(range(1, 16)))
        self.assertEqual([c.number for c in LIVE], list(range(1, 12)))
        self.assertEqual([c.number for c in HISTORICAL], [12, 13, 14, 15])
        self.assertEqual(len({c.key for c in CATEGORIES}), 15)

    def test_design_references_follow_the_document(self):
        self.assertEqual([c.design_ref for c in LIVE], [f"14.3.{i}" for i in range(1, 12)])
        self.assertEqual([c.design_ref for c in HISTORICAL], [f"14.4.{i}" for i in range(1, 5)])

    def test_groups(self):
        self.assertTrue(all(c.group == Group.LIVE for c in LIVE))
        self.assertTrue(all(c.group == Group.HISTORICAL for c in HISTORICAL))

    def test_active_categories_in_this_delivery(self):
        active = {c.key for c in CATEGORIES if c.status == Status.ACTIVE}
        self.assertEqual(active, {Cat.NET_WORTH, Cat.TAXPAYER, Cat.OLDEST_ACCOUNT, Cat.ACTIVE_TIME,
                                  Cat.NET_WORTH_RECORD, Cat.ACTIVE_TIME_RECORD})

    def test_political_influence_is_out_of_scope_and_qol_is_pending_design(self):
        self.assertEqual(spec(Cat.POLITICAL_INFLUENCE).status, Status.OUT_OF_SCOPE)
        self.assertEqual(spec(Cat.QOL).status, Status.PENDING_DESIGN)

    def test_every_non_active_category_names_what_it_depends_on(self):
        for c in CATEGORIES:
            if c.status != Status.ACTIVE:
                self.assertTrue(c.depends_on, c.key)
            else:
                self.assertTrue(c.source, c.key)

    def test_windows_and_gap_are_the_design_values(self):
        self.assertEqual((params.PRODUCTION_WINDOW_DAYS, params.TAXPAYER_WINDOW_DAYS), (14, 30))
        self.assertEqual(params.STREAK_MAX_GAP_SECONDS, 72 * 3600)
        self.assertEqual(spec(Cat.TAXPAYER).window_days, 30)
        self.assertEqual(spec(Cat.PRODUCTION).window_days, 14)

    def test_unknown_category_is_an_error_not_an_empty_ranking(self):
        with self.assertRaises(ValueError):
            spec("nope")
