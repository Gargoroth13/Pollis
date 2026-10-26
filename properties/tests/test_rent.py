"""Aluguel (10 §9-13) como tipo do motor de contratos (18): anúncio, contrato, pagamento, inadimplência, fim, quebra e venda do imóvel alugado."""
from contracts import services as contracts
from contracts.audit import audit_contracts
from contracts.constants import Status
from contracts.models import Contract, ContractPartyChange
from ledger import services as ledger
from ledger.audit import audit_ledger, ledger_metrics
from ledger.constants import Nature
from ledger.models import Entry, Obligation
from players import registry
from properties import housing, rent, services
from properties.audit import audit_properties
from properties.models import ActiveResidence, RentListing, Tenancy

from .base import PropertiesBase


class RentBase(PropertiesBase):
    def setUp(self):
        super().setUp()
        self.addCleanup(self._audit_contracts)
        self.house = self.built(self.worker, kind="high_density_simple")
        self.u1, self.u2, self.u3 = (self.unit(self.house, i) for i in (1, 2, 3))
        self.owner = self.player_ref(self.worker)

    def _audit_contracts(self):
        report = audit_contracts()
        self.assertTrue(report.ok, report.findings)

    def listing(self, unit=None, **kw):
        res = self.rent_listing(unit or self.u1, self.owner, self.worker, **kw)
        self.assertTrue(res.ok, res)
        return res.detail["rent_listing"]

    def rented(self, tenant=None, unit=None, starts=1, ends=3, **kw):
        tenant = tenant or self.third
        li = self.listing(unit, **kw)
        res = self.rent_it(li, tenant, starts, ends)
        self.assertTrue(res.ok, res)
        return res.detail["contract"]

    def c(self, cid):
        return Contract.objects.get(pk=cid)

    def circulation(self):
        return ledger_metrics()["in_circulation"]


class ListingTests(RentBase):
    def test_the_owner_lists_a_unit_at_his_price_and_period(self):
        res = self.rent_listing(self.u1, self.owner, self.worker, 12_345, "weekly", penalty=500, max_failures=2)
        self.assertTrue(res.ok, res)
        row = RentListing.objects.get()
        self.assertEqual((row.unit_id, row.amount_cents, row.frequency, row.penalty_cents, row.max_failures, row.status),
                         (self.u1.pk, 12_345, "weekly", 500, 2, "open"))
        self.assertEqual(housing.unit_view(self.u1.pk)["rent_listing"], {"id": row.pk, "amount_cents": 12_345, "frequency": "weekly"})

    def test_refusals(self):
        L = lambda **kw: rent.list_rent(self.worker.pk, {"unit": self.u1.pk, "owner": self.owner, "amount": 100, "frequency": "daily", **kw})
        self.assertEqual(rent.list_rent(10 ** 9, {}).code, "PLAYER_NOT_FOUND")
        self.assertEqual(rent.list_rent(self.worker.pk, {"unit": 1}).code, "INVALID_PARAMS")
        self.assertEqual(L(amount=0).code, "INVALID_PARAMS")
        self.assertEqual(L(frequency="yearly").code, "INVALID_FREQUENCY")
        self.assertEqual(L(frequency="once").code, "INVALID_FREQUENCY")
        self.assertEqual(L(penalty=-1).code, "INVALID_PENALTY")
        self.assertEqual(L(max_failures=0).code, "INVALID_MAX_FAILURES")
        self.assertEqual(L(unit=10 ** 9).code, "UNIT_NOT_FOUND")
        self.assertEqual(L(owner={"kind": "government", "id": 1}).code, "INVALID_PARTY")
        self.assertEqual(rent.list_rent(self.third.pk, {"unit": self.u1.pk, "owner": self.player_ref(self.third), "amount": 100,
                                                        "frequency": "daily"}).code, "NOT_LOT_OWNER")
        self.assertEqual(rent.list_rent(self.third.pk, {"unit": self.u1.pk, "owner": self.owner, "amount": 100, "frequency": "daily"}).code,
                         "NOT_PARTY_REPRESENTATIVE")
        self.assertTrue(L().ok)
        self.assertEqual(L().code, "ALREADY_LISTED_FOR_RENT")
        self.assertEqual(RentListing.objects.count(), 1)

    def test_a_unit_the_owner_lives_in_cannot_be_listed_until_he_moves_out(self):
        self.assertTrue(housing.set_residence(self.worker.pk, self.u1.pk).ok)
        self.assertEqual(self.rent_listing(self.u1, self.owner, self.worker).code, "UNIT_OCCUPIED")
        self.assertTrue(housing.set_residence(self.worker.pk, None).ok)
        self.assertTrue(self.rent_listing(self.u1, self.owner, self.worker).ok)

    def test_the_owner_cannot_move_into_a_unit_that_is_listed_for_rent_until_he_withdraws_it(self):
        li = self.listing()
        self.assertEqual(housing.set_residence(self.worker.pk, self.u1.pk).code, "UNIT_LISTED_FOR_RENT")
        self.assertEqual(ActiveResidence.objects.count(), 0)
        self.assertTrue(rent.unlist_rent(self.worker.pk, {"listing": li, "owner": self.owner}).ok)
        self.assertTrue(housing.set_residence(self.worker.pk, self.u1.pk).ok)

    def test_the_owner_withdraws_the_listing(self):
        li = self.listing()
        self.assertEqual(rent.unlist_rent(self.third.pk, {"listing": li, "owner": self.player_ref(self.third)}).code, "NOT_SELLER")
        self.assertTrue(rent.unlist_rent(self.worker.pk, {"listing": li, "owner": self.owner}).ok)
        self.assertEqual(RentListing.objects.get().status, "cancelled")
        self.assertEqual(rent.unlist_rent(self.worker.pk, {"listing": li, "owner": self.owner}).code, "RENT_LISTING_NOT_OPEN")
        self.assertEqual(rent.unlist_rent(self.worker.pk, {"listing": 10 ** 9, "owner": self.owner}).code, "RENT_LISTING_NOT_FOUND")
        self.assertEqual(self.rent_it(li, self.third).code, "RENT_LISTING_NOT_OPEN")

    def test_a_company_landlord_lists_through_its_owner(self):
        built = self.built(company=self.build)
        unit = self.unit(built)
        res = rent.list_rent(self.boss.pk, {"unit": unit.pk, "owner": self.company_ref(self.build), "amount": 900, "frequency": "monthly"})
        self.assertTrue(res.ok, res)
        self.assertEqual(rent.list_rent(self.worker.pk, {"unit": unit.pk, "owner": self.company_ref(self.build), "amount": 900,
                                                         "frequency": "monthly"}).code, "NOT_OWNER")


class ContractTests(RentBase):
    def test_renting_a_listed_unit_proposes_and_accepts_in_one_act_and_binds_the_unit(self):
        cid = self.rented(amount=10_000)
        c = self.c(cid)
        self.assertEqual((c.type, c.status, c.party_a_kind, c.party_a_id, c.party_b_kind, c.party_b_id),
                         ("rent", "active", "player", self.worker.pk, "player", self.third.pk))
        self.assertEqual(c.terms, {"lot": self.house.lot_id, "unit": 1, "amount_cents": 10_000})
        self.assertEqual((c.frequency, c.starts_on, c.ends_on, c.occurrences), ("daily", self.day0 + 1, self.day0 + 3, 3))
        t = Tenancy.objects.get()
        self.assertEqual((t.contract_id, t.unit_id, t.tenant_kind, t.tenant_id), (cid, self.u1.pk, "player", self.third.pk))
        row = RentListing.objects.get()
        self.assertEqual((row.status, row.contract_id, row.close_reason), ("rented", cid, "rented"))
        self.assertEqual(housing.unit_view(self.u1.pk)["lease"]["contract"], cid)

    def test_the_listing_conditions_become_the_contract_conditions(self):
        cid = self.rented(frequency="weekly", penalty=700, max_failures=2, ends=20)
        c = self.c(cid)
        self.assertEqual((c.frequency, c.penalty_cents, c.max_failures), ("weekly", 700, 2))

    def test_the_rent_is_paid_by_the_tenant_to_the_owner_each_period_without_tax(self):
        cid = self.rented(amount=10_000)
        tenant, landlord, circulation = self.money(self.third), self.money(self.worker), self.circulation()
        self.go_day(1)
        self.go_day(2)
        paid = Entry.objects.filter(nature=Nature.RENT.value)
        self.assertEqual((paid.count(), sum(e.amount for e in paid)), (2, 20_000))
        self.assertFalse(Entry.objects.filter(nature=Nature.TAX_SALES.value).exists())
        self.assertEqual(self.money(self.third), tenant - 20_000)
        self.assertEqual(self.money(self.worker) - landlord, 20_000)                    # só aluguel: sem folha de Dono nesta empresa
        self.assertEqual(self.circulation(), circulation)                                 # nada se cria nem se perde
        self.go_day(3)
        self.assertEqual(self.c(cid).status, "closed")
        self.assertEqual(Entry.objects.filter(nature=Nature.RENT.value).count(), 3)

    def test_a_company_landlord_receives_the_rent_in_the_company_account(self):
        built = self.built(company=self.build)
        unit = self.unit(built)
        res = rent.list_rent(self.boss.pk, {"unit": unit.pk, "owner": self.company_ref(self.build), "amount": 4_000, "frequency": "daily"})
        li = res.detail["rent_listing"]
        cash = self.money_of("company", self.build)
        self.assertTrue(self.rent_it(li, self.third, 1, 2).ok)
        self.go_day(1)
        self.assertEqual(self.money_of("company", self.build) - cash, 4_000 - self.owner_salary_paid())

    def owner_salary_paid(self):
        return sum(Entry.objects.filter(nature=Nature.OWNER_SALARY.value, from_account_id=ledger.get_or_create_account(
            "company", self.build).pk).values_list("amount", flat=True))

    def test_a_direct_proposal_through_the_contract_actions_also_works(self):
        proposal = {"type": "rent", "role": "landlord", "proposer": self.owner, "counterparty": self.player_ref(self.third),
                    "terms": {"lot": self.house.lot_id, "unit": 2, "amount_cents": 3_000}, "frequency": "daily",
                    "starts_on": self.day0 + 1, "ends_on": self.day0 + 2}
        res = registry.execute_action(self.worker.pk, "propose_contract", proposal)
        self.assertTrue(res.ok, res)
        accepted = registry.execute_action(self.third.pk, "accept_contract", {"contract": res.detail["contract"], "party": self.player_ref(self.third)})
        self.assertTrue(accepted.ok, accepted)
        self.assertEqual(Tenancy.objects.get().unit_id, self.u2.pk)

    def test_proposal_refusals(self):
        base = {"type": "rent", "role": "landlord", "proposer": self.owner, "counterparty": self.player_ref(self.third),
                "terms": {"lot": self.house.lot_id, "unit": 1, "amount_cents": 3_000}, "frequency": "daily", "starts_on": self.day0 + 1,
                "ends_on": self.day0 + 2}

        def code(**over):
            p = {**base, **over}
            return contracts.propose(self.worker.pk, p).code

        self.assertEqual(code(terms={"lot": self.house.lot_id, "unit": 1}), "INVALID_TERMS")
        self.assertEqual(code(terms={**base["terms"], "unit": 99}), "UNIT_NOT_FOUND")
        self.assertEqual(code(terms={**base["terms"], "lot": 10 ** 9}), "UNIT_NOT_FOUND")
        self.assertEqual(code(terms={**base["terms"], "amount_cents": 0}), "INVALID_AMOUNT")
        self.assertEqual(code(frequency="once"), "INVALID_FREQUENCY")
        self.assertEqual(code(starts_on=self.day0), "INVALID_SCHEDULE")
        self.assertEqual(code(ends_on=None), "INVALID_SCHEDULE")
        self.assertEqual(code(ends_on=self.day0), "INVALID_SCHEDULE")
        self.assertEqual(code(counterparty=self.company_ref(self.build)), "PARTY_KIND_NOT_ALLOWED")              # inquilino residencial é jogador
        self.assertEqual(contracts.propose(self.third.pk, {**base, "proposer": self.player_ref(self.third), "counterparty": self.owner}).code,
                         "LANDLORD_NOT_OWNER")
        self.assertEqual(code(penalty_cents=3_000 * 2 + 1), "INVALID_PENALTY")                                    # limitada ao valor do contrato
        self.assertTrue(code() == "OK")

    def test_one_lease_at_a_time_per_unit_and_the_unit_must_be_free_of_other_residents(self):
        li = self.listing()
        self.assertTrue(self.rent_it(li, self.third, 1, 3).ok)
        self.assertEqual(self.rent_listing(self.u1, self.owner, self.worker).code, "UNIT_LEASED")
        direct = {"type": "rent", "role": "landlord", "proposer": self.owner, "counterparty": self.player_ref(self.boss),
                  "terms": {"lot": self.house.lot_id, "unit": 1, "amount_cents": 100}, "frequency": "daily", "starts_on": self.day0 + 1,
                  "ends_on": self.day0 + 2}
        cid = contracts.propose(self.worker.pk, direct).detail["contract"]
        res = contracts.accept(self.boss.pk, cid, self.player_ref(self.boss))
        self.assertEqual(res.code, "UNIT_LEASED")
        self.assertEqual(Tenancy.objects.count(), 1)
        self.assertTrue(housing.set_residence(self.worker.pk, self.u2.pk).ok)
        direct["terms"] = {**direct["terms"], "unit": 2}
        cid = contracts.propose(self.worker.pk, direct).detail["contract"]
        self.assertEqual(contracts.accept(self.boss.pk, cid, self.player_ref(self.boss)).code, "UNIT_OCCUPIED")

    def test_the_landlord_must_still_be_the_owner_at_acceptance(self):
        direct = {"type": "rent", "role": "landlord", "proposer": self.owner, "counterparty": self.player_ref(self.third),
                  "terms": {"lot": self.house.lot_id, "unit": 1, "amount_cents": 100}, "frequency": "daily", "starts_on": self.day0 + 1,
                  "ends_on": self.day0 + 2}
        cid = contracts.propose(self.worker.pk, direct).detail["contract"]
        li = services.list_property(self.worker.pk, self.house.lot_id, self.owner, 50_000).detail["listing"]
        self.assertTrue(services.buy_property(self.boss.pk, li, self.player_ref(self.boss)).ok)
        self.assertEqual(contracts.accept(self.third.pk, cid, self.player_ref(self.third)).code, "LANDLORD_NOT_OWNER")
        self.assertEqual(Tenancy.objects.count(), 0)

    def test_a_started_day_cannot_be_accepted(self):
        direct = {"type": "rent", "role": "landlord", "proposer": self.owner, "counterparty": self.player_ref(self.third),
                  "terms": {"lot": self.house.lot_id, "unit": 1, "amount_cents": 100}, "frequency": "daily", "starts_on": self.day0 + 1,
                  "ends_on": self.day0 + 2}
        cid = contracts.propose(self.worker.pk, direct).detail["contract"]
        self.clk.set(self.day_time(1))
        self.assertEqual(contracts.accept(self.third.pk, cid, self.player_ref(self.third)).code, "STARTS_ON_PASSED")

    def test_the_registry_offers_the_same_refusals_for_renting(self):
        li = self.listing()
        target = {"listing": li, "tenant": self.player_ref(self.third), "starts_on": self.day0 + 1, "ends_on": self.day0 + 3}
        self.assertTrue(registry.check_action(self.third.pk, "rent_unit", target).available)
        self.assertEqual(registry.check_action(self.third.pk, "rent_unit", {**target, "starts_on": self.day0}).code, "INVALID_SCHEDULE")
        self.assertEqual(registry.check_action(self.worker.pk, "rent_unit", {**target, "tenant": self.owner}).code, "SELF_RENT")
        self.assertEqual(registry.check_action(self.third.pk, "rent_unit", {**target, "tenant": self.company_ref(self.build)}).code,
                         "TENANT_MUST_BE_PLAYER")
        self.assertEqual(registry.check_action(self.third.pk, "rent_unit", {"listing": li}).code, "INVALID_PARAMS")
        res = registry.execute_action(self.third.pk, "rent_unit", target)
        self.assertTrue(res.ok, res)
        self.assertEqual(registry.check_action(self.boss.pk, "rent_unit", target).code, "RENT_LISTING_NOT_OPEN")


class ResidenceByLeaseTests(RentBase):
    def test_the_tenant_may_move_in_only_after_the_lease_begins_and_loses_the_right_when_it_ends(self):
        cid = self.rented(starts=1, ends=2)
        self.assertEqual(housing.set_residence(self.third.pk, self.u1.pk).code, "NOT_ENTITLED_TO_UNIT")        # contrato vale, ainda não começou
        self.go_day(1)
        self.assertEqual(self.worker_cannot_use_leased_unit(), "NOT_ENTITLED_TO_UNIT")
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)
        self.assertEqual(ActiveResidence.objects.get().player_id, self.third.pk)
        self.go_day(2)                                                                                           # última parcela: contrato encerra
        self.assertEqual(self.c(cid).status, "closed")
        self.assertEqual(ActiveResidence.objects.count(), 0)                                                     # volta à moradia inicial
        self.assertEqual(housing.residence_view(self.third.pk)["housing"], "initial")
        self.assertIsNone(housing.running_lease(self.u1.pk))
        self.assertTrue(housing.set_residence(self.worker.pk, self.u1.pk).ok)                                  # o dono volta a poder usar a unidade
        self.assertEqual(self.c(cid).events.filter(kind="closed").get().data["on_ended"]["residence_cleared"], True)

    def worker_cannot_use_leased_unit(self):
        return housing.set_residence(self.worker.pk, self.u1.pk).code

    def test_the_lease_qol_comes_from_the_rented_building(self):
        self.ensure_qol_provider()
        self.rented(starts=1, ends=5)
        self.go_day(1)
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)
        from players import qol
        steps = {s.key: s.amount for s in qol.qol_base(self.third, self.clk.now()).steps}
        self.assertEqual(steps[housing.PROVIDER_NAME], self.house.qol_bonus)

    def test_an_owner_cannot_move_into_a_unit_leased_to_someone_else(self):
        self.rented(starts=1, ends=5)
        self.assertEqual(housing.set_residence(self.worker.pk, self.u1.pk).code, "NOT_ENTITLED_TO_UNIT")
        self.assertTrue(housing.set_residence(self.worker.pk, self.u3.pk).ok)                                     # outras unidades seguem livres


class DefaultTests(RentBase):
    def drain(self, player):
        sink = ledger.player_account(self.boss.pk).pk
        account = ledger.player_account(player.pk).pk
        res = ledger.transfer(account, sink, ledger.available_of(account), Nature.DONATION, key=f"drain:{player.pk}:{self.clk.now()}",
                              reference_kind="t", reference_id=str(player.pk))
        self.assertTrue(res.ok, res)

    def test_an_unpaid_rent_becomes_a_debt_and_the_contract_defaults_without_ending_the_occupation(self):
        cid = self.rented(amount=10_000, starts=1, ends=5)
        self.go_day(1)                                                                                           # 1º aluguel pago
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)
        self.drain(self.third)
        self.go_day(2)
        c = self.c(cid)
        self.assertEqual(c.status, "defaulted")
        ob = Obligation.objects.get(nature="rent")
        self.assertEqual((ob.amount_due, ob.nature, ob.creditor_id, ob.debtor_id),
                         (10_000, "rent", ledger.player_account(self.worker.pk).pk, ledger.player_account(self.third.pk).pk))
        self.assertEqual(c.executions.get(sequence=1).failure_code, "INSUFFICIENT_FUNDS")
        self.assertEqual(c.executions.get(sequence=1).responsible, "b")
        self.assertEqual(ActiveResidence.objects.count(), 1)                                                     # 10 §12: não apaga a ocupação já
        self.assertEqual(Entry.objects.filter(nature=Nature.RENT.value).count(), 1)

    def test_max_failures_consecutive_unpaid_rents_break_the_contract_and_end_the_occupation(self):
        cid = self.rented(amount=10_000, starts=1, ends=9, max_failures=2, penalty=0)
        self.go_day(1)
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)
        self.drain(self.third)
        self.go_day(2)
        self.assertEqual(self.c(cid).status, "defaulted")
        self.go_day(3)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason), ("broken", "default_by_b"))
        self.assertEqual(ActiveResidence.objects.count(), 0)                                                     # despejo: volta à moradia inicial
        self.assertIsNone(housing.running_lease(self.u1.pk))
        self.assertEqual(Obligation.objects.filter(nature="rent", status="open").count(), 2)                                    # as dívidas ficam (registro global)
        self.assertTrue(self.rent_listing(self.u1, self.owner, self.worker).ok)                                 # a unidade pode ser anunciada de novo

    def test_a_later_payment_settles_the_debt_oldest_first_through_the_global_rule(self):
        cid = self.rented(amount=10_000, starts=1, ends=5)
        self.go_day(1)
        self.drain(self.third)
        self.go_day(2)
        self.assertEqual(Obligation.objects.filter(nature="rent", status="open").count(), 1)
        from ledger.tests.base import fund_account
        fund_account(ledger.player_account(self.third.pk), 500_000)
        self.go_day(3)                                                                                           # a dívida velha quita antes da nova parcela
        self.assertEqual(Obligation.objects.filter(nature="rent", status="open").count(), 0)
        self.assertEqual(self.c(cid).status, "active")

    def test_a_voluntary_break_by_the_tenant_pays_the_penalty_and_frees_the_unit(self):
        cid = self.rented(amount=10_000, starts=1, ends=9, penalty=5_000)
        self.go_day(1)
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)
        tenant, landlord = self.money(self.third), self.money(self.worker)
        res = contracts.break_contract(self.third.pk, cid, self.player_ref(self.third))
        self.assertTrue(res.ok, res)
        self.assertEqual((self.money(self.third), self.money(self.worker)), (tenant - 5_000, landlord + 5_000))
        self.assertEqual(ActiveResidence.objects.count(), 0)
        self.assertEqual(self.c(cid).status, "broken")
        self.assertEqual(Obligation.objects.filter(nature="rent").count(), 0)                                                          # aluguéis futuros não são cobrados


class SaleOfRentedPropertyTests(RentBase):
    """10 §13: a venda não apaga o contrato; o inquilino segue morando e os pagamentos futuros vão ao novo proprietário."""

    def sell_house(self, buyer):
        li = services.list_property(self.worker.pk, self.house.lot_id, self.owner, 50_000).detail["listing"]
        res = services.buy_property(buyer.pk, li, self.player_ref(buyer))
        self.assertTrue(res.ok, res)
        return res

    def test_the_lease_continues_and_the_rent_goes_to_the_new_owner(self):
        cid = self.rented(amount=10_000, starts=1, ends=5)
        self.go_day(1)
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)
        res = self.sell_house(self.boss)
        self.assertEqual(res.detail["leases_ceded"], [cid])
        c = self.c(cid)
        self.assertEqual((c.status, c.party_a_kind, c.party_a_id), ("active", "player", self.boss.pk))
        self.assertEqual(ActiveResidence.objects.get().player_id, self.third.pk)                                 # o inquilino não é despejado
        old, new = self.money(self.worker), self.money(self.boss)
        self.go_day(2)
        self.assertEqual(self.money(self.worker) - old, 0)
        last = Entry.objects.filter(nature=Nature.RENT.value).order_by("seq").last()
        self.assertEqual((last.amount, last.to_account_id), (10_000, ledger.player_account(self.boss.pk).pk))
        self.assertGreaterEqual(self.money(self.boss) - new, 10_000)                                             # (+ folha de Dono do comprador, se houver)
        self.assertEqual(ContractPartyChange.objects.get().reason, "property_sale")
        self.assertEqual(services.owner_of_lot(self.house.lot_id), (services.OwnerKind.PLAYER, self.boss.pk))

    def test_old_debts_stay_with_the_old_owner(self):
        cid = self.rented(amount=10_000, starts=1, ends=5)
        sink = ledger.player_account(self.boss.pk).pk
        account = ledger.player_account(self.third.pk).pk
        ledger.transfer(account, sink, ledger.available_of(account), Nature.DONATION, key="drain", reference_kind="t", reference_id="1")
        self.go_day(1)
        before = list(Obligation.objects.filter(nature="rent").values_list("pk", "creditor_id"))
        self.assertEqual(len(before), 1)
        self.sell_house(self.boss)
        self.assertEqual(list(Obligation.objects.filter(nature="rent").values_list("pk", "creditor_id")), before)
        self.assertEqual(before[0][1], ledger.player_account(self.worker.pk).pk)

    def test_the_sellers_residence_is_dropped_but_the_tenants_is_kept_and_open_listings_fall(self):
        self.rented(starts=1, ends=5)
        self.go_day(1)
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)
        self.assertTrue(housing.set_residence(self.worker.pk, self.u2.pk).ok)
        self.listing(self.u3)
        res = self.sell_house(self.boss)
        self.assertEqual((res.detail["residents_dropped"], res.detail["rent_listings_cancelled"]), (1, 1))
        self.assertEqual(list(ActiveResidence.objects.values_list("player_id", flat=True)), [self.third.pk])
        self.assertEqual(RentListing.objects.filter(status="cancelled", close_reason="property_sold").count(), 1)

    def test_the_tenant_buying_his_rented_property_merges_the_lease(self):
        cid = self.rented(amount=10_000, starts=1, ends=5)
        self.go_day(1)
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)
        res = self.sell_house(self.third)
        self.assertEqual(res.detail["leases_merged"], [cid])
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason, c.party_a_id), ("closed", "parties_merged", self.worker.pk))
        self.assertEqual(Entry.objects.filter(nature=Nature.PENALTY.value).count(), 0)
        self.assertEqual(list(ActiveResidence.objects.values_list("player_id", flat=True)), [])                  # o contrato acabou; ele é dono: pode morar de novo
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)

    def test_selling_with_no_leases_reports_nothing_ceded(self):
        res = self.sell_house(self.boss)
        self.assertEqual((res.detail["leases_ceded"], res.detail["leases_merged"]), ([], []))


class AuditTests(RentBase):
    audit_properties_at_end = False

    def findings(self):
        return {f["code"] for f in audit_properties().findings}

    def test_clean_with_a_lease_a_sale_and_a_listing(self):
        self.rented(starts=1, ends=5)
        self.go_day(1)
        self.assertTrue(housing.set_residence(self.third.pk, self.u1.pk).ok)
        self.listing(self.u2)
        self.assertEqual(self.findings(), set())
        stats = audit_properties().stats
        self.assertEqual((stats["tenancies"], stats["residences"]), (1, 1))

    def test_a_landlord_that_is_not_the_owner_is_found(self):
        self.rented(starts=1, ends=5)
        from properties.models import LotTitle
        LotTitle.objects.filter(lot_id=self.house.lot_id).update(owner_id=self.boss.pk)
        self.assertIn("LANDLORD_IS_NOT_THE_OWNER", self.findings())

    def test_a_resident_who_is_not_the_tenant_is_found(self):
        self.rented(starts=1, ends=5)
        ActiveResidence.objects.create(player=self.boss, unit=self.u1, since=0)
        self.assertIn("RESIDENT_NOT_THE_TENANT", self.findings())

    def test_a_tenancy_with_other_terms_is_found(self):
        self.rented(starts=1, ends=5)
        Tenancy.objects.update(unit=self.u2)
        self.assertIn("TENANCY_TERMS_MISMATCH", self.findings())

    def test_an_open_rent_listing_on_an_occupied_unit_is_found(self):
        self.listing(self.u1)
        ActiveResidence.objects.create(player=self.worker, unit=self.u1, since=0)
        self.assertIn("OPEN_RENT_LISTING_ON_OCCUPIED_UNIT", self.findings())

    def test_an_open_rent_listing_on_a_leased_unit_is_found(self):
        self.rented(starts=1, ends=5)
        RentListing.objects.create(unit=self.u1, landlord_kind="player", landlord_id=self.worker.pk, amount_cents=1, frequency="daily",
                                   listed_at=0)
        self.assertIn("OPEN_RENT_LISTING_ON_LEASED_UNIT", self.findings())
