from decimal import Decimal

from catalog import services
from catalog.constants import NutritionLevel, QolEffect, Sector, UseKind
from catalog.models import FoodProfile, Product, Recipe, RecipeInput
from geography.constants import Resource

from .base import CatalogTestCase

D = Decimal


class RecipeQueryTests(CatalogTestCase):
    def test_recipe_of_lists_inputs_in_document_order_with_unspecified_quantities(self):
        r = services.recipe_of("construction_materials")
        self.assertEqual([i.key for i in r.inputs], ["cement", "steel", "wood", "glass"])
        self.assertEqual([i.name for i in r.inputs][:2], ["Cimento", "Aço"])
        self.assertTrue(all(i.quantity is None for i in r.inputs))
        self.assertIsNone(r.yield_quantity)
        self.assertFalse(r.fully_specified)

    def test_raw_materials_and_procured_products_have_no_recipe(self):
        self.assertIsNone(services.recipe_of("iron"))
        self.assertIsNone(services.recipe_of("military_weapons"))
        self.assertIsNone(services.recipe_of("no_such_product"))

    def test_a_recipe_becomes_fully_specified_only_when_everything_is_given(self):
        recipe = Recipe.objects.get(product__key="steel")
        Recipe.objects.filter(pk=recipe.pk).update(yield_quantity=D("1"))
        RecipeInput.objects.filter(recipe=recipe, ingredient__key="iron").update(quantity=D("2"))
        self.assertFalse(services.recipe_of("steel").fully_specified)
        RecipeInput.objects.filter(recipe=recipe, ingredient__key="coal").update(quantity=D("1"))
        self.assertTrue(services.recipe_of("steel").fully_specified)

    def test_inputs_alone_are_not_enough_without_the_yield(self):
        RecipeInput.objects.filter(recipe__product__key="steel").update(quantity=D("1"))
        self.assertFalse(services.recipe_of("steel").fully_specified)

    def test_raw_materials_of_follows_the_chain_transitively(self):
        self.assertEqual(services.raw_materials_of("steel"), {"iron", "coal"})
        self.assertEqual(services.raw_materials_of("hamburger"), {"milk", "meat", "wheat"})
        self.assertEqual(services.raw_materials_of("iron"), {"iron"})
        self.assertEqual(services.raw_materials_of("cellphone"),
                         {"copper", "silica", "gold", "oil", "lithium", "chemicals"})

    def test_raw_materials_of_deep_chain_ppe(self):
        self.assertEqual(services.raw_materials_of("ppe"), {"rubber", "oil", "iron", "coal", "wool", "leather"})


class UsesAreDerivedTests(CatalogTestCase):
    def test_steel_is_an_input_of_the_recipes_that_list_it(self):
        self.assertEqual(services.consumers_of("steel"),
                         sorted(["construction_materials", "ppe", "furniture", "pen", "car", "computer", "improvised_weapons",
                                 "improvised_armor"]))
        self.assertTrue(all(u.kind == UseKind.RECIPE_INPUT for u in services.uses_of("steel")))

    def test_consumers_come_from_recipes_and_nothing_else(self):
        from_db = {ri.recipe.product.key for ri in RecipeInput.objects.filter(ingredient__key="sugar").select_related("recipe__product")}
        self.assertEqual(set(services.consumers_of("sugar")), from_db)
        self.assertEqual(set(services.consumers_of("sugar")), {"chocolate", "juice", "ice_cream", "soda"})

    def test_a_food_that_is_also_an_input_has_both_uses(self):
        kinds = [u.kind for u in services.uses_of("juice")]
        self.assertEqual(kinds, [UseKind.RECIPE_INPUT, UseKind.PLAYER_CONSUMPTION])

    def test_a_food_that_is_not_an_input_has_only_the_consumption_use(self):
        self.assertEqual([u.kind for u in services.uses_of("chocolate")], [UseKind.PLAYER_CONSUMPTION])

    def test_products_without_declared_use_have_NO_use_and_no_inferred_permission(self):
        for key in ("diamond", "silver", "latex", "resin", "natural_oil", "fertilizer", "fuel", "ppe", "car", "military_weapons"):
            self.assertEqual(services.uses_of(key), [], key)
            self.assertFalse(services.has_declared_use(key), key)
            self.assertEqual(services.consumers_of(key), [], key)

    def test_a_use_declared_later_in_the_catalog_appears_without_any_other_change(self):
        """Adicionar a receita que consome o Fertilizante (uma decisão futura do design) cria o uso derivado."""
        self.assertFalse(services.has_declared_use("fertilizer"))
        recipe = Recipe.objects.get(product__key="bread")
        RecipeInput.objects.create(recipe=recipe, ingredient=Product.objects.get(key="fertilizer"), position=9)
        self.assertEqual(services.consumers_of("fertilizer"), ["bread"])

    def test_the_use_carries_the_unspecified_quantity_as_none(self):
        use = services.uses_of("iron")[0]
        self.assertIsNone(use.quantity)


class GeographyLinkTests(CatalogTestCase):
    def test_every_geography_resource_maps_to_one_raw_material(self):
        for res in Resource:
            p = services.product_for_resource(res)
            self.assertEqual((p.key, p.resource), (res.value, res.value))
            self.assertEqual(services.product_for_resource(res.value).pk, p.pk)

    def test_oil_is_extractive_and_minerals_are_mining(self):
        self.assertEqual(services.product_for_resource(Resource.OIL).sector, Sector.EXTRACTIVE.value)
        self.assertEqual(services.product_for_resource(Resource.IRON).sector, Sector.MINING.value)

    def test_products_in_sector_match_the_matrix_of_the_design(self):
        self.assertEqual(len(services.products_in_sector(Sector.AGRO)), 10)
        self.assertEqual(len(services.products_in_sector(Sector.EXTRACTIVE)), 10)
        self.assertEqual(len(services.products_in_sector(Sector.MINING)), 9)

    def test_non_spatial_raw_materials_are_not_linked_to_a_resource(self):
        self.assertIsNone(services.product_for_resource("wheat"))
        self.assertIsNone(Product.objects.get(key="wheat").resource)


class ProductionReadinessTests(CatalogTestCase):
    def test_nothing_is_production_ready_while_the_design_values_are_unspecified(self):
        for p in Product.objects.exclude(sector=Sector.MILITARY_PROCUREMENT.value):
            r = services.check_production_ready(p.key)
            self.assertEqual((r.ok, r.code), (False, "UNSPECIFIED_DESIGN_VALUE"), p.key)

    def test_the_refusal_says_exactly_what_is_missing(self):
        r = services.check_production_ready("steel")
        self.assertEqual(r.detail["missing"], ["yield_quantity", "quantity:iron", "quantity:coal"])
        self.assertEqual(services.check_production_ready("iron").detail["missing"], ["min_stars"])

    def test_militia_products_do_not_ask_for_stars(self):
        self.assertNotIn("min_stars", services.check_production_ready("improvised_armor").detail["missing"])

    def test_army_products_are_not_producible_and_unknown_products_are_refused(self):
        self.assertEqual(services.check_production_ready("military_armor").code, "NOT_PRODUCIBLE")
        self.assertEqual(services.check_production_ready("ghost").code, "UNKNOWN_PRODUCT")

    def test_ready_once_every_value_is_specified(self):
        recipe = Recipe.objects.get(product__key="steel")
        Recipe.objects.filter(pk=recipe.pk).update(yield_quantity=D("1"))
        RecipeInput.objects.filter(recipe=recipe).update(quantity=D("1"))
        self.assertTrue(services.check_production_ready("steel").ok)
        self.assertFalse(services.check_production_ready("cement").ok)       # as demais continuam indefinidas

    def test_raw_material_becomes_ready_when_its_stars_are_specified(self):
        Product.objects.filter(key="iron").update(min_stars=1)
        self.assertTrue(services.check_production_ready("iron").ok)

    def test_unspecified_is_never_read_as_zero(self):
        r = services.recipe_of("steel")
        for v in [r.yield_quantity] + [i.quantity for i in r.inputs]:
            self.assertIsNone(v)
            self.assertNotEqual(v, D(0))


class ConsumptionReadinessTests(CatalogTestCase):
    def test_every_food_refuses_until_its_numbers_exist(self):
        for key in ("chocolate", "pasta", "hamburger", "juice", "ice_cream", "sun_dried_meat", "soda"):
            r = services.check_consumption_ready(key)
            self.assertEqual((r.ok, r.code, r.detail["missing"]), (False, "UNSPECIFIED_DESIGN_VALUE", ["nutrition_amount", "qol_intensity"]), key)

    def test_non_food_and_unknown(self):
        self.assertEqual(services.check_consumption_ready("steel").code, "NOT_FOOD")
        self.assertEqual(services.check_consumption_ready("bread").code, "NOT_FOOD")   # GAP_FOOD_PROFILE_BREAD_UNDECLARED
        self.assertEqual(services.check_consumption_ready("ghost").code, "UNKNOWN_PRODUCT")

    def test_zero_is_a_specified_value_and_is_not_confused_with_unspecified(self):
        FoodProfile.objects.filter(product__key="soda").update(nutrition_amount=D(0), qol_intensity=D(0))
        self.assertTrue(services.check_consumption_ready("soda").ok)
        self.assertEqual(services.food_of("soda").nutrition_amount, D(0))

    def test_partially_specified_lists_only_the_missing_one(self):
        FoodProfile.objects.filter(product__key="soda").update(nutrition_amount=D("5"))
        self.assertEqual(services.check_consumption_ready("soda").detail["missing"], ["qol_intensity"])

    def test_food_profiles_keep_the_qualitative_levels_of_the_design(self):
        f = services.food_of("sun_dried_meat")
        self.assertEqual((f.nutrition_level, f.qol_effect), (NutritionLevel.MEDIUM, QolEffect.DEBUFF))
        f = services.food_of("ice_cream")
        self.assertEqual((f.nutrition_level, f.qol_effect), (NutritionLevel.NONE, QolEffect.MEDIUM_BUFF))
