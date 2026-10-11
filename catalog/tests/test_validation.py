"""Cada código de ERRO e de PENDÊNCIA, com definições sintéticas; e a distinção entre os dois."""
from dataclasses import replace
from decimal import Decimal

from django.test import SimpleTestCase

from catalog.constants import NutritionLevel, QolEffect, Sector
from catalog.definitions import PRODUCTS, FoodDef, InputDef, ProductDef
from catalog.validation import find_cycles, validate

D = Decimal
BY_KEY = {p.key: p for p in PRODUCTS}


def mod(key, **changes):
    """Catálogo real com um produto alterado (os demais ficam intactos)."""
    return [replace(p, **changes) if p.key == key else p for p in PRODUCTS]


def add(*extra):
    return list(PRODUCTS) + list(extra)


def made(key, inputs, sector=Sector.INDUSTRIAL_PRODUCTION, **kw):
    return ProductDef(key=key, name=key, sector=sector, min_stars=kw.pop("min_stars", 1),
                      inputs=tuple(InputDef(i) for i in inputs), **kw)


class ErrorCodesTests(SimpleTestCase):
    def test_the_real_catalog_has_no_error(self):
        self.assertTrue(validate(PRODUCTS).ok)

    def test_duplicate_key(self):
        self.assertIn("DUPLICATE_KEY", validate(add(BY_KEY["iron"])).codes)

    def test_duplicate_resource_link(self):
        r = validate(add(ProductDef("iron2", "Ferro 2", Sector.MINING, resource="iron")))
        self.assertIn("DUPLICATE_RESOURCE_LINK", r.codes)

    def test_ingredient_not_found(self):
        r = validate(mod("steel", inputs=(InputDef("iron"), InputDef("unobtainium"))))
        self.assertEqual(r.subjects("INGREDIENT_NOT_FOUND"), ["steel"])

    def test_duplicate_input(self):
        self.assertIn("DUPLICATE_INPUT", validate(mod("steel", inputs=(InputDef("iron"), InputDef("iron")))).codes)

    def test_raw_with_recipe_and_procured_with_recipe(self):
        self.assertIn("RAW_WITH_RECIPE", validate(mod("iron", inputs=(InputDef("coal"),))).codes)
        self.assertIn("PROCURED_WITH_RECIPE", validate(mod("military_armor", inputs=(InputDef("steel"),))).codes)

    def test_produced_without_recipe(self):
        self.assertIn("PRODUCED_WITHOUT_RECIPE", validate(mod("steel", inputs=None)).codes)
        self.assertIn("PRODUCED_WITHOUT_RECIPE", validate(mod("steel", inputs=())).codes)

    def test_invalid_quantity_rejects_zero_negative_and_float_but_accepts_unspecified(self):
        for bad in (D(0), D(-1), 1.5, 1):
            r = validate(mod("steel", inputs=(InputDef("iron", bad), InputDef("coal"))))
            self.assertIn("INVALID_QUANTITY", r.codes, repr(bad))
        r = validate(mod("steel", inputs=(InputDef("iron", D("2")), InputDef("coal", None))))
        self.assertTrue(r.ok)

    def test_invalid_yield(self):
        for bad in (D(0), D(-2), 3.0):
            self.assertIn("INVALID_YIELD", validate(mod("steel", yield_quantity=bad)).codes, repr(bad))
        self.assertTrue(validate(mod("steel", yield_quantity=D("1"))).ok)

    def test_invalid_stars(self):
        for bad in (0, 6, -1, 2.5):
            self.assertIn("INVALID_STARS", validate(mod("steel", min_stars=bad)).codes, repr(bad))
        for good in (1, 3, 5):
            self.assertTrue(validate(mod("steel", min_stars=good)).ok)

    def test_stars_are_not_applicable_to_militia_or_procurement(self):
        self.assertIn("STARS_NOT_APPLICABLE", validate(mod("improvised_armor", min_stars=2)).codes)
        self.assertIn("STARS_NOT_APPLICABLE", validate(mod("military_armor", min_stars=2)).codes)

    def test_food_values_zero_is_specified_but_negative_is_invalid(self):
        food = FoodDef(NutritionLevel.NONE, QolEffect.NO_EFFECT, D(0), D(0))
        self.assertTrue(validate(mod("soda", food=food)).ok)
        bad = FoodDef(NutritionLevel.NONE, QolEffect.NO_EFFECT, D(-1), None)
        self.assertIn("INVALID_FOOD_VALUE", validate(mod("soda", food=bad)).codes)
        bad = FoodDef(NutritionLevel.NONE, QolEffect.NO_EFFECT, None, 2.0)
        self.assertIn("INVALID_FOOD_VALUE", validate(mod("soda", food=bad)).codes)

    def test_geography_link_errors(self):
        self.assertIn("RESOURCE_ON_NON_RAW", validate(mod("steel", resource="gold")).codes)
        self.assertIn("RESOURCE_UNKNOWN", validate(mod("wheat", resource="mithril")).codes)
        self.assertIn("RESOURCE_SECTOR_MISMATCH", validate(mod("oil", sector=Sector.MINING)).codes)
        self.assertIn("RESOURCE_SECTOR_MISMATCH", validate(mod("iron", sector=Sector.EXTRACTIVE)).codes)

    def test_resource_without_product(self):
        r = validate([p for p in PRODUCTS if p.key != "lithium"])
        self.assertIn("RESOURCE_WITHOUT_PRODUCT", r.codes)
        self.assertEqual(r.subjects("RESOURCE_WITHOUT_PRODUCT"), ["lithium"])


class CycleTests(SimpleTestCase):
    def test_the_real_catalog_has_no_cycle(self):
        self.assertEqual(find_cycles(PRODUCTS), [])

    def test_self_reference(self):
        self.assertEqual(len(find_cycles(add(made("loop", ["loop"])))), 1)

    def test_two_and_three_cycles(self):
        self.assertEqual(len(find_cycles(add(made("a", ["b"]), made("b", ["a"])))), 1)
        r = validate(add(made("a", ["b"]), made("b", ["c"]), made("c", ["a"])))
        self.assertIn("RECIPE_CYCLE", r.codes)

    def test_a_cycle_through_the_real_graph(self):
        """Aço <- Ferro e Carvão; fazer o Carvão depender do Aço fecha um ciclo no grafo REAL."""
        r = validate(mod("coal", sector=Sector.INDUSTRIAL_PRODUCTION, inputs=(InputDef("steel"),), resource=None))
        self.assertIn("RECIPE_CYCLE", r.codes)

    def test_a_diamond_shaped_dependency_is_not_a_cycle(self):
        diamond = add(made("top", ["left", "right"]), made("left", ["base"]), made("right", ["base"]), made("base", ["iron"]))
        self.assertEqual(find_cycles(diamond), [])
        self.assertTrue(validate(diamond).ok)

    def test_a_broken_reference_is_reported_once_and_does_not_crash_the_cycle_search(self):
        r = validate(add(made("x", ["nope"])))
        self.assertEqual(r.subjects("INGREDIENT_NOT_FOUND"), ["x"])
        self.assertNotIn("RECIPE_CYCLE", r.codes)


class PendingVsErrorTests(SimpleTestCase):
    def test_design_pending_never_makes_the_catalog_fail(self):
        r = validate(PRODUCTS)
        self.assertTrue(r.ok)
        self.assertGreater(len(r.pending), 100)

    def test_the_five_raw_materials_without_declared_use(self):
        self.assertEqual(validate(PRODUCTS).subjects("RAW_MATERIAL_WITHOUT_USE"),
                         ["diamond", "latex", "natural_oil", "resin", "silver"])

    def test_products_without_declared_use(self):
        subjects = validate(PRODUCTS).subjects("PRODUCT_WITHOUT_DECLARED_USE")
        for key in ("fertilizer", "fuel", "ppe", "school_supplies", "uniform", "car", "cellphone", "computer",
                    "ground_coffee", "butter", "construction_materials", "military_weapons"):
            self.assertIn(key, subjects)
        for key in ("steel", "bread", "juice", "chocolate"):   # insumo de receita ou alimento: TEM uso declarado
            self.assertNotIn(key, subjects)

    def test_a_food_has_a_declared_use_even_without_being_an_input(self):
        self.assertNotIn("chocolate", validate(PRODUCTS).subjects("PRODUCT_WITHOUT_DECLARED_USE"))

    def test_unspecified_values_are_pending_per_product(self):
        r = validate(PRODUCTS)
        self.assertEqual(len(r.subjects("RECIPE_QUANTITIES_UNSPECIFIED")), 41)
        self.assertEqual(len(r.subjects("RECIPE_YIELD_UNSPECIFIED")), 41)
        self.assertEqual(len(r.subjects("MIN_STARS_UNSPECIFIED")), 29)
        self.assertEqual(len(r.subjects("FOOD_NUTRITION_UNSPECIFIED")), 7)
        self.assertEqual(len(r.subjects("FOOD_QOL_INTENSITY_UNSPECIFIED")), 7)

    def test_specifying_a_value_removes_only_its_own_pending(self):
        steel = BY_KEY["steel"]
        full = mod("steel", inputs=tuple(InputDef(i.key, D("1")) for i in steel.inputs), yield_quantity=D("1"))
        r = validate(full)
        self.assertNotIn("steel", r.subjects("RECIPE_QUANTITIES_UNSPECIFIED"))
        self.assertNotIn("steel", r.subjects("RECIPE_YIELD_UNSPECIFIED"))
        self.assertIn("cement", r.subjects("RECIPE_QUANTITIES_UNSPECIFIED"))

    def test_a_partially_specified_recipe_is_still_pending(self):
        r = validate(mod("steel", inputs=(InputDef("iron", D("2")), InputDef("coal"))))
        self.assertIn("steel", r.subjects("RECIPE_QUANTITIES_UNSPECIFIED"))

    def test_zero_is_not_treated_as_unspecified(self):
        food = FoodDef(NutritionLevel.NONE, QolEffect.NO_EFFECT, D(0), D(0))
        r = validate(mod("soda", food=food))
        self.assertNotIn("soda", r.subjects("FOOD_NUTRITION_UNSPECIFIED"))
        self.assertNotIn("soda", r.subjects("FOOD_QOL_INTENSITY_UNSPECIFIED"))

    def test_a_pending_does_not_grant_a_use(self):
        """Declarar a pendência não cria uso: o produto continua sem consumidor."""
        r = validate(PRODUCTS)
        self.assertIn("fertilizer", r.subjects("PRODUCT_WITHOUT_DECLARED_USE"))
