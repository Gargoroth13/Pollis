from geography import zoning
from geography.balance import get_scenario
from geography.constants import Category
from geography.models import Lot
from geography.zoning import ZoningConflict

from .base import GeoTestCase


class ZoningTests(GeoTestCase):
    def setUp(self):
        super().setUp()
        self.sc = self.world()
        self.res = Lot.objects.filter(category="residential").first()
        self.com = Lot.objects.filter(category="commercial").first()
        self.ind = Lot.objects.filter(category="industrial").first()
        for name in ("law_a", "law_b"):
            self.addCleanup(zoning.unregister_zoning_override, name)

    def test_default_keeps_uses_separated(self):
        """08 §16: por padrão, cada categoria só admite o próprio uso."""
        self.assertTrue(zoning.is_use_allowed(self.res, Category.RESIDENTIAL))
        self.assertFalse(zoning.is_use_allowed(self.res, Category.COMMERCIAL))
        self.assertFalse(zoning.is_use_allowed(self.com, Category.INDUSTRIAL))
        self.assertTrue(zoning.is_use_allowed(self.ind, Category.INDUSTRIAL))

    def test_every_category_admits_at_least_itself(self):
        base = zoning.base_permissions(self.sc)
        for c in Category:
            self.assertIn(c, base[c])

    def test_use_can_be_given_as_a_string(self):
        self.assertTrue(zoning.is_use_allowed(self.res, "residential"))

    def test_zoning_is_a_parameter_not_a_structural_rule(self):
        """08 §16/§23.4: parametrizável. Aqui o comercial também admite uso residencial."""
        sc = get_scenario(**{"zoning_permissions": {"commercial": ["commercial", "residential"]}})
        self.assertTrue(zoning.is_use_allowed(self.com, Category.RESIDENTIAL, sc))
        self.assertFalse(zoning.is_use_allowed(self.res, Category.COMMERCIAL, sc))      # a recíproca não vem de graça

    def test_a_law_can_liberate_a_use(self):
        """08 §16: leis e projetos 'poderão liberar determinados usos'."""
        zoning.register_zoning_override("law_a", lambda lot, use: True if (lot.category == "commercial" and use is Category.RESIDENTIAL) else None)
        d = zoning.decide(self.com, Category.RESIDENTIAL)
        self.assertEqual((d.allowed, d.base_allowed, d.overridden_by), (True, False, (("law_a", True),)))
        self.assertFalse(zoning.is_use_allowed(self.ind, Category.RESIDENTIAL))        # sem efeito fora do escopo da lei

    def test_a_law_can_restrict_a_use(self):
        zoning.register_zoning_override("law_a", lambda lot, use: False if lot.pk == self.res.pk else None)
        d = zoning.decide(self.res, Category.RESIDENTIAL)
        self.assertEqual((d.allowed, d.base_allowed), (False, True))
        other = Lot.objects.filter(category="residential").exclude(pk=self.res.pk).first()
        self.assertTrue(zoning.is_use_allowed(other, Category.RESIDENTIAL))            # "exceções territoriais": só este lote

    def test_a_law_that_does_not_opine_changes_nothing(self):
        zoning.register_zoning_override("law_a", lambda lot, use: None)
        d = zoning.decide(self.res, Category.RESIDENTIAL)
        self.assertEqual((d.allowed, d.overridden_by), (True, ()))

    def test_agreeing_laws_are_fine(self):
        zoning.register_zoning_override("law_a", lambda lot, use: True)
        zoning.register_zoning_override("law_b", lambda lot, use: True)
        self.assertTrue(zoning.is_use_allowed(self.res, Category.INDUSTRIAL))

    def test_conflicting_laws_fail_loudly_because_the_design_defines_no_precedence(self):
        zoning.register_zoning_override("law_a", lambda lot, use: True)
        zoning.register_zoning_override("law_b", lambda lot, use: False)
        with self.assertRaises(ZoningConflict):
            zoning.decide(self.res, Category.RESIDENTIAL)

    def test_override_names_are_unique(self):
        zoning.register_zoning_override("law_a", lambda lot, use: None)
        with self.assertRaises(ValueError):
            zoning.register_zoning_override("law_a", lambda lot, use: None)
