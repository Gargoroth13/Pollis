"""Obra com lote (10 §5-6, §28): a Construtora constrói no lote que é dela; a conclusão gera o imóvel; auditoria detecta adulteração."""
from decimal import Decimal

from companies import construction, params as company_params
from companies.models import ConstructionJob
from geography import zoning
from geography.models import Lot
from players import registry
from properties import params, services
from properties.audit import audit_properties
from properties.models import Auction, Building, ConstructionSite, Listing, LotTitle, TitleEvent

from .base import PropertiesBase

D = Decimal


class SiteBase(PropertiesBase):
    def setUp(self):
        super().setUp()
        self.plot = self.lot()
        self.sold_to(self.boss, self.plot, price=3_000, party=self.company_ref(self.build))       # a Construtora compra o terreno

    def start(self, lot=None, project="low_density_simple", player=None):
        return construction.start_construction((player or self.boss).pk, self.build, project, (lot or self.plot).pk)

    def finish(self, shortcut=False):
        """Faz o pedreiro trabalhar até concluir. `shortcut` leva a obra a 99% antes (as obras grandes têm centenas de trabalhos)."""
        if shortcut:
            ConstructionJob.objects.filter(status="active").update(progress=D(99))
        self.set_skill(self.mason, "physical", 100)
        for _ in range(80):
            res = self.builder_work()
            self.assertTrue(res.ok, res)
            if res.detail["hooks"][construction.ACTION_HOOK]["completed"]:
                return res
        self.fail("a obra não concluiu")

    def findings(self):
        return {f["code"] for f in audit_properties().findings}


class StartTests(SiteBase):
    def test_the_building_company_starts_on_its_own_empty_lot_and_the_site_is_linked(self):
        res = self.start()
        self.assertTrue(res.ok, res)
        self.assertEqual(res.detail["lot"], self.plot.pk)
        site = ConstructionSite.objects.get()
        self.assertEqual((site.job_id, site.lot_id, site.company_id, site.project, site.status),
                         (ConstructionJob.objects.get().pk, self.plot.pk, self.build, "low_density_simple", "active"))
        view = services.lot_view(self.plot.pk)
        self.assertEqual(view["active_site"], {"job": site.job_id, "project": "low_density_simple"})
        self.assertEqual(view["occupation"], "empty")

    def test_the_lot_must_belong_to_the_builder_company_itself(self):
        gov = self.lot(n=1)
        res = self.start(gov)
        self.assertEqual((res.code, res.detail["lot"]), ("LOT_NOT_OWNED_BY_BUILDER", gov.pk))             # governo
        other = self.lot(n=2)
        self.sold_to(self.worker, other, price=1_000)
        self.assertEqual(self.start(other).code, "LOT_NOT_OWNED_BY_BUILDER")                              # de outro jogador
        self.sold_to(self.boss, self.lot(n=3), price=1_000, party=self.company_ref(self.firm))
        self.assertEqual(self.start(self.lot(n=3)).code, "LOT_NOT_OWNED_BY_BUILDER")                      # de outra empresa do mesmo Dono
        self.assertEqual(ConstructionJob.objects.count(), 0)
        self.assertEqual(ConstructionSite.objects.count(), 0)

    def test_invalid_lots_and_states(self):
        self.assertEqual(self.start(type(self.plot)(pk=10 ** 9)).code, "LOT_NOT_FOUND")
        self.assertEqual(construction.start_construction(self.boss.pk, self.build, "low_density_simple", "x").code, "INVALID_PARAMS")
        self.assertEqual(construction.start_construction(self.boss.pk, self.build, "low_density_simple", True).code, "INVALID_PARAMS")
        self.assertEqual(self.start(player=self.mason).code, "NOT_OWNER")
        Lot.objects.filter(pk=self.plot.pk).update(occupation="occupied")
        self.assertEqual(self.start().code, "LOT_OCCUPIED")

    def test_zoning_must_allow_housing_on_the_lot(self):
        commercial = self.lot("commercial")
        self.sold_to(self.boss, commercial, price=1_000, party=self.company_ref(self.build))
        res = self.start(commercial)
        self.assertEqual((res.code, res.detail["category"], res.detail["use"]), ("LOT_USE_NOT_ALLOWED", "commercial", "residential"))
        zoning.register_zoning_override("test_ban", lambda lot, use: False if lot.pk == self.plot.pk and use.value == "residential" else None)
        self.addCleanup(zoning.unregister_zoning_override, "test_ban")
        self.assertEqual(self.start().code, "LOT_USE_NOT_ALLOWED")                                       # leis/projetos mudam a decisão

    def test_a_listed_lot_is_reserved_and_the_registry_offers_the_same_refusal(self):
        li = services.list_property(self.boss.pk, self.plot.pk, self.company_ref(self.build), 9_000)
        self.assertTrue(li.ok, li)
        self.assertEqual(self.start().code, "LOT_RESERVED")
        target = {"company": self.build, "project": "low_density_simple", "lot": self.plot.pk}
        self.assertEqual(registry.check_action(self.boss.pk, "start_construction", target).code, "LOT_RESERVED")
        self.assertTrue(services.unlist_property(self.boss.pk, li.detail["listing"], self.company_ref(self.build)).ok)
        self.assertTrue(registry.check_action(self.boss.pk, "start_construction", target).available)
        res = registry.execute_action(self.boss.pk, "start_construction", target)
        self.assertTrue(res.ok, res)
        self.assertEqual(registry.check_action(self.boss.pk, "start_construction", {**target, "bogus": 1}).code, "INVALID_PARAMS")

    def test_one_active_site_per_lot_and_per_company(self):
        self.assertTrue(self.start().ok)
        self.assertEqual(self.start().code, "CONSTRUCTION_ACTIVE")                                       # a Construtora só tem uma obra ativa
        self.assertEqual(ConstructionSite.objects.count(), 1)

    def test_without_a_lot_the_old_construction_still_works_and_creates_no_building(self):
        res = construction.start_construction(self.boss.pk, self.build, "low_density_simple")
        self.assertTrue(res.ok, res)
        self.assertIsNone(res.detail["lot"])
        self.finish()
        self.assertEqual((Building.objects.count(), ConstructionSite.objects.count()), (0, 0))          # lacuna registrada em design/10a

    def test_without_the_properties_system_a_lot_is_not_supported(self):
        validators = dict(construction._start_validators)
        construction._start_validators.clear()
        self.addCleanup(construction._start_validators.update, validators)
        self.assertEqual(self.start().code, "LOT_NOT_SUPPORTED")

    def test_a_cancelled_start_leaves_no_site(self):
        before = ConstructionJob.objects.count()
        self.start(self.lot(n=1))                                   # recusado: lote do governo
        self.assertEqual((ConstructionJob.objects.count(), ConstructionSite.objects.count()), (before, 0))


class CompletionTests(SiteBase):
    def test_completing_the_work_creates_the_building_occupies_the_lot_and_closes_the_site(self):
        self.assertTrue(self.start().ok)
        self.finish()
        b = Building.objects.get()
        self.assertEqual((b.lot_id, b.kind, b.units, b.qol_bonus, b.builder_company_id), (self.plot.pk, "low_density_simple", 1, D("0"), self.build))
        job = ConstructionJob.objects.get()
        self.assertEqual((b.job_id, b.completed_at), (job.pk, job.completed_at))
        self.assertEqual(Lot.objects.get(pk=self.plot.pk).occupation, "occupied")
        self.assertEqual(ConstructionSite.objects.get().status, "completed")
        self.assertEqual(services.owner_of_lot(self.plot.pk), (services.OwnerKind.COMPANY, self.build))   # o dono do terreno é o dono do imóvel
        view = services.lot_view(self.plot.pk)
        self.assertEqual((view["building"], view["active_site"]),
                         ({"kind": "low_density_simple", "family": "residential", "level": None, "units": 1, "qol_bonus": "0.00"}, None))
        self.assertEqual(self.findings(), set())

    def test_a_built_lot_is_not_built_again_nor_auctioned_and_may_be_sold_with_its_building(self):
        self.assertTrue(self.start().ok)
        self.finish()
        self.assertEqual(self.start().code, "LOT_OCCUPIED")
        self.assertEqual(services.open_auction(self.plot.pk, 100).code, "LOT_NOT_GOVERNMENT_OWNED")
        li = services.list_property(self.boss.pk, self.plot.pk, self.company_ref(self.build), 90_000)
        self.assertTrue(li.ok, li)
        res = services.buy_property(self.worker.pk, li.detail["listing"], self.player_ref(self.worker))
        self.assertTrue(res.ok, res)
        view = services.lot_view(self.plot.pk)
        self.assertEqual((view["owner"], view["building"]["kind"]), (["player", self.worker.pk], "low_density_simple"))   # 10 §3: mesmo ativo
        self.assertEqual(Building.objects.get().builder_company_id, self.build)

    def test_the_building_types_follow_the_design_table_and_the_construction_projects(self):
        self.assertEqual({k: (b.units, b.qol_bonus, b.min_stars) for k, b in params.BUILDING_TYPES.items()},
                         {"low_density_simple": (1, D("0"), 1), "low_density_luxury": (1, D("0.3"), 3),
                          "high_density_simple": (20, D("0.1"), 2), "high_density_luxury": (20, D("0.4"), 4),
                          # G5 (GD 2026-10-29): comercial nível 1–5 (Construtora ≥ nível) e industrial único sem nível (Construtora ≥ 2★); sem unidades
                          **{f"commercial_{n}": (0, D("0"), n) for n in range(1, 6)}, "industrial": (0, D("0"), 2)})
        self.assertEqual({k: (b.family.value, b.level) for k, b in params.BUILDING_TYPES.items() if b.family.value != "residential"},
                         {**{f"commercial_{n}": ("commercial", n) for n in range(1, 6)}, "industrial": ("industrial", None)})
        self.assertEqual({k: p.work_units for k, p in company_params.CONSTRUCTION_PROJECTS.items() if k.startswith("commercial_") or k == "industrial"},
                         {"commercial_1": 50, "commercial_2": 100, "commercial_3": 200, "commercial_4": 400, "commercial_5": 800, "industrial": 200})
        self.assertEqual({k: p.min_stars for k, p in company_params.CONSTRUCTION_PROJECTS.items()},
                         {k: b.min_stars for k, b in params.BUILDING_TYPES.items()})

    def test_each_project_creates_the_building_of_its_type(self):
        from companies.models import Company
        self.audit_companies_at_end = False                  # `finish(shortcut=True)` adianta o progresso direto no banco (de propósito)
        Company.objects.filter(pk=self.build).update(stars=5)
        used = {}
        for key, kind in params.BUILDING_TYPES.items():
            if key in ("commercial_2", "commercial_4"):
                continue                                           # o mundo pequeno só tem 3 lotes comerciais: níveis 1, 3 e 5 (a tabela de todos está no teste acima)
            category = params.FAMILY_USE[kind.family].value
            used[category] = used.get(category, 0) + 1
            lot = self.lot(category, used[category])                                  # cada família no lote da sua categoria (zoneamento)
            self.sold_to(self.boss, lot, price=1_000, party=self.company_ref(self.build))
            self.assertTrue(self.start(lot, key).ok, key)
            self.finish(shortcut=True)
            b = Building.objects.get(lot=lot)
            self.assertEqual((b.kind, b.units, b.qol_bonus, b.family, b.level), (key, kind.units, kind.qol_bonus, kind.family.value, kind.level))
            self.assertEqual(b.unit_rows.count(), kind.units)
        self.assertEqual(self.findings(), set())

    def test_the_work_that_completes_the_obra_and_the_building_are_one_transaction(self):
        self.assertTrue(self.start().ok)
        original = services._completion_hook
        def boom(job):
            raise RuntimeError("falha no hook")
        construction._completion_hooks[services.HOOK_NAME] = boom
        self.addCleanup(construction._completion_hooks.__setitem__, services.HOOK_NAME, original)
        self.set_skill(self.mason, "physical", 100)
        with self.assertRaises(RuntimeError):
            for _ in range(80):
                self.builder_work()
        job = ConstructionJob.objects.get()
        self.assertEqual(job.status, "active")                           # nada ficou pela metade
        self.assertEqual(Building.objects.count(), 0)


class AuditTests(SiteBase):
    """A auditoria enxerga adulteração direta no banco (o teste a faz de propósito)."""

    audit_properties_at_end = False

    def setUp(self):
        super().setUp()
        self.audit_companies_at_end = False

    def test_a_clean_world_is_clean(self):
        self.assertTrue(self.start().ok)
        self.finish()
        a = self.auction(self.lot(n=1))
        self.assertTrue(self.bid(self.worker, a, 5_000).ok)
        self.assertEqual(self.findings(), set())
        self.assertEqual(audit_properties().stats["buildings"], 1)

    def test_title_not_matching_the_chain_is_found(self):
        LotTitle.objects.filter(lot=self.plot).update(owner_kind="player", owner_id=self.worker.pk)
        self.assertIn("TITLE_NOT_LAST_EVENT", self.findings())

    def test_a_title_event_without_its_payment_or_with_another_price_is_found(self):
        TitleEvent.objects.filter(lot=self.plot).update(price_cents=1)
        self.assertIn("TITLE_PRICE_MISMATCH", self.findings())

    def test_a_broken_chain_is_found(self):
        TitleEvent.objects.filter(lot=self.plot).update(sequence=3)
        self.assertTrue({"TITLE_SEQUENCE_GAP"} <= self.findings())

    def test_auction_with_inconsistent_top_bid_is_found(self):
        a = self.auction(self.lot(n=1))
        self.assertTrue(self.bid(self.worker, a, 5_000).ok)
        Auction.objects.filter(pk=a).update(top_bid_cents=9_000)
        self.assertIn("TOP_BID_MISMATCH", self.findings())

    def test_a_sold_auction_without_title_is_found(self):
        a = self.auction(self.lot(n=1))
        Auction.objects.filter(pk=a).update(status="sold", closed_at=1)
        self.assertIn("SOLD_WITHOUT_TITLE_OR_PAYMENT", self.findings())

    def test_a_building_on_a_lot_that_is_not_occupied_or_that_the_government_owns_is_found(self):
        self.assertTrue(self.start().ok)
        self.finish()
        Lot.objects.filter(pk=self.plot.pk).update(occupation="empty")
        self.assertIn("BUILDING_LOT_NOT_OCCUPIED", self.findings())
        LotTitle.objects.filter(lot=self.plot).update(owner_kind="government", owner_id=None)
        self.assertIn("BUILDING_WITHOUT_PRIVATE_OWNER", self.findings())

    def test_an_open_listing_of_someone_who_no_longer_owns_the_lot_is_found(self):
        Listing.objects.create(lot=self.plot, seller_kind="player", seller_id=self.worker.pk, price_cents=1, listed_at=0)
        self.assertIn("OPEN_LISTING_SELLER_NOT_OWNER", self.findings())

    def test_the_commands_run(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("audit_properties", stdout=out)
        self.assertIn("achados=0", out.getvalue())
        out = StringIO()
        call_command("open_auctions", lot=[self.lot(n=2).pk], min_bid=500, stdout=out)
        self.assertEqual(Auction.objects.filter(status="open").count(), 1)
