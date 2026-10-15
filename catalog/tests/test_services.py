from decimal import Decimal

from catalog import services
from catalog import provisional as prov
from catalog.constants import Category, Channel, NutritionLevel, QolEffect, Sector, UseKind
from catalog.models import FoodProfile, Product, Recipe, RecipeInput
from geography.constants import Resource

from .base import CatalogTestCase

D = Decimal


def unspecify(key):
    """Volta o produto ao estado 'não especificado' (NULL), para testar a recusa sem depender do que o design preencheu."""
    Product.objects.filter(key=key).update(min_stars=None, raw_yield=None, base_price=None)
    RecipeInput.objects.filter(recipe__product__key=key).update(quantity=None)
    Recipe.objects.filter(product__key=key).update(yield_quantity=None)
    FoodProfile.objects.filter(product__key=key).update(nutrition_amount=None, qol_intensity=None)


class RecipeQueryTests(CatalogTestCase):
    def test_recipe_of_lists_inputs_in_document_order_with_the_provisional_quantities(self):
        r = services.recipe_of("construction_materials")
        self.assertEqual([i.key for i in r.inputs], ["cement", "steel", "wood", "glass"])
        self.assertEqual([i.name for i in r.inputs][:2], ["Cimento", "Aço"])
        self.assertTrue(all(i.quantity == prov.RECIPE_INPUT_QUANTITY for i in r.inputs))
        self.assertEqual(r.yield_quantity, prov.RECIPE_YIELD)
        self.assertTrue(r.fully_specified)

    def test_raw_materials_and_unknown_products_have_no_recipe_but_the_army_products_do(self):
        self.assertIsNone(services.recipe_of("iron"))
        self.assertIsNone(services.recipe_of("no_such_product"))
        self.assertEqual([i.key for i in services.recipe_of("military_weapons").inputs], ["steel", "wood", "plastic"])
        self.assertEqual([i.key for i in services.recipe_of("military_medical_kits").inputs], ["wool", "hospital_supplies"])

    def test_a_recipe_becomes_fully_specified_only_when_everything_is_given(self):
        unspecify("steel")
        recipe = Recipe.objects.get(product__key="steel")
        self.assertFalse(services.recipe_of("steel").fully_specified)
        Recipe.objects.filter(pk=recipe.pk).update(yield_quantity=D("1"))
        RecipeInput.objects.filter(recipe=recipe, ingredient__key="iron").update(quantity=D("2"))
        self.assertFalse(services.recipe_of("steel").fully_specified)
        RecipeInput.objects.filter(recipe=recipe, ingredient__key="coal").update(quantity=D("1"))
        self.assertTrue(services.recipe_of("steel").fully_specified)

    def test_inputs_alone_are_not_enough_without_the_yield(self):
        unspecify("steel")
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
                                 "improvised_armor", "military_weapons", "military_armor"]))
        self.assertEqual({u.kind for u in services.uses_of("steel")}, {UseKind.RECIPE_INPUT, UseKind.COMMERCIAL_CHANNEL})

    def test_consumers_come_from_recipes_and_nothing_else(self):
        from_db = {ri.recipe.product.key for ri in RecipeInput.objects.filter(ingredient__key="sugar").select_related("recipe__product")}
        self.assertEqual(set(services.consumers_of("sugar")), from_db)
        self.assertEqual(set(services.consumers_of("sugar")), {"chocolate", "juice", "ice_cream", "soda"})

    def test_a_food_that_is_also_an_input_has_both_uses(self):
        kinds = [u.kind for u in services.uses_of("juice")]
        self.assertEqual(kinds[:2], [UseKind.RECIPE_INPUT, UseKind.PLAYER_CONSUMPTION])
        self.assertEqual({u.channel for u in services.uses_of("juice") if u.kind == UseKind.COMMERCIAL_CHANNEL},
                         {Channel.INTER_COMPANY, Channel.RETAIL_SALE})

    def test_a_food_that_is_not_an_input_has_only_the_consumption_use(self):
        kinds = [u.kind for u in services.uses_of("chocolate")]
        self.assertEqual(kinds[0], UseKind.PLAYER_CONSUMPTION)
        self.assertNotIn(UseKind.RECIPE_INPUT, kinds)

    def test_a_product_without_any_declared_use_has_NO_use_and_no_inferred_permission(self):
        """Nada é inferido: sem receita que o consuma, sem perfil de alimento e sem canal declarado, não há uso."""
        Product.objects.filter(key="diamond").update(commercial_channels=[])
        self.assertEqual(services.uses_of("diamond"), [])
        self.assertFalse(services.has_declared_use("diamond"))
        self.assertEqual(services.consumers_of("diamond"), [])
        self.assertEqual(services.channels_of("diamond"), ())

    def test_every_catalog_product_declares_at_least_one_use_after_the_approved_classification(self):
        for p in Product.objects.all():
            self.assertTrue(services.has_declared_use(p.key), p.key)

    def test_military_products_have_the_military_action_use_and_only_their_declared_channels(self):
        self.assertIn(UseKind.MILITARY_ACTION, [u.kind for u in services.uses_of("military_weapons")])
        self.assertEqual(services.channels_of("military_weapons"), (Channel.ARMY_PROCUREMENT,))
        self.assertEqual(services.channels_of("improvised_weapons"), ())      # a milícia produz; ninguém a revende

    def test_army_exclusive_products_are_not_sold_by_varejo_and_not_traded_between_companies(self):
        for key in ("military_weapons", "military_armor", "military_medical_kits"):
            self.assertFalse(services.has_channel(key, Channel.RETAIL_SALE), key)
            self.assertFalse(services.has_channel(key, Channel.INTER_COMPANY), key)
            self.assertTrue(services.has_channel(key, Channel.ARMY_PROCUREMENT), key)

    def test_the_militia_requisition_channel_covers_exactly_the_direct_inputs_of_the_improvised_recipes(self):
        direct = set()
        for key in ("improvised_weapons", "improvised_armor", "militia_medical_kit"):
            direct |= {i.key for i in services.recipe_of(key).inputs}
        self.assertEqual({p.key for p in Product.objects.all() if services.has_channel(p.key, Channel.SPECIAL_REQUISITION)}, direct)

    def test_categories_and_base_prices_are_queryable(self):
        self.assertEqual(services.category_of("iron"), Category.MATERIAL)
        self.assertEqual(services.category_of("bread"), Category.FOOD)
        self.assertEqual(services.category_of("car"), Category.DURABLE)
        self.assertEqual(services.category_of("ppe"), Category.EQUIPMENT)
        self.assertEqual(services.category_of("military_armor"), Category.MILITARY)
        self.assertIsNone(services.category_of("ghost"))
        self.assertEqual(services.base_price_of("iron"), prov.RAW_BASE_PRICE)
        self.assertEqual(services.base_price_of("steel"), D("30.00"))      # 10 + 10 + 5 × 2★
        self.assertIsNone(services.base_price_of("ghost"))

    def test_a_use_declared_later_in_the_catalog_appears_without_any_other_change(self):
        """Adicionar a receita que consome o Fertilizante (uma decisão futura do design) cria o uso derivado."""
        Product.objects.filter(key="fertilizer").update(commercial_channels=[])
        self.assertFalse(services.has_declared_use("fertilizer"))
        recipe = Recipe.objects.get(product__key="bread")
        RecipeInput.objects.create(recipe=recipe, ingredient=Product.objects.get(key="fertilizer"), position=9)
        self.assertEqual(services.consumers_of("fertilizer"), ["bread"])

    def test_the_use_carries_the_quantity_and_an_unspecified_one_stays_none(self):
        use = services.uses_of("iron")[0]
        self.assertEqual((use.kind, use.quantity), (UseKind.RECIPE_INPUT, prov.RECIPE_INPUT_QUANTITY))
        RecipeInput.objects.filter(ingredient__key="iron").update(quantity=None)
        self.assertIsNone(services.uses_of("iron")[0].quantity)


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
    def test_every_catalog_product_is_production_ready_with_the_provisional_values(self):
        for p in Product.objects.all():
            r = services.check_production_ready(p.key)
            self.assertEqual((r.ok, r.code), (True, "OK"), p.key)

    def test_the_refusal_still_exists_and_says_exactly_what_is_missing(self):
        unspecify("steel")
        unspecify("iron")
        r = services.check_production_ready("steel")
        self.assertEqual((r.ok, r.code), (False, "UNSPECIFIED_DESIGN_VALUE"))
        self.assertEqual(r.detail["missing"], ["min_stars", "yield_quantity", "quantity:iron", "quantity:coal"])
        self.assertEqual(services.check_production_ready("iron").detail["missing"], ["min_stars", "raw_yield"])

    def test_militia_products_do_not_ask_for_stars_but_army_products_do(self):
        unspecify("improvised_armor")
        self.assertNotIn("min_stars", services.check_production_ready("improvised_armor").detail["missing"])
        unspecify("military_armor")
        self.assertIn("min_stars", services.check_production_ready("military_armor").detail["missing"])

    def test_army_products_are_producible_and_unknown_products_are_refused(self):
        self.assertTrue(services.check_production_ready("military_armor").ok)
        self.assertEqual(services.check_production_ready("ghost").code, "UNKNOWN_PRODUCT")

    def test_ready_again_once_every_value_is_specified(self):
        unspecify("steel")
        Product.objects.filter(key="steel").update(min_stars=2)
        recipe = Recipe.objects.get(product__key="steel")
        Recipe.objects.filter(pk=recipe.pk).update(yield_quantity=D("1"))
        RecipeInput.objects.filter(recipe=recipe).update(quantity=D("1"))
        self.assertTrue(services.check_production_ready("steel").ok)

    def test_raw_material_becomes_ready_when_its_stars_and_yield_are_specified(self):
        unspecify("iron")
        Product.objects.filter(key="iron").update(min_stars=None)
        self.assertFalse(services.check_production_ready("iron").ok)
        Product.objects.filter(key="iron").update(min_stars=1, raw_yield=D(1))
        self.assertTrue(services.check_production_ready("iron").ok)

    def test_unspecified_is_never_read_as_zero(self):
        unspecify("steel")
        r = services.recipe_of("steel")
        for v in [r.yield_quantity] + [i.quantity for i in r.inputs]:
            self.assertIsNone(v)
            self.assertNotEqual(v, D(0))


class ConsumptionReadinessTests(CatalogTestCase):
    FOODS = ("chocolate", "pasta", "hamburger", "juice", "ice_cream", "sun_dried_meat", "soda", "bread")

    def test_every_food_has_the_provisional_numbers_for_its_qualitative_level(self):
        for key in self.FOODS:
            self.assertTrue(services.check_consumption_ready(key).ok, key)
            f = services.food_of(key)
            self.assertEqual((f.nutrition_amount, f.qol_intensity),
                             (prov.nutrition_amount(f.nutrition_level), prov.qol_intensity(f.qol_effect)), key)

    def test_a_food_refuses_if_its_numbers_become_unspecified_again(self):
        for key in self.FOODS:
            unspecify(key)
            r = services.check_consumption_ready(key)
            self.assertEqual((r.ok, r.code, r.detail["missing"]), (False, "UNSPECIFIED_DESIGN_VALUE", ["nutrition_amount", "qol_intensity"]), key)

    def test_non_food_and_unknown(self):
        self.assertEqual(services.check_consumption_ready("steel").code, "NOT_FOOD")
        self.assertEqual(services.check_consumption_ready("ghost").code, "UNKNOWN_PRODUCT")

    def test_bread_is_a_consumable_food_with_the_provisional_profile(self):
        f = services.food_of("bread")
        self.assertEqual((f.nutrition_level, f.qol_effect), (prov.BREAD_NUTRITION_LEVEL, prov.BREAD_QOL_EFFECT))
        self.assertTrue(services.check_consumption_ready("bread").ok)
        self.assertTrue(Product.objects.get(key="bread").is_consumable)

    def test_zero_is_a_specified_value_and_is_not_confused_with_unspecified(self):
        FoodProfile.objects.filter(product__key="soda").update(nutrition_amount=D(0), qol_intensity=D(0))
        self.assertTrue(services.check_consumption_ready("soda").ok)
        self.assertEqual(services.food_of("soda").nutrition_amount, D(0))

    def test_partially_specified_lists_only_the_missing_one(self):
        FoodProfile.objects.filter(product__key="soda").update(nutrition_amount=D("5"), qol_intensity=None)
        self.assertEqual(services.check_consumption_ready("soda").detail["missing"], ["qol_intensity"])

    def test_food_profiles_keep_the_qualitative_levels_of_the_design(self):
        f = services.food_of("sun_dried_meat")
        self.assertEqual((f.nutrition_level, f.qol_effect), (NutritionLevel.MEDIUM, QolEffect.DEBUFF))
        f = services.food_of("ice_cream")
        self.assertEqual((f.nutrition_level, f.qol_effect), (NutritionLevel.NONE, QolEffect.MEDIUM_BUFF))
