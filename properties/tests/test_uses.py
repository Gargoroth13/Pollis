"""Mudança de uso do lote (10 §21; G6, GD 2026-10-29): aprovação automática quando o zoneamento e as restrições permitem; custo zero; gancho político só nega."""
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import override_settings

from companies import construction
from geography import zoning
from geography.constants import Category, Occupation
from geography.models import Lot
from ledger import services as ledger
from ledger.audit import ledger_metrics
from ledger.constants import AccountKind
from players import registry
from properties import params, services, sites, uses
from properties.models import Building, CompanyLocation, UseChange

from .test_sites import SitesBase

MIXED = override_settings(POLIS_GEOGRAPHY={"zoning_permissions": zoning.BOT_TEST_ZONING})


class UseBase(SitesBase):
    def setUp(self):
        super().setUp()
        self.retail = self.found(self.boss, "retail", "Loja", 0)
        self.plot = self.own(self.lot("residential", 2), self.retail)           # lote residencial da empresa

    def ask(self, use="commercial", lot=None, owner=None, player=None):
        return uses.change_use((player or self.boss).pk, {"lot": (lot or self.plot).pk, "owner": owner or self.company_ref(self.retail), "use": use})

    def history(self):
        return list(UseChange.objects.order_by("lot_id", "sequence").values_list("old_use", "new_use"))


class DefaultZoningTests(UseBase):
    def test_with_the_default_matrix_every_change_is_refused_and_the_use_is_the_category(self):
        res = self.ask("commercial")
        self.assertEqual((res.code, res.detail["base_allowed"]), ("ZONING_DOES_NOT_ALLOW_USE", False))
        self.assertEqual(UseChange.objects.count(), 0)
        self.assertEqual(uses.use_of_lot(self.plot), Category.RESIDENTIAL)
        self.assertEqual(uses.use_view(self.plot.pk)["zoning_allows"], ["residential"])

    def test_the_default_matrix_keeps_building_and_location_exactly_as_before(self):
        self.assertIsNone(uses.use_refusal(self.plot, Category.RESIDENTIAL))
        self.assertEqual(uses.use_refusal(self.plot, Category.COMMERCIAL).code, "LOT_USE_NOT_ALLOWED")


@MIXED
class MixedZoningTests(UseBase):
    def test_the_bot_test_preset_is_coherent_only_residential_and_commercial_mix(self):
        base = zoning.base_permissions()
        self.assertEqual({c.value: sorted(u.value for u in base[c]) for c in Category},
                         {"residential": ["commercial", "residential"], "commercial": ["commercial", "residential"], "industrial": ["industrial"],
                          "institutional": ["institutional"], "special": ["special"], "rural": ["rural"]})

    def test_the_owner_changes_the_use_automatically_at_no_cost_and_it_is_recorded(self):
        supply = ledger_metrics()["in_circulation"]
        balance = ledger.balance_of(ledger.get_or_create_account(AccountKind.COMPANY, self.retail).pk)
        res = self.ask("commercial")
        self.assertTrue(res.ok, res)
        self.assertEqual((res.detail["old_use"], res.detail["new_use"], res.detail["sequence"], res.detail["fee_cents"]), ("residential", "commercial", 1, 0))
        self.assertEqual(self.history(), [("residential", "commercial")])
        row = UseChange.objects.get()
        self.assertEqual((row.requested_by, row.owner_kind, row.owner_id, row.fee_cents, row.at), (self.boss.pk, "company", self.retail, 0, self.clk.now()))
        self.assertTrue(row.decision["zoning"]["allowed"])
        self.assertEqual(row.decision["rule"], "automatic_when_zoning_allows")
        self.assertEqual((ledger.balance_of(ledger.get_or_create_account(AccountKind.COMPANY, self.retail).pk), ledger_metrics()["in_circulation"]), (balance, supply))        # nenhum dinheiro se move
        self.assertEqual(uses.use_of_lot(self.plot), Category.COMMERCIAL)
        self.assertEqual(services.lot_view(self.plot.pk)["designated_use"], "commercial")

    def test_it_can_change_back_and_the_history_chains(self):
        self.assertTrue(self.ask("commercial").ok)
        self.assertTrue(self.ask("residential").ok)
        self.assertEqual(self.history(), [("residential", "commercial"), ("commercial", "residential")])
        self.assertEqual(uses.use_view(self.plot.pk)["history"][1]["sequence"], 2)

    def test_the_designated_use_decides_what_can_be_built_and_who_can_locate(self):
        self.assertEqual(uses.use_refusal(self.plot, Category.COMMERCIAL).code, "LOT_USE_NOT_DESIGNATED")           # zoneamento permite, mas não está designado
        self.assertTrue(self.ask("commercial").ok)
        self.assertIsNone(uses.use_refusal(self.plot, Category.COMMERCIAL))
        self.assertEqual(uses.use_refusal(self.plot, Category.RESIDENTIAL).code, "LOT_USE_NOT_DESIGNATED")

    def test_a_retail_company_locates_on_the_changed_lot_when_the_building_requirement_is_off(self):
        self.assertEqual(self.locate(self.retail, self.plot).code, "LOT_USE_NOT_DESIGNATED")
        self.assertTrue(self.ask("commercial").ok)
        self.assertTrue(self.locate(self.retail, self.plot).ok)
        self.assertEqual(self.ask("residential").code, "LOT_HAS_COMPANY")                                         # com empresa operando o uso não muda

    def test_the_construction_company_builds_the_commercial_building_only_after_the_change(self):
        from companies.models import Company
        Company.objects.filter(pk=self.build).update(stars=2)
        lot = self.own(self.lot("residential", 3), self.build)
        self.assertEqual(construction.start_construction(self.boss.pk, self.build, "commercial_1", lot.pk).code, "LOT_USE_NOT_DESIGNATED")
        self.assertTrue(self.ask("commercial", lot=lot, owner=self.company_ref(self.build)).ok)
        self.assertTrue(construction.start_construction(self.boss.pk, self.build, "commercial_1", lot.pk).ok)
        self.assertEqual(self.ask("residential", lot=lot, owner=self.company_ref(self.build)).code, "LOT_RESERVED")      # obra ativa

    def test_refusals(self):
        other = self.found(self.boss, "retail", "Outra", 0)
        cases = [
            (self.ask("castle"), "INVALID_USE"), (self.ask(7), "INVALID_USE"),
            (self.ask("residential"), "USE_UNCHANGED"),
            (self.ask(player=self.third), "NOT_OWNER"),
            (self.ask(owner=self.company_ref(other)), "NOT_LOT_OWNER"),
            (self.ask(owner=self.player_ref(self.boss)), "NOT_LOT_OWNER"),
            (self.ask(lot=Lot(pk=10 ** 9)), "LOT_NOT_FOUND"),
            (uses.change_use(10 ** 9, {"lot": self.plot.pk, "owner": self.company_ref(self.retail), "use": "commercial"}), "PLAYER_NOT_FOUND"),
            (uses.change_use(self.boss.pk, {"lot": self.plot.pk}), "INVALID_PARAMS"),
            (uses.change_use(self.boss.pk, {"lot": "x", "owner": self.company_ref(self.retail), "use": "commercial"}), "INVALID_PARAMS"),
            (uses.change_use(self.boss.pk, {"lot": self.plot.pk, "owner": {"kind": "government", "id": 1}, "use": "commercial"}), "INVALID_PARTY"),
        ]
        for res, code in cases:
            self.assertEqual((res.ok, res.code), (False, code))
        gov_lot = self.lot("residential", 0)                                                                        # lote do governo: nenhum dono privado
        self.assertEqual(self.ask(lot=gov_lot).code, "NOT_LOT_OWNER")
        self.assertEqual(UseChange.objects.count(), 0)

    def test_the_government_zoning_still_decides_for_other_categories(self):
        rural = self.own(self.rural(0), self.matrix)
        res = uses.change_use(self.boss.pk, {"lot": rural.pk, "owner": self.company_ref(self.matrix), "use": "commercial"})
        self.assertEqual(res.code, "ZONING_DOES_NOT_ALLOW_USE")                                                   # rural isolado no preset

    def test_a_built_lot_an_open_listing_or_a_located_company_block_the_change(self):
        lot = self.own(self.lot("residential", 3), self.retail)
        house = self.built(company=self.retail)
        self.assertEqual(self.ask(lot=Lot.objects.get(pk=house.lot_id)).code, "USE_CHANGE_BUILDING_PRESENT")
        listing = services.list_property(self.boss.pk, lot.pk, self.company_ref(self.retail), 9_000).detail["listing"]
        self.assertEqual(self.ask(lot=lot).code, "LOT_RESERVED")
        self.assertTrue(services.unlist_property(self.boss.pk, listing, self.company_ref(self.retail)).ok)
        self.assertTrue(self.ask(lot=lot).ok)

    def test_a_law_override_that_forbids_wins_and_one_that_allows_is_respected(self):
        zoning.register_zoning_override("ban", lambda lot, use: False if use is Category.COMMERCIAL else None)
        try:
            res = self.ask("commercial")
            self.assertEqual((res.code, res.detail["base_allowed"], res.detail["overridden_by"]), ("ZONING_DOES_NOT_ALLOW_USE", True, [["ban", False]]))
        finally:
            zoning.unregister_zoning_override("ban")
        self.assertTrue(self.ask("commercial").ok)

    def test_the_fee_is_zero_and_any_positive_value_is_refused_not_charged(self):
        with mock.patch.object(params, "USE_CHANGE_FEE_CENTS", 500):
            res = self.ask("commercial")
        self.assertEqual((res.code, res.detail["fee_cents"]), ("USE_CHANGE_FEE_UNDEFINED", 500))
        self.assertEqual(UseChange.objects.count(), 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            UseChange.objects.create(lot=self.plot, sequence=1, old_use="residential", new_use="commercial", requested_by=1, owner_kind="company", owner_id=1,
                                     fee_cents=1, at=0)

    def test_the_history_is_immutable_through_the_orm(self):
        self.assertTrue(self.ask("commercial").ok)
        row = UseChange.objects.get()
        row.new_use = "residential"
        with self.assertRaises(ValueError):
            row.save()

    def test_the_registry_offers_the_same_refusals_and_executes(self):
        target = {"lot": self.plot.pk, "owner": self.company_ref(self.retail), "use": "commercial"}
        self.assertEqual(registry.check_action(self.third.pk, "change_lot_use", target).code, "NOT_OWNER")
        check = registry.check_action(self.boss.pk, "change_lot_use", target)
        self.assertEqual((check.available, check.preview["use"]["designated_use"]), (True, "residential"))
        self.assertTrue(registry.execute_action(self.boss.pk, "change_lot_use", target).ok)
        self.assertEqual(registry.check_action(self.boss.pk, "change_lot_use", target).code, "USE_UNCHANGED")
        self.assertEqual(registry.execute_action(self.boss.pk, "change_lot_use", None).code, "TARGET_REQUIRED")


@MIXED
class PoliticalHookTests(UseBase):
    """O gancho de aprovação política só NEGA: nunca aprova o que o zoneamento ou as restrições recusam; sem regra de votação/competência."""

    def test_without_approvers_it_is_approved(self):
        self.assertTrue(self.ask("commercial").ok)

    def test_an_approver_can_deny_and_receives_the_facts(self):
        seen = []

        def deny(lot, old, new, requester):
            seen.append((lot.pk, old, new, requester))
            return uses.refuse("USE_CHANGE_DENIED_BY_APPROVER", by="test")
        uses.register_use_change_approver("t", deny)
        self.addCleanup(uses.unregister_use_change_approver, "t")
        res = self.ask("commercial")
        self.assertEqual((res.code, UseChange.objects.count()), ("USE_CHANGE_DENIED_BY_APPROVER", 0))
        self.assertEqual(seen, [(self.plot.pk, Category.RESIDENTIAL, Category.COMMERCIAL, self.boss.pk)])

    def test_an_approving_approver_never_overrides_the_zoning(self):
        uses.register_use_change_approver("yes", lambda *a: None)
        self.addCleanup(uses.unregister_use_change_approver, "yes")
        rural = self.own(self.rural(0), self.matrix)
        res = uses.change_use(self.boss.pk, {"lot": rural.pk, "owner": self.company_ref(self.matrix), "use": "commercial"})
        self.assertEqual(res.code, "ZONING_DOES_NOT_ALLOW_USE")

    def test_the_decision_lists_the_approvers_and_restrictions_consulted(self):
        uses.register_use_change_approver("a", lambda *x: None)
        uses.register_use_change_restriction("r", lambda *x: None)
        self.addCleanup(uses.unregister_use_change_approver, "a")
        self.addCleanup(uses.unregister_use_change_restriction, "r")
        res = self.ask("commercial")
        self.assertEqual((res.detail["decision"]["approvers_consulted"], res.detail["decision"]["restrictions_checked"]), (["a"], ["r"]))

    def test_a_lot_restriction_can_refuse(self):
        uses.register_use_change_restriction("hist", lambda lot, old, new, owner: uses.refuse("LOT_RESTRICTION", why="tombado"))
        self.addCleanup(uses.unregister_use_change_restriction, "hist")
        self.assertEqual(self.ask("commercial").code, "LOT_RESTRICTION")

    def test_duplicate_registrations_are_errors(self):
        uses.register_use_change_approver("d", lambda *a: None)
        self.addCleanup(uses.unregister_use_change_approver, "d")
        with self.assertRaises(ValueError):
            uses.register_use_change_approver("d", lambda *a: None)
        uses.register_use_change_restriction("d", lambda *a: None)
        self.addCleanup(uses.unregister_use_change_restriction, "d")
        with self.assertRaises(ValueError):
            uses.register_use_change_restriction("d", lambda *a: None)


@MIXED
class UseAuditTests(UseBase):
    def test_a_clean_history_passes_and_tampering_is_found(self):
        self.assertTrue(self.ask("commercial").ok)
        self.assertTrue(self.ask("residential").ok)
        self.assertEqual(self.audit_codes(), set())
        UseChange.objects.filter(sequence=2).update(old_use="rural")
        self.assertIn("USE_CHANGE_CHAIN_BROKEN", self.audit_codes())
        UseChange.objects.filter(sequence=2).update(old_use="commercial", new_use="commercial")
        self.assertIn("USE_CHANGE_NO_CHANGE", self.audit_codes())
        UseChange.objects.filter(sequence=2).update(new_use="residential", decision={})
        self.assertIn("USE_CHANGE_FEE_OR_DECISION", self.audit_codes())
        UseChange.objects.filter(sequence=2).update(decision={"rule": "x"})
        UseChange.objects.filter(sequence=2).update(sequence=5)
        self.assertIn("USE_CHANGE_SEQUENCE_GAP", self.audit_codes())
        UseChange.objects.filter(sequence=5).update(sequence=2)

    def test_the_audit_flags_a_building_outside_the_designated_use(self):
        house = self.built(company=self.retail)
        self.assertEqual(self.audit_codes(), set())
        UseChange.objects.create(lot_id=house.lot_id, sequence=1, old_use="residential", new_use="commercial", requested_by=self.boss.pk, owner_kind="company",
                                 owner_id=self.retail, fee_cents=0, at=0, decision={"rule": "x"})
        self.assertIn("BUILDING_USE_NOT_DESIGNATED", self.audit_codes())
        UseChange.objects.all().delete()

    def test_the_audit_flags_a_located_company_whose_lot_use_is_not_designated(self):
        self.assertTrue(self.ask("commercial").ok)
        self.assertTrue(self.locate(self.retail, self.plot).ok)
        self.assertEqual(self.audit_codes(), set())
        UseChange.objects.all().delete()
        self.assertIn("LOCATION_LOT_USE_NOT_DESIGNATED", self.audit_codes())
        CompanyLocation.objects.all().delete()
        Lot.objects.filter(pk=self.plot.pk).update(occupation=Occupation.EMPTY.value)
