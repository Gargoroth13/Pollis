from dataclasses import replace
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import TestCase

from catalog import loader
from catalog.constants import Sector
from catalog.definitions import PRODUCTS, InputDef
from catalog.loader import CatalogDefinitionError, load_from_db, sync_catalog
from catalog.models import FoodProfile, Product, Recipe, RecipeInput

D = Decimal


class SyncTests(TestCase):
    def test_first_sync_creates_everything(self):
        r = sync_catalog()
        self.assertEqual((r.created, r.updated, r.unchanged), (73, 0, 0))
        self.assertEqual((Product.objects.count(), Recipe.objects.count(), FoodProfile.objects.count()), (73, 41, 7))
        self.assertEqual(RecipeInput.objects.count(), sum(len(p.inputs or ()) for p in PRODUCTS))

    def test_sync_is_idempotent(self):
        sync_catalog()
        ids = list(Product.objects.values_list("id", "key"))
        counts = (Recipe.objects.count(), RecipeInput.objects.count(), FoodProfile.objects.count())
        r = sync_catalog()
        self.assertEqual((r.created, r.updated, r.unchanged), (0, 0, 73))
        self.assertEqual(list(Product.objects.values_list("id", "key")), ids)
        self.assertEqual((Recipe.objects.count(), RecipeInput.objects.count(), FoodProfile.objects.count()), counts)

    def test_the_database_reads_back_exactly_as_defined(self):
        sync_catalog()
        self.assertEqual(list(load_from_db().values()), list(PRODUCTS))

    def test_pending_design_does_not_block_the_load(self):
        r = sync_catalog()
        self.assertTrue(r.report.ok)
        self.assertGreater(len(r.report.pending), 0)

    def test_inputs_keep_the_order_of_the_design_document(self):
        sync_catalog()
        self.assertEqual([i.ingredient.key for i in Product.objects.get(key="hamburger").recipe.inputs.all()],
                         ["cheese", "processed_meat", "bread"])


class InvalidDefinitionsTests(TestCase):
    def test_definitions_with_an_error_are_not_loaded_at_all(self):
        bad = [replace(p, inputs=(InputDef("iron"), InputDef("ghost"))) if p.key == "steel" else p for p in PRODUCTS]
        with self.assertRaises(CatalogDefinitionError) as cm:
            sync_catalog(bad)
        self.assertIn("INGREDIENT_NOT_FOUND", cm.exception.report.codes)
        self.assertEqual(Product.objects.count(), 0)

    def test_a_cycle_is_not_loaded(self):
        bad = [replace(p, sector=Sector.INDUSTRIAL_PRODUCTION, resource=None, inputs=(InputDef("steel"),)) if p.key == "coal" else p
               for p in PRODUCTS]
        with self.assertRaises(CatalogDefinitionError):
            sync_catalog(bad)
        self.assertEqual(Product.objects.count(), 0)

    def test_the_load_is_atomic(self):
        """Falha DEPOIS de gravar produtos e receitas: nada fica."""
        with mock.patch.object(loader.FoodProfile.objects, "update_or_create", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                sync_catalog()
        self.assertEqual((Product.objects.count(), Recipe.objects.count(), RecipeInput.objects.count()), (0, 0, 0))
        sync_catalog()
        self.assertEqual(Product.objects.count(), 73)


class StableIdentityTests(TestCase):
    def setUp(self):
        sync_catalog()

    def test_renaming_changes_the_name_and_keeps_the_identity(self):
        pk = Product.objects.get(key="steel").pk
        renamed = [replace(p, name="Aço carbono") if p.key == "steel" else p for p in PRODUCTS]
        r = sync_catalog(renamed)
        self.assertEqual((r.updated, r.unchanged), (1, 72))
        p = Product.objects.get(key="steel")
        self.assertEqual((p.pk, p.name), (pk, "Aço carbono"))
        self.assertEqual(RecipeInput.objects.filter(ingredient=p).count(), sum(1 for q in PRODUCTS if q.inputs and any(i.key == "steel" for i in q.inputs)))

    def test_the_key_cannot_be_changed_on_a_saved_product(self):
        p = Product.objects.get(key="steel")
        p.key = "acero"
        with self.assertRaises(ValueError):
            p.save()
        self.assertTrue(Product.objects.filter(key="steel").exists())

    def test_a_changed_recipe_is_replaced_not_duplicated(self):
        changed = [replace(p, inputs=(InputDef("iron", D("2")),)) if p.key == "steel" else p for p in PRODUCTS]
        sync_catalog(changed)
        inputs = list(Product.objects.get(key="steel").recipe.inputs.all())
        self.assertEqual([(i.ingredient.key, i.quantity) for i in inputs], [("iron", D("2")), ])
        self.assertEqual(sync_catalog(changed).unchanged, 73)

    def test_a_recipe_removed_from_the_definitions_is_removed(self):
        self.assertTrue(Recipe.objects.filter(product__key="militia_medical_kit").exists())
        moved = [replace(p, inputs=None, sector=Sector.MILITARY_PROCUREMENT) if p.key == "militia_medical_kit" else p
                 for p in PRODUCTS]
        sync_catalog(moved)
        self.assertFalse(Recipe.objects.filter(product__key="militia_medical_kit").exists())
        self.assertFalse(RecipeInput.objects.filter(recipe__product__key="militia_medical_kit").exists())

    def test_a_product_that_leaves_the_definitions_is_never_deleted(self):
        sync_catalog([p for p in PRODUCTS if p.key != "resin"])
        self.assertTrue(Product.objects.filter(key="resin").exists())

    def test_specifying_a_value_later_flows_through_the_sync(self):
        steel = next(p for p in PRODUCTS if p.key == "steel")
        specified = [replace(p, yield_quantity=D("3"), inputs=tuple(InputDef(i.key, D("2")) for i in steel.inputs)) if p.key == "steel" else p
                     for p in PRODUCTS]
        sync_catalog(specified)
        recipe = Product.objects.get(key="steel").recipe
        self.assertEqual(recipe.yield_quantity, D("3"))
        self.assertEqual({i.quantity for i in recipe.inputs.all()}, {D("2")})


class DatabaseConstraintTests(TestCase):
    def setUp(self):
        sync_catalog()

    def test_zero_or_negative_quantities_are_rejected_by_the_database(self):
        ri = RecipeInput.objects.first()
        for bad in (D(0), D(-1)):
            with self.assertRaises(IntegrityError), transaction.atomic():
                RecipeInput.objects.filter(pk=ri.pk).update(quantity=bad)

    def test_zero_yield_is_rejected_but_unspecified_is_stored_as_null(self):
        recipe = Recipe.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Recipe.objects.filter(pk=recipe.pk).update(yield_quantity=D(0))
        self.assertIsNone(Recipe.objects.get(pk=recipe.pk).yield_quantity)

    def test_stars_outside_1_to_5_are_rejected(self):
        for bad in (0, 6):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Product.objects.filter(key="steel").update(min_stars=bad)

    def test_nutrition_zero_is_a_legal_specified_value_and_negative_is_not(self):
        f = FoodProfile.objects.first()
        FoodProfile.objects.filter(pk=f.pk).update(nutrition_amount=D(0))
        self.assertEqual(FoodProfile.objects.get(pk=f.pk).nutrition_amount, D(0))
        with self.assertRaises(IntegrityError), transaction.atomic():
            FoodProfile.objects.filter(pk=f.pk).update(nutrition_amount=D(-1))

    def test_one_resource_one_product_and_one_input_per_recipe(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.filter(key="gold").update(resource="iron")
        recipe = Product.objects.get(key="steel").recipe
        with self.assertRaises(IntegrityError), transaction.atomic():
            RecipeInput.objects.create(recipe=recipe, ingredient=Product.objects.get(key="iron"), position=9)

    def test_an_ingredient_cannot_be_deleted_while_a_recipe_uses_it(self):
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            Product.objects.get(key="iron").delete()
