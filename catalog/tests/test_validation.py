"""Cada código de ERRO e de PENDÊNCIA, com definições sintéticas; e a distinção entre os dois."""
from dataclasses import replace
from decimal import Decimal

from django.test import SimpleTestCase

from catalog.constants import Category, Channel, NutritionLevel, QolEffect, Sector
from catalog.definitions import KNOWN_GAPS, PRODUCTS, FoodDef, InputDef, ProductDef
from catalog.validation import find_cycles, validate

D = Decimal
BY_KEY = {p.key: p for p in PRODUCTS}


def mod(key, **changes):
    """Catálogo real com um produto alterado (os demais ficam intactos)."""
    return [replace(p, **changes) if p.key == key else p for p in PRODUCTS]


def add(*extra):
    return list(PRODUCTS) + list(extra)


def made(key, inputs, sector=Sector.INDUSTRIAL_PRODUCTION, **kw):
    kw.setdefault("category", Category.MATERIAL)
    kw.setdefault("channels", (Channel.INTER_COMPANY,))
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

    def test_raw_with_recipe(self):
        self.assertIn("RAW_WITH_RECIPE", validate(mod("iron", inputs=(InputDef("coal"),))).codes)

    def test_produced_without_recipe_including_the_army_products(self):
        self.assertIn("PRODUCED_WITHOUT_RECIPE", validate(mod("steel", inputs=None)).codes)
        self.assertIn("PRODUCED_WITHOUT_RECIPE", validate(mod("steel", inputs=())).codes)
        self.assertIn("PRODUCED_WITHOUT_RECIPE", validate(mod("military_armor", inputs=None)).codes)

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

    def test_stars_are_not_applicable_to_militia_but_apply_to_the_army_products(self):
        self.assertIn("STARS_NOT_APPLICABLE", validate(mod("improvised_armor", min_stars=2)).codes)
        self.assertTrue(validate(mod("military_armor", min_stars=3)).ok)
        self.assertIn("INVALID_STARS", validate(mod("military_armor", min_stars=6)).codes)

    def test_invalid_raw_yield_and_base_price(self):
        for bad in (D(0), D(-1), 1.0):
            self.assertIn("INVALID_RAW_YIELD", validate(mod("iron", raw_yield=bad)).codes, repr(bad))
        self.assertIn("INVALID_RAW_YIELD", validate(mod("steel", raw_yield=D(1))).codes)      # só matéria-prima tem
        for bad in (D(-1), 2.5):
            self.assertIn("INVALID_BASE_PRICE", validate(mod("steel", base_price=bad)).codes, repr(bad))
        self.assertTrue(validate(mod("steel", base_price=D(0))).ok)        # zero é valor especificado


class ClassificationErrorsTests(SimpleTestCase):
    """Q6/Q8: uma categoria, tags coerentes, canais declarados coerentes com a estrutura."""

    def codes(self, key, **changes):
        return validate(mod(key, **changes)).codes

    def test_category_missing_and_invalid(self):
        self.assertIn("CATEGORY_MISSING", self.codes("steel", category=None))
        self.assertIn("CATEGORY_INVALID", self.codes("steel", category="material"))

    def test_the_military_category_follows_the_military_sectors(self):
        self.assertIn("CATEGORY_SECTOR_MISMATCH", self.codes("steel", category=Category.MILITARY, is_military=True))
        self.assertIn("CATEGORY_SECTOR_MISMATCH", self.codes("military_armor", category=Category.EQUIPMENT, is_military=False))
        self.assertIn("MILITARY_TAG_MISMATCH", self.codes("military_armor", is_military=False))

    def test_a_food_must_be_classified_as_a_consumable_food_and_vice_versa(self):
        self.assertIn("FOOD_NOT_CLASSIFIED_AS_FOOD", self.codes("soda", category=Category.MATERIAL))
        self.assertIn("FOOD_NOT_CLASSIFIED_AS_FOOD", self.codes("soda", is_consumable=False))
        self.assertIn("FOOD_WITHOUT_PROFILE", self.codes("steel", category=Category.FOOD))

    def test_consumable_and_permanent_are_exclusive(self):
        self.assertIn("CONSUMABLE_AND_PERMANENT", self.codes("car", is_consumable=True))

    def test_channels_must_be_unique_declared_values(self):
        self.assertIn("CHANNEL_INVALID", self.codes("steel", channels=(Channel.INTER_COMPANY, Channel.INTER_COMPANY)))
        self.assertIn("CHANNEL_INVALID", self.codes("steel", channels=("inter_company",)))

    def test_varejo_sells_final_goods_only(self):
        self.assertIn("RETAIL_CHANNEL_NOT_FINAL_GOOD", self.codes("steel", channels=(Channel.INTER_COMPANY, Channel.RETAIL_SALE)))
        self.assertTrue(validate(mod("car", channels=(Channel.INTER_COMPANY, Channel.RETAIL_SALE))).ok)

    def test_military_products_are_not_traded_between_companies_or_sold_by_varejo(self):
        self.assertIn("MILITARY_IN_INTER_COMPANY_TRADE",
                      self.codes("military_armor", channels=(Channel.ARMY_PROCUREMENT, Channel.INTER_COMPANY)))
        self.assertIn("ARMY_PRODUCT_IN_RETAIL",
                      self.codes("military_armor", channels=(Channel.ARMY_PROCUREMENT, Channel.RETAIL_SALE)))
        self.assertIn("RETAIL_CHANNEL_NOT_FINAL_GOOD",
                      self.codes("military_armor", channels=(Channel.ARMY_PROCUREMENT, Channel.RETAIL_SALE)))

    def test_the_army_channel_belongs_to_the_army_products_only(self):
        self.assertIn("ARMY_CHANNEL_NOT_ARMY_PRODUCT", self.codes("steel", channels=(Channel.INTER_COMPANY, Channel.ARMY_PROCUREMENT)))
        self.assertIn("ARMY_CHANNEL_NOT_ARMY_PRODUCT", self.codes("improvised_armor", channels=(Channel.ARMY_PROCUREMENT,)))

    def test_special_requisition_only_covers_inputs_of_the_militia_recipes(self):
        self.assertIn("REQUISITION_NOT_A_MILITIA_INPUT", self.codes("cement", channels=(Channel.INTER_COMPANY, Channel.SPECIAL_REQUISITION)))
        self.assertTrue(validate(mod("steel", channels=(Channel.INTER_COMPANY, Channel.SPECIAL_REQUISITION))).ok)

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
    def test_the_real_catalog_has_only_the_known_gaps_as_pending(self):
        """Com os valores [PROV] e a classificação aprovados, não resta pendência por produto: só as lacunas conhecidas."""
        r = validate(PRODUCTS)
        self.assertTrue(r.ok)
        self.assertEqual(r.pending_codes, sorted(g.code for g in KNOWN_GAPS))
        self.assertEqual(len(r.pending), len(KNOWN_GAPS))

    def test_every_product_has_a_declared_use_in_the_real_catalog(self):
        r = validate(PRODUCTS)
        self.assertEqual(r.subjects("RAW_MATERIAL_WITHOUT_USE"), [])
        self.assertEqual(r.subjects("PRODUCT_WITHOUT_DECLARED_USE"), [])

    def test_a_product_with_no_recipe_consumer_food_profile_or_channel_has_no_use(self):
        r = validate(mod("diamond", channels=()))
        self.assertEqual(r.subjects("RAW_MATERIAL_WITHOUT_USE"), ["diamond"])
        r = validate(mod("fertilizer", channels=()))
        self.assertEqual(r.subjects("PRODUCT_WITHOUT_DECLARED_USE"), ["fertilizer"])

    def test_design_pending_never_makes_the_catalog_fail(self):
        broken = [replace(p, base_price=None, min_stars=None if p.inputs is None else p.min_stars,
                          raw_yield=None, yield_quantity=None,
                          inputs=None if p.inputs is None else tuple(InputDef(i.key) for i in p.inputs),
                          food=None if p.food is None else FoodDef(p.food.nutrition_level, p.food.qol_effect))
                  for p in PRODUCTS]
        r = validate(broken)
        self.assertTrue(r.ok)
        self.assertEqual(len(r.subjects("RECIPE_QUANTITIES_UNSPECIFIED")), 44)
        self.assertEqual(len(r.subjects("RECIPE_YIELD_UNSPECIFIED")), 44)
        self.assertEqual(len(r.subjects("MIN_STARS_UNSPECIFIED")), 29)
        self.assertEqual(len(r.subjects("RAW_YIELD_UNSPECIFIED")), 29)
        self.assertEqual(len(r.subjects("BASE_PRICE_UNSPECIFIED")), 73)
        self.assertEqual(len(r.subjects("FOOD_NUTRITION_UNSPECIFIED")), 8)
        self.assertEqual(len(r.subjects("FOOD_QOL_INTENSITY_UNSPECIFIED")), 8)

    def test_specifying_a_value_removes_only_its_own_pending(self):
        steel = BY_KEY["steel"]
        unspecified = [replace(p, yield_quantity=None, inputs=tuple(InputDef(i.key) for i in p.inputs)) if p.inputs else p
                       for p in PRODUCTS]
        full = [replace(p, yield_quantity=D("1"), inputs=tuple(InputDef(i.key, D("1")) for i in steel.inputs))
                if p.key == "steel" else p for p in unspecified]
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
        self.assertNotIn("iron", validate(mod("iron", base_price=D(0))).subjects("BASE_PRICE_UNSPECIFIED"))

    def test_a_pending_does_not_grant_a_use(self):
        """Declarar a pendência não cria uso: o produto sem canal continua sem uso declarado."""
        r = validate(mod("fertilizer", channels=(), base_price=None))
        self.assertIn("fertilizer", r.subjects("PRODUCT_WITHOUT_DECLARED_USE"))
        self.assertIn("fertilizer", r.subjects("BASE_PRICE_UNSPECIFIED"))
