"""As definições transcritas do 22: estrutura válida, fiéis ao arquivo de design e sem número inventado."""
import re
from pathlib import Path

from django.test import SimpleTestCase

from catalog.constants import NutritionLevel, QolEffect, Sector
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
    """Lê o 22 como está: matriz por terreno, tabelas de receitas por sub-tipo e a lista do Exército."""
    text = DOC.read_text(encoding="utf-8").replace("\r", "")
    matrix, rows, army, section = {}, [], [], None
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
        if section and section.startswith("Produtos militares") and line.strip() and not line.startswith("**"):
            army.append(line.strip())
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 3 and "---" not in line and cells[0] not in ("Produto final", "Terreno"):
            rows.append((section, cells))
    return matrix, rows, army


class DefinitionsAreValidTests(SimpleTestCase):
    def test_no_integrity_error_and_expected_size(self):
        r = validate(PRODUCTS)
        self.assertEqual(r.errors, [])
        self.assertEqual((r.stats["products"], r.stats["raw"], r.stats["recipes"], r.stats["foods"]), (73, 29, 41, 7))

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

    def test_no_numeric_value_was_invented(self):
        """GD (2026-10-11): o 22 não dá quantidade, rendimento, Nutrição numérica nem intensidade: tudo None.
        Se o design passar a especificar valores, ESTE teste deve ser atualizado junto com as definições."""
        for p in PRODUCTS:
            self.assertIsNone(p.yield_quantity, p.key)
            for i in p.inputs or ():
                self.assertIsNone(i.quantity, f"{p.key}:{i.key}")
            if p.food:
                self.assertEqual((p.food.nutrition_amount, p.food.qol_intensity), (None, None), p.key)
        self.assertTrue(all(p.min_stars is None for p in PRODUCTS if p.sector in (Sector.AGRO, Sector.EXTRACTIVE, Sector.MINING)))

    def test_militia_and_army_products_have_no_stars(self):
        for p in PRODUCTS:
            if p.sector in (Sector.MILITIA, Sector.MILITARY_PROCUREMENT):
                self.assertIsNone(p.min_stars, p.key)

    def test_army_products_have_no_recipe_and_militia_products_do(self):
        self.assertEqual({p.key for p in PRODUCTS if p.sector == Sector.MILITARY_PROCUREMENT},
                         {"military_weapons", "military_armor", "military_medical_kits"})
        self.assertTrue(all(p.inputs is None for p in PRODUCTS if p.sector == Sector.MILITARY_PROCUREMENT))
        self.assertTrue(all(p.inputs for p in PRODUCTS if p.sector == Sector.MILITIA))

    def test_the_two_medical_kits_stay_distinct_entities(self):
        self.assertNotEqual(BY_KEY["militia_medical_kit"].name, BY_KEY["military_medical_kits"].name)
        self.assertNotEqual(BY_KEY["militia_medical_kit"].sector, BY_KEY["military_medical_kits"].sector)


class DefinitionsMatchTheDesignDocumentTests(SimpleTestCase):
    """Fidelidade ao `design/22-Receitas-Produção.md`: se o arquivo mudar, este teste obriga a atualizar o catálogo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.matrix, cls.rows, cls.army = parse_doc()
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
        self.assertEqual(len(recipes), 41)
        for section, cells in recipes:
            p = BY_KEY[self.resolve(cells[0])]
            self.assertEqual([i.key for i in p.inputs], [self.resolve(n.strip()) for n in cells[1].split("+")], p.key)
            stars = None if cells[2] == "Não existe" else int(cells[2][0])
            self.assertEqual(p.min_stars, stars, p.key)
            if len(cells) >= 5 and cells[3] != "—":
                self.assertEqual((p.food.nutrition_level, p.food.qol_effect), (NUTRITION[cells[3]], QOL[cells[4].strip("*")]), p.key)
            else:
                self.assertIsNone(p.food, p.key)

    def test_army_products_listed_in_the_document(self):
        self.assertEqual({self.resolve(n) for n in self.army}, {"military_weapons", "military_armor", "military_medical_kits"})

    def test_every_catalog_product_comes_from_the_document(self):
        in_doc = {self.resolve(n) for v in self.matrix.values() for n in v}
        in_doc |= {self.resolve(c[0]) for _, c in self.rows if len(c) >= 3 and ("★" in c[2] or c[2] == "Não existe")}
        in_doc |= {self.resolve(n) for n in self.army}
        self.assertEqual(in_doc, set(BY_KEY))

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
    REQUIRED = {"GAP_FINISHINGS_UNDEFINED", "GAP_OPERATIONAL_MATERIALS_UNDEFINED", "GAP_MATRIZ_STARS_UNDEFINED"}

    def test_the_gaps_named_by_the_game_director_are_registered(self):
        self.assertLessEqual(self.REQUIRED, {g.code for g in KNOWN_GAPS})

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
