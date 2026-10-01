from decimal import Decimal

from django.test import SimpleTestCase

from core.breakdown import Calc, D, Explained, StepKind


class CalcTests(SimpleTestCase):
    def test_additive_formula_matches_doc20_example(self):
        """design/20: QoL 0,76 = base 0,82 + moradia... com componentes visíveis."""
        r = (Calc("base", "0.82").add("housing", "0.10").add("overpopulation", "-0.10")
             .add("nutrition", "-0.04").add("health", "-0.02").result())
        self.assertEqual(r.value, Decimal("0.76"))
        self.assertEqual([s.key for s in r.steps], ["base", "housing", "overpopulation", "nutrition", "health"])
        self.assertEqual([s.result for s in r.steps], [Decimal(x) for x in ("0.82", "0.92", "0.82", "0.78", "0.76")])

    def test_multiplicative_formula_matches_doc20_example(self):
        r = Calc("base", 1200).mul("employees", "1.25").mul("engineers", "1.30").mul("specialization", "0.95").result()
        self.assertEqual(r.value, Decimal("1200") * Decimal("1.25") * Decimal("1.30") * Decimal("0.95"))
        self.assertTrue(all(s.kind == StepKind.MULTIPLY for s in r.steps[1:]))

    def test_cap_reports_which_rule_restricted(self):
        """20.3: 125% disponível, teto 100% -> resultado 100%, e o teto aparece como restritivo."""
        r = Calc("available", 125).cap("operational_limit", 100).result()
        self.assertEqual(r.value, 100)
        self.assertEqual(r.restricted_by, ("operational_limit",))
        self.assertTrue(r.step("operational_limit").binding)

    def test_non_binding_limit_is_recorded_but_not_restrictive(self):
        r = Calc("salary", 150).cap("legal_cap", 180).floor("minimum", 50).result()
        self.assertEqual(r.value, 150)
        self.assertEqual(r.restricted_by, ())
        self.assertFalse(r.step("legal_cap").binding)  # existe no detalhamento, mas não restringiu

    def test_conditional_formula_doc20_salary_example(self):
        r = Calc("calculated_by_skill", 210).floor("minimum", 50).cap("legal_cap", 180).result()
        self.assertEqual((r.value, r.restricted_by), (180, ("legal_cap",)))

    def test_floor_binding(self):
        r = Calc("regen", "0.5").floor("regen_floor", 1).result()
        self.assertEqual((r.value, r.restricted_by), (1, ("regen_floor",)))

    def test_hierarchical_detail(self):
        inner = Calc("human", 620).mul("specialization", "0.775").result()
        outer = Calc("base", 0).add("human_force", inner.value, detail=inner).result()
        self.assertIs(outer.step("human_force").detail, inner)
        self.assertEqual(outer.to_dict()["steps"][1]["detail"]["value"], str(inner.value))

    def test_values_are_never_rounded(self):
        r = Calc("a", "0.1").mul("third", Decimal(1) / Decimal(3)).result()
        self.assertGreater(len(str(r.value)), 20)  # 20.8: arredondar é da UI

    def test_float_is_rejected(self):
        for bad in (lambda: D(0.1), lambda: Calc("a", 1.5), lambda: Calc("a", 1).add("b", 0.1)):
            with self.assertRaises(TypeError):
                bad()

    def test_to_dict_is_pure_data_json_serializable(self):
        import json
        r = Calc("a", 1).add("b", "0.5").cap("c", 1).result(computed_at=123)
        d = r.to_dict()
        self.assertEqual(json.loads(json.dumps(d)), d)
        self.assertEqual(d["computed_at"], 123)
        self.assertEqual(d["steps"][2], {"key": "c", "kind": "cap", "amount": "1", "result": "1", "binding": True})

    def test_step_lookup(self):
        r = Calc("a", 1).add("b", 2).result()
        self.assertTrue(r.has("b") and not r.has("zzz"))
        with self.assertRaises(KeyError):
            r.step("zzz")
