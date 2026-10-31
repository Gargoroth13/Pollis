"""Criação, aceite das duas partes, permissões, recusa/retirada e validação das propostas (design/18 §18.1, §18.4; checklist 1-2)."""
from contracts import handlers, services
from contracts.constants import ContractType, Status
from contracts.models import Contract, ContractExecution
from players import registry

from .base import ContractBase, TestRentHandler


class CreationAndAcceptanceTests(ContractBase):
    def setUp(self):
        super().setUp()
        handlers.register_type(TestRentHandler())
        self.addCleanup(handlers.unregister_type, ContractType.RENT)

    def test_contracts_are_created_between_player_and_player_player_and_company_and_company_and_company(self):
        loan = self.propose_loan()                                                                       # jogador ↔ jogador
        supply = self.propose_supply()                                                                   # empresa ↔ empresa
        rent = services.propose(self.boss.pk, {"type": "rent", "role": "landlord", "proposer": self.seller_ref,   # empresa ↔ jogador
                                               "counterparty": {"kind": "player", "id": self.worker.pk}, "terms": {"amount_cents": 500},
                                               "frequency": "daily", "starts_on": self.day0 + 1, "ends_on": self.day0 + 2})
        self.assertTrue(rent.ok, rent)
        kinds = {(c.party_a_kind, c.party_b_kind) for c in Contract.objects.all()}
        self.assertEqual(kinds, {("player", "player"), ("company", "company"), ("company", "player")})
        for cid in (loan, supply, rent.detail["contract"]):
            self.assertEqual(self.c(cid).status, Status.PROPOSED.value)

    def test_the_generic_engine_runs_a_player_company_contract_end_to_end(self):
        res = services.propose(self.boss.pk, {"type": "rent", "role": "landlord", "proposer": self.seller_ref,
                                              "counterparty": {"kind": "player", "id": self.worker.pk}, "terms": {"amount_cents": 500},
                                              "frequency": "daily", "starts_on": self.day0 + 1, "ends_on": self.day0 + 2})
        cid = res.detail["contract"]
        self.assertTrue(services.accept(self.worker.pk, cid, {"kind": "player", "id": self.worker.pk}).ok)
        tenant, landlord = self.money(self.worker), self.company_money(self.firm)
        self.tick(2)
        self.assertEqual((self.money(self.worker), self.c(cid).status), (tenant - 1_000, Status.CLOSED.value))
        self.assertEqual(self.company_money(self.firm) - landlord, 1_000 - 2_000 * 2)                    # + aluguéis − folha do Dono (2 dias)

    def test_nothing_runs_before_both_parties_accept_and_the_proposer_has_already_accepted(self):
        cid = self.propose_supply(starts_on=self.day0 + 5, ends_on=self.day0 + 6)
        c = self.c(cid)
        self.assertEqual((c.accepted_a_at is not None, c.accepted_b_at, c.next_due_day), (True, None, None))
        self.tick(2)
        self.assertEqual(ContractExecution.objects.count(), 0)
        self.assertEqual(self.c(cid).status, Status.PROPOSED.value)

    def test_only_the_owner_acts_for_a_company_and_only_the_player_for_himself(self):
        cid = self.propose_supply()
        self.assertRefused(services.accept(self.worker.pk, cid, self.buyer_ref), "NOT_OWNER")
        self.assertRefused(services.accept(self.boss.pk, cid, self.seller_ref), "ALREADY_ACCEPTED")
        self.assertRefused(services.accept(self.third.pk, cid, {"kind": "company", "id": 10 ** 6}), "NOT_A_PARTY")
        self.assertRefused(services.accept(self.third.pk, 10 ** 9, self.buyer_ref), "CONTRACT_NOT_FOUND")
        self.assertRefused(services.accept(self.third.pk, cid, "x"), "INVALID_PARTY")
        loan = self.propose_loan()
        self.assertRefused(services.accept(self.boss.pk, loan, {"kind": "player", "id": self.borrower.pk}), "NOT_PARTY_REPRESENTATIVE")
        self.assertRefused(services.accept(10 ** 9, loan, {"kind": "player", "id": self.borrower.pk}), "PLAYER_NOT_FOUND")
        self.assertRefused(services.propose(self.worker.pk, self.supply_proposal()), "NOT_OWNER")        # só o Dono propõe pela empresa
        self.assertRefused(services.propose(self.boss.pk, self.loan_proposal()), "NOT_PARTY_REPRESENTATIVE")

    def test_the_second_acceptance_activates_and_a_third_is_refused(self):
        cid = self.active_supply()
        c = self.c(cid)
        self.assertEqual((c.status, c.next_due_day, c.anchor_day), (Status.ACTIVE.value, self.day0 + 1, self.day0 + 1))
        self.assertRefused(services.accept(self.third.pk, cid, self.buyer_ref), "NOT_PROPOSED")

    def test_the_counterparty_declines_and_the_proposer_withdraws_and_neither_can_be_accepted_later(self):
        a, b = self.propose_supply(), self.propose_supply()
        self.assertRefused(services.decline(self.boss.pk, a, self.seller_ref), "IS_PROPOSER")
        self.assertRefused(services.withdraw(self.third.pk, a, self.buyer_ref), "NOT_PROPOSER")
        self.assertTrue(services.decline(self.third.pk, a, self.buyer_ref).ok)
        self.assertTrue(services.withdraw(self.boss.pk, b, self.seller_ref).ok)
        self.assertEqual((self.c(a).end_reason, self.c(b).end_reason), ("declined_by_b", "withdrawn"))
        for cid in (a, b):
            self.assertRefused(services.accept(self.third.pk, cid, self.buyer_ref), "NOT_PROPOSED")
            self.assertEqual(self.c(cid).status, Status.CANCELLED.value)
        self.assertEqual(self.events(a), ["created", "accepted", "declined"])

    def test_a_proposal_whose_start_has_passed_cannot_be_accepted_and_is_cancelled_by_the_daily_tick(self):
        cid = self.propose_supply(starts_on=self.day0 + 1, ends_on=self.day0 + 2)
        self.clk.set(self.at(1, 0, 1))
        self.assertRefused(services.accept(self.third.pk, cid, self.buyer_ref), "STARTS_ON_PASSED")
        self.tick(1)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason), (Status.CANCELLED.value, "expired"))

    def test_the_terms_are_frozen_and_sealed_by_a_hash_the_audit_checks(self):
        cid = self.propose_supply()
        sealed = self.c(cid).terms_hash
        self.assertTrue(services.accept(self.third.pk, cid, self.buyer_ref).ok)
        self.assertEqual(self.c(cid).terms_hash, sealed)
        self.assertEqual(self.c(cid).frozen_digest(), sealed)


class ProposalValidationTests(ContractBase):
    def refused(self, code, proposer=None, **over):
        res = services.propose((proposer or self.boss).pk, self.supply_proposal(**over))
        self.assertRefused(res, code)
        self.assertEqual(Contract.objects.count(), 0, res)

    def test_the_proposal_shape_type_role_and_parties_are_checked(self):
        self.assertRefused(services.propose(self.boss.pk, "x"), "INVALID_PARAMS")
        self.assertRefused(services.propose(self.boss.pk, {"type": "supply"}), "INVALID_PARAMS")
        self.assertRefused(services.propose(10 ** 9, self.supply_proposal()), "PLAYER_NOT_FOUND")
        self.refused("INVALID_PARAMS", extra=1)
        self.refused("TYPE_NOT_AVAILABLE", type="government")
        self.refused("TYPE_NOT_AVAILABLE", type="rent")                       # sem handler registrado (P1.07)
        self.refused("TYPE_NOT_AVAILABLE", type="nope")
        self.refused("INVALID_ROLE", role="lender")
        self.refused("INVALID_PARTY", counterparty={"kind": "company"})
        self.refused("INVALID_PARTY", counterparty={"kind": "state", "id": 1})
        self.refused("SAME_PARTY", counterparty=self.seller_ref)
        self.refused("PARTY_NOT_FOUND", counterparty={"kind": "company", "id": 10 ** 6})
        self.refused("PARTY_KIND_NOT_ALLOWED", counterparty={"kind": "player", "id": self.worker.pk})
        self.refused("INVALID_FREQUENCY", frequency="yearly")

    def test_supply_terms_schedule_penalty_and_the_buyer_s_use_for_the_product_are_checked(self):
        t = {"product": "wheat", "quantity": 100, "unit_price_cents": 1_000}
        self.refused("INVALID_TERMS", terms={**t, "x": 1})
        self.refused("INVALID_TERMS", terms="x")
        self.refused("UNKNOWN_PRODUCT", terms={**t, "product": "nothing"})
        self.refused("INVALID_QUANTITY", terms={**t, "quantity": 0})
        self.refused("INVALID_QUANTITY", terms={**t, "quantity": True})
        self.refused("INVALID_PRICE", terms={**t, "unit_price_cents": -1})
        self.refused("INVALID_PRICE", terms={**t, "unit_price_cents": 1.5})
        self.refused("INVALID_SCHEDULE", starts_on=self.day0)                                             # hoje não: a execução é à virada do dia
        self.refused("INVALID_SCHEDULE", starts_on=None)
        self.refused("INVALID_SCHEDULE", ends_on=self.day0)
        self.refused("INVALID_SCHEDULE", frequency="once", ends_on=self.day0 + 9)
        self.refused("TOO_MANY_OCCURRENCES", ends_on=self.day0 + 5_000)
        self.refused("INVALID_PENALTY", penalty_cents=-1)
        self.refused("INVALID_PENALTY", penalty_cents=100 * 1_000 * 3 + 1)                                # > valor total do contrato
        self.refused("INVALID_PENALTY", penalty_cents=True)
        self.refused("INVALID_MAX_FAILURES", max_failures=0)
        retail = self.found(self.third, "retail", "Loja", 0)
        self.refused("NO_VALID_USE", counterparty={"kind": "company", "id": retail})                      # comprador sem uso para o produto
        self.refused("PRODUCT_NOT_TRADABLE_BETWEEN_COMPANIES", terms={**t, "product": "military_weapons"})

    def test_a_valid_proposal_with_zero_penalty_and_no_failure_condition_is_accepted(self):
        res = services.propose(self.boss.pk, self.supply_proposal(penalty_cents=0, max_failures=None))
        self.assertTrue(res.ok, res)
        self.assertEqual(self.c(res.detail["contract"]).occurrences, 3)


class RegistryTests(ContractBase):
    def test_the_actions_exist_with_stable_descriptors(self):
        ids = {d.id: d for d in registry.list_descriptors()}
        for action in ("propose_contract", "accept_contract", "decline_contract", "withdraw_contract", "break_contract"):
            self.assertEqual(ids[action].target, registry.TargetSpec(registry.TARGET_PARAMS, True), action)

    def test_the_whole_flow_runs_through_the_registry_like_for_a_bot(self):
        proposed = registry.execute_action(self.boss.pk, "propose_contract", self.supply_proposal())
        self.assertTrue(proposed.ok, proposed)
        later = self.supply_proposal(starts_on=self.day0 + 9, ends_on=self.day0 + 10)
        other = registry.execute_action(self.boss.pk, "propose_contract", later)
        third = registry.execute_action(self.boss.pk, "propose_contract", later)
        cid = proposed.detail["contract"]
        accepted = registry.execute_action(self.third.pk, "accept_contract", {"contract": cid, "party": self.buyer_ref})
        self.assertTrue(accepted.ok and accepted.detail["activated"], accepted)
        self.tick(1)
        self.assertEqual(self.c(cid).next_sequence, 1)
        broken = registry.execute_action(self.third.pk, "break_contract", {"contract": cid, "party": self.buyer_ref})
        self.assertTrue(broken.ok, broken)
        self.assertTrue(registry.execute_action(self.boss.pk, "withdraw_contract",
                                                {"contract": other.detail["contract"], "party": self.seller_ref}).ok)
        self.assertTrue(registry.execute_action(self.third.pk, "decline_contract",
                                                {"contract": third.detail["contract"], "party": self.buyer_ref}).ok)

    def test_availability_and_execution_give_the_same_refusal(self):
        cid = self.propose_supply()
        cases = (
            (self.worker, "propose_contract", self.supply_proposal(), "NOT_OWNER"),
            (self.boss, "propose_contract", self.supply_proposal(terms={"product": "nothing", "quantity": 1, "unit_price_cents": 1}), "UNKNOWN_PRODUCT"),
            (self.worker, "accept_contract", {"contract": cid, "party": self.buyer_ref}, "NOT_OWNER"),
            (self.boss, "accept_contract", {"contract": cid, "party": self.seller_ref}, "ALREADY_ACCEPTED"),
            (self.third, "accept_contract", {"contract": 10 ** 9, "party": self.buyer_ref}, "CONTRACT_NOT_FOUND"),
            (self.third, "decline_contract", {"contract": cid, "party": self.seller_ref}, "NOT_OWNER"),
            (self.boss, "decline_contract", {"contract": cid, "party": self.seller_ref}, "IS_PROPOSER"),
            (self.third, "withdraw_contract", {"contract": cid, "party": self.buyer_ref}, "NOT_PROPOSER"),
            (self.boss, "break_contract", {"contract": cid, "party": self.seller_ref}, "NOT_RUNNING"),
        )
        for player, action, target, code in cases:
            check = registry.check_action(player.pk, action, target)
            run = registry.execute_action(player.pk, action, target)
            self.assertEqual((check.available, check.code, run.ok, run.code), (False, code, False, code), (action, code))

    def test_invalid_targets_are_invalid_params_and_a_target_is_required(self):
        for action, bad in (("accept_contract", {"contract": 1}), ("break_contract", {"contract": 1, "party": {}, "x": 1}),
                            ("decline_contract", "x"), ("propose_contract", {"type": "supply"})):
            self.assertEqual(registry.execute_action(self.boss.pk, action, bad).code, "INVALID_PARAMS", (action, bad))
            self.assertEqual(registry.check_action(self.boss.pk, action, bad).code, "INVALID_PARAMS", (action, bad))
        self.assertEqual(registry.execute_action(self.boss.pk, "accept_contract").code, "TARGET_REQUIRED")

    def test_the_preview_shows_what_the_player_needs_before_acting(self):
        cid = self.propose_supply()
        check = registry.check_action(self.third.pk, "accept_contract", {"contract": cid, "party": self.buyer_ref})
        self.assertTrue(check.available, check)
        self.assertEqual(check.preview["contract"]["terms"]["quantity"], 100)
        proposal = registry.check_action(self.boss.pk, "propose_contract", self.supply_proposal())
        self.assertEqual((proposal.preview["occurrences"], proposal.preview["role_a"]), (3, "seller"))
