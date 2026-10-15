"""As definições transcritas do 22: estrutura válida, fiéis ao arquivo de design e sem número inventado."""
import re
from pathlib import Path

from django.test import SimpleTestCase

from catalog import audit, provisional as prov
from catalog.constants import Category, Channel, NutritionLevel, QolEffect, Sector
from catalog.definitions import KNOWN_GAPS, PRODUCTS
from catalog.validation import validate
from geography.constants import Resource

DOC = Path(__file__).resolve().parents[2] / "design" / "22-Receitas-Produção.md"
BY_KEY = {p.key: p for p in PRODUCTS}

NUTRITION = {"nada": NutritionLevel.NONE, "quase nada": NutritionLevel.ALMOST_NONE, "pouca": NutritionLevel.LOW,
             "média": NutritionLevel.MEDIUM, "bastante": NutritionLevel.HIGH}
QOL = {"sem efeito": QolEffect.NO_EFFECT, "pequeno buff": QolEffect.SMALL_BUFF, "buff médio": QolEffect.MEDIUM_BUFF,
       "debuff": QolEffect.DEBUFF}


def parse_doc():
    """Lê o 22 como está: matriz por terreno e tabelas de receitas por sub-tipo (inclui o Exército)."""
    text = DOC.read_text(encoding="utf-8").replace("\r", "")
    matrix, rows, section = {}, [], None
    for line in text.splitlines():
        m = re.match(r"\|\s*(Agropecuária|Extrativismo|Mineração)\s*\|\s*(.*?)\s*\|$", line)
        if m:
            matrix[m.group(1)] = [x.strip() for x in m.group(2).split(",")]
            continue
        if line.startswith("#"):
            section = None
            continue
        if line.startswith("**"):
            section = line.strip("*: ").strip()
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 3 and "---" not in line and cells[0] not in ("Produto final", "Terreno"):
            rows.append((section, cells))
    return matrix, rows


class DefinitionsAreValidTests(SimpleTestCase):
    def test_no_integrity_error_and_expected_size(self):
        r = validate(PRODUCTS)
        self.assertEqual(r.errors, [])
        self.assertEqual((r.stats["products"], r.stats["raw"], r.stats["recipes"], r.stats["foods"]), (73, 29, 44, 8))

    def test_keys_are_unique_slugs_independent_of_the_display_name(self):
        keys = [p.key for p in PRODUCTS]
        self.assertEqual(len(keys), len(set(keys)))
        for p in PRODUCTS:
            self.assertRegex(p.key, r"^[a-z][a-z0-9_]*$")
        for p in PRODUCTS:
            if p.key != re.sub(r"[^a-z0-9]+", "_", p.name.lower()):
                break
        else:
            self.fail("as chaves não deveriam ser só o nome em minúsculas")

    def test_every_geography_resource_is_a_raw_material_with_the_resource_value_as_key(self):
        for res in Resource:
            p = BY_KEY[res.value]
            self.assertEqual((p.resource, p.inputs), (res.value, None))

    def test_oil_is_extractive_and_the_nine_minerals_are_mining(self):
        self.assertEqual(BY_KEY["oil"].sector, Sector.EXTRACTIVE)
        self.assertEqual({k for k, p in BY_KEY.items() if p.sector == Sector.MINING},
                         {r.value for r in Resource if r is not Resource.OIL})

    def test_every_number_comes_from_the_provisional_table(self):
        """GD (2026-10-14, Q3): os números que o 22 não dá vêm SÓ de `provisional.py`. Nenhum produto carrega número próprio."""
        recipes = {p.key: (tuple((i.key, prov.RECIPE_INPUT_QUANTITY) for i in p.inputs), prov.RECIPE_YIELD, p.min_stars)
                   for p in PRODUCTS if p.inputs is not None}
        prices = prov.compute_base_prices(recipes, [p.key for p in PRODUCTS if p.inputs is None])
        for p in PRODUCTS:
            self.assertEqual(p.base_price, prices[p.key], p.key)
            if p.inputs is None:
                self.assertEqual((p.min_stars, p.raw_yield, p.yield_quantity), (prov.MATRIZ_MIN_STARS, prov.MATRIZ_YIELD, None), p.key)
            else:
                self.assertEqual((p.yield_quantity, p.raw_yield), (prov.RECIPE_YIELD, None), p.key)
                self.assertEqual({i.quantity for i in p.inputs}, {prov.RECIPE_INPUT_QUANTITY}, p.key)
            if p.food:
                self.assertEqual((p.food.nutrition_amount, p.food.qol_intensity),
                                 (prov.nutrition_amount(p.food.nutrition_level), prov.qol_intensity(p.food.qol_effect)), p.key)

    def test_the_provisional_table_lists_every_provisional_number_with_its_source(self):
        rows = audit.provisional_table()
        self.assertTrue(all(r.status == "PROV" and r.source.startswith("GD 2026-10-14") for r in rows))
        per_product = {(r.scope, r.parameter) for r in rows}
        for p in PRODUCTS:
            self.assertIn((p.key, "base_price"), per_product)
            self.assertIn((p.key, "matriz" if p.inputs is None else "receita"), per_product)
            if p.food:
                self.assertIn((p.key, "consumo"), per_product)

    def test_matriz_stars_are_uniform_and_industrial_stars_come_from_the_document(self):
        self.assertEqual({p.min_stars for p in PRODUCTS if p.sector in (Sector.AGRO, Sector.EXTRACTIVE, Sector.MINING)},
                         {prov.MATRIZ_MIN_STARS})

    def test_militia_has_no_stars_and_the_army_products_use_the_provisional_star(self):
        for p in PRODUCTS:
            if p.sector == Sector.MILITIA:
                self.assertIsNone(p.min_stars, p.key)
            if p.sector == Sector.MILITARY_PROCUREMENT:
                self.assertEqual(p.min_stars, prov.ARMY_MIN_STARS, p.key)

    def test_army_and_militia_products_all_have_recipes_and_are_distinct_entities(self):
        self.assertEqual({p.key for p in PRODUCTS if p.sector == Sector.MILITARY_PROCUREMENT},
                         {"military_weapons", "military_armor", "military_medical_kits"})
        self.assertTrue(all(p.inputs for p in PRODUCTS if p.sector in (Sector.MILITARY_PROCUREMENT, Sector.MILITIA)))
        self.assertEqual([i.key for i in BY_KEY["military_weapons"].inputs], [i.key for i in BY_KEY["improvised_weapons"].inputs])
        self.assertEqual({BY_KEY[k].name for k in ("improvised_weapons", "improvised_armor", "militia_medical_kit")},
                         {"Armas Improvisadas", "Armaduras Improvisadas", "Kit Médico Improvisado"})
        self.assertEqual({BY_KEY[k].name for k in ("military_weapons", "military_armor", "military_medical_kits")},
                         {"Armas Militares", "Armaduras Militares", "Kits de Primeiros Socorros do Exército"})

    def test_bread_is_a_consumable_food(self):
        bread = BY_KEY["bread"]
        self.assertEqual((bread.category, bread.is_consumable), (Category.FOOD, True))
        self.assertEqual((bread.food.nutrition_level, bread.food.qol_effect), (prov.BREAD_NUTRITION_LEVEL, prov.BREAD_QOL_EFFECT))

    def test_the_classification_follows_the_approved_rules(self):
        """Q6/Q7/Q8: uma categoria; tags separadas; canais declarados; sem Acabamentos; exclusivos do Exército fora do Varejo."""
        self.assertNotIn("finishings", BY_KEY)
        self.assertEqual({p.key for p in PRODUCTS if p.category is Category.FOOD}, {p.key for p in PRODUCTS if p.food})
        for p in PRODUCTS:
            self.assertEqual(p.is_military, p.category is Category.MILITARY, p.key)
            self.assertEqual(p.is_permanent, p.category is Category.DURABLE, p.key)
            if p.is_military:
                self.assertNotIn(Channel.INTER_COMPANY, p.channels, p.key)
                self.assertNotIn(Channel.RETAIL_SALE, p.channels, p.key)
            if p.inputs is None:
                self.assertEqual(p.category, Category.MATERIAL, p.key)
                self.assertIn(Channel.INTER_COMPANY, p.channels, p.key)
        self.assertEqual({p.key for p in PRODUCTS if Channel.ARMY_PROCUREMENT in p.channels}, {"military_weapons", "military_armor", "military_medical_kits"})
        self.assertEqual({p.key for p in PRODUCTS if Channel.SPECIAL_REQUISITION in p.channels},
                         {"steel", "wood", "plastic", "wool", "hospital_supplies"})
        self.assertTrue(all(p.category is not Category.MATERIAL for p in PRODUCTS if Channel.RETAIL_SALE in p.channels))


class DefinitionsMatchTheDesignDocumentTests(SimpleTestCase):
    """Fidelidade ao `design/22-Receitas-Produção.md`: se o arquivo mudar, este teste obriga a atualizar o catálogo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.matrix, cls.rows = parse_doc()
        cls.by_name = {}
        for p in PRODUCTS:
            for n in {p.name, *p.source_names}:
                assert cls.by_name.setdefault(n, p.key) == p.key, f"nome ambíguo: {n}"

    def resolve(self, name):
        self.assertIn(name, self.by_name, f"'{name}' do 22 não resolve para nenhum produto do catálogo")
        return self.by_name[name]

    def test_the_matrix_lists_exactly_the_raw_materials_by_terrain(self):
        sector = {"Agropecuária": Sector.AGRO, "Extrativismo": Sector.EXTRACTIVE, "Mineração": Sector.MINING}
        for terrain, names in self.matrix.items():
            self.assertEqual({self.resolve(n) for n in names}, {k for k, p in BY_KEY.items() if p.sector == sector[terrain]}, terrain)
        self.assertEqual(sum(len(v) for v in self.matrix.values()), 29)

    def test_every_recipe_row_matches_inputs_stars_and_food_columns(self):
        recipes = [(s, c) for s, c in self.rows if len(c) >= 3 and ("★" in c[2] or c[2] == "Não existe")]
        self.assertEqual(len(recipes), 44)
        for section, cells in recipes:
            p = BY_KEY[self.resolve(cells[0])]
            self.assertEqual([i.key for i in p.inputs], [self.resolve(n.strip()) for n in cells[1].split("+")], p.key)
            stars = None if cells[2] == "Não existe" else int(cells[2][0])   # "2★ [PROV]" também lê 2
            self.assertEqual(p.min_stars, stars, p.key)
            if len(cells) >= 5 and cells[3] != "—":
                self.assertEqual((p.food.nutrition_level, p.food.qol_effect), (NUTRITION[cells[3]], QOL[cells[4].strip("*")]), p.key)
            else:
                self.assertIsNone(p.food, p.key)

    def test_every_catalog_product_comes_from_the_document(self):
        in_doc = {self.resolve(n) for v in self.matrix.values() for n in v}
        in_doc |= {self.resolve(c[0]) for _, c in self.rows if len(c) >= 3 and ("★" in c[2] or c[2] == "Não existe")}
        self.assertEqual(in_doc, set(BY_KEY))

    def test_the_army_section_of_the_document_matches_the_catalog(self):
        army = [c for s, c in self.rows if s and s.startswith("Produtos militares do Exército") and "★" in c[2]]
        self.assertEqual({self.resolve(c[0]) for c in army}, {"military_weapons", "military_armor", "military_medical_kits"})
        self.assertTrue(all("[PROV]" in c[2] for c in army))

    def _table(self, heading):
        """Linhas de dados da tabela que vem logo após o título `heading` do 22."""
        text = DOC.read_text(encoding="utf-8").replace("\r", "")
        block = text.split(heading, 1)[1]
        out = []
        for line in block.splitlines()[1:]:
            if line.startswith("#") and out:
                break
            if line.startswith("|") and "---" not in line:
                out.append([c.strip() for c in line.strip().strip("|").split("|")])
        return out[1:]       # sem o cabeçalho

    def test_the_classification_table_of_the_document_is_what_the_catalog_generates(self):
        """§3 é GERADA (`manage.py list_provisional --format markdown`): se divergir, regenere o trecho."""
        self.assertEqual(self._table("### 3. Classificação e canais comerciais"), [list(r) for r in audit.classification_rows()])

    def test_the_provisional_tables_of_the_document_are_what_the_catalog_generates(self):
        general = self._table("#### 4.1 Parâmetros gerais")
        self.assertEqual(general, [[r.parameter, r.value, r.rule, r.source, r.status] for r in prov.general_rows()])
        prices = self._table("#### 4.2 Preço-base de referência por produto")
        self.assertEqual(prices, [[p.key, p.name, str(p.base_price)] for p in PRODUCTS])

    def test_documented_name_normalizations(self):
        """Normalizações aprovadas (GD, 2026-10-11): as variantes do 22 resolvem para a MESMA chave."""
        for variants, key in ((("Calçado", "Calçados"), "shoes"), (("Ovo", "Ovos"), "eggs"), (("Químico", "Químicos"), "chemicals"),
                              (("Materiais Hospitalares", "Materiais hospitalares"), "hospital_supplies"),
                              (("Grão de Café", "Grão de café"), "coffee_bean")):
            for v in variants:
                self.assertEqual(self.by_name[v], key)
        self.assertEqual({BY_KEY["shoes"].name, BY_KEY["eggs"].name, BY_KEY["chemicals"].name,
                          BY_KEY["hospital_supplies"].name, BY_KEY["coffee_bean"].name},
                         {"Calçados", "Ovos", "Químicos", "Materiais hospitalares", "Grão de café"})


class KnownGapsTests(SimpleTestCase):
    REQUIRED = {"GAP_OPERATIONAL_MATERIALS_UNDEFINED", "GAP_VEHICLE_RELATION_UNDEFINED"}
    RESOLVED = {"GAP_FINISHINGS_UNDEFINED", "GAP_MATRIZ_STARS_UNDEFINED", "GAP_ARMY_RECIPES_UNDEFINED",
                "GAP_ARMY_PRODUCER_SUBTYPE_UNDEFINED"}

    def test_the_open_gaps_are_registered_and_the_resolved_ones_are_gone(self):
        codes = {g.code for g in KNOWN_GAPS}
        self.assertEqual(codes, self.REQUIRED)
        self.assertFalse(codes & self.RESOLVED)

    def test_every_gap_says_who_cites_it_and_which_future_steps_it_blocks(self):
        for g in KNOWN_GAPS:
            self.assertTrue(g.description and g.referenced_by and g.blocks, g.code)
        self.assertEqual(len({g.code for g in KNOWN_GAPS}), len(KNOWN_GAPS))

    def test_the_gaps_appear_in_the_report_as_design_pending_not_errors(self):
        r = validate(PRODUCTS)
        self.assertLessEqual({g.code for g in KNOWN_GAPS}, set(r.pending_codes))
        self.assertTrue(r.ok)

    def test_the_gaps_are_traceable_in_the_changelog(self):
        text = (Path(__file__).resolve().parents[2] / "CHANGELOG_DEV.md").read_text(encoding="utf-8")
        for g in KNOWN_GAPS:
            self.assertIn(g.code, text, f"{g.code} não está registrada no CHANGELOG_DEV.md")
