from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from catalog.definitions import PRODUCTS, KNOWN_GAPS
from catalog.integrity import check_integrity
from catalog.loader import sync_catalog
from catalog.models import FoodProfile, Product, Recipe, RecipeInput

from .base import CatalogTestCase


class IntegrityReportTests(CatalogTestCase):
    def test_the_loaded_catalog_has_no_error(self):
        r = check_integrity()
        self.assertTrue(r.ok, r.errors)
        self.assertEqual(r.stats["products"], 73)

    def test_design_pending_is_reported_but_does_not_fail(self):
        r = check_integrity()
        self.assertEqual(r.pending_codes, sorted(g.code for g in KNOWN_GAPS))
        self.assertEqual(r.codes, [])
        Product.objects.filter(key="iron").update(base_price=None)
        r = check_integrity()
        self.assertIn("BASE_PRICE_UNSPECIFIED", r.pending_codes)        # pendência de design: listada, não reprova
        self.assertEqual(r.codes, ["PRODUCT_DIFFERS_FROM_DEFINITIONS"])  # mas o banco divergiu das definições

    def test_a_cycle_written_directly_to_the_database_is_detected(self):
        RecipeInput.objects.create(recipe=Recipe.objects.get(product__key="iron") if Recipe.objects.filter(product__key="iron").exists()
                                   else Recipe.objects.create(product=Product.objects.get(key="iron")),
                                   ingredient=Product.objects.get(key="steel"), position=1)
        r = check_integrity()
        self.assertIn("RAW_WITH_RECIPE", r.codes)
        self.assertIn("RECIPE_CYCLE", r.codes)
        self.assertIn("PRODUCT_DIFFERS_FROM_DEFINITIONS", r.codes)

    def test_a_product_missing_from_the_database_is_detected_as_not_synced(self):
        FoodProfile.objects.filter(product__key="soda").delete()
        Recipe.objects.filter(product__key="soda").delete()
        Product.objects.get(key="soda").delete()
        r = check_integrity()
        self.assertIn("CATALOG_NOT_SYNCED", r.codes)
        self.assertEqual(r.subjects("CATALOG_NOT_SYNCED"), ["soda"])

    def test_an_extra_product_not_in_the_definitions_is_detected(self):
        Product.objects.create(key="mystery", name="Mistério", sector="agro")
        r = check_integrity()
        self.assertEqual(r.subjects("PRODUCT_NOT_IN_DEFINITIONS"), ["mystery"])

    def test_a_value_changed_in_the_database_is_detected_and_a_sync_repairs_it(self):
        Product.objects.filter(key="steel").update(name="Aço adulterado")
        self.assertEqual(check_integrity().subjects("PRODUCT_DIFFERS_FROM_DEFINITIONS"), ["steel"])
        sync_catalog()
        self.assertTrue(check_integrity().ok)

    def test_a_changed_classification_or_channel_in_the_database_is_detected(self):
        Product.objects.filter(key="military_armor").update(commercial_channels=["army_procurement", "retail_sale"])
        r = check_integrity()
        self.assertIn("ARMY_PRODUCT_IN_RETAIL", r.codes)
        self.assertIn("PRODUCT_DIFFERS_FROM_DEFINITIONS", r.codes)
        Product.objects.filter(key="steel").update(category="")
        self.assertIn("CATEGORY_MISSING", check_integrity().codes)

    def test_a_broken_resource_link_is_detected(self):
        Product.objects.filter(key="gold").update(resource=None)
        r = check_integrity()
        self.assertIn("RESOURCE_WITHOUT_PRODUCT", r.codes)


class EmptyCatalogTests(TestCase):
    def test_empty_catalog_is_an_error(self):
        self.assertEqual(check_integrity().codes, ["EMPTY_CATALOG"])


class CommandTests(TestCase):
    def test_sync_then_check(self):
        out = StringIO()
        call_command("sync_catalog", stdout=out)
        self.assertIn("criados=73", out.getvalue())
        out = StringIO()
        call_command("sync_catalog", stdout=out)
        self.assertIn("criados=0 atualizados=0 inalterados=73", out.getvalue())
        out = StringIO()
        call_command("check_catalog", "--pending", stdout=out)
        self.assertIn("integridade: OK", out.getvalue())
        self.assertIn("PENDÊNCIA GAP_OPERATIONAL_MATERIALS_UNDEFINED", out.getvalue())

    def test_check_fails_on_an_empty_catalog(self):
        with self.assertRaises(CommandError):
            call_command("check_catalog", stdout=StringIO())

    def test_check_fails_with_a_real_error_but_not_with_pending(self):
        call_command("sync_catalog", stdout=StringIO())
        call_command("check_catalog", stdout=StringIO())            # pendências existem e NÃO reprovam
        Product.objects.create(key="mystery", name="Mistério", sector="agro")
        with self.assertRaises(CommandError):
            call_command("check_catalog", stdout=StringIO())
