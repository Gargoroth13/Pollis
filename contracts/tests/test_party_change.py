"""Cessão de parte (10 §13: a venda do imóvel alugado não apaga o contrato) e gancho de fim de contrato."""
from contracts import handlers, services
from contracts.audit import audit_contracts
from contracts.constants import ContractType, EventKind, PartyKind, Side, Status
from contracts.models import Contract, ContractEvent, ContractPartyChange, ContractsImmutableError
from ledger.models import Entry
from ledger.constants import Nature

from .base import ContractBase, TestRentHandler


class EndedProbe(TestRentHandler):
    """O tipo de teste que também anota os fins de contrato."""
    ended = []

    def on_ended(self, contract, at, status):
        type(self).ended.append((contract.pk, status))
        return {"probe": True}


class PartyChangeBase(ContractBase):
    def setUp(self):
        super().setUp()
        EndedProbe.ended = []
        real = handlers.get_handler(ContractType.RENT)               # o aluguel real vive em `properties`: troca pelo tipo de teste e devolve
        handlers.unregister_type(ContractType.RENT)
        handlers.register_type(EndedProbe())
        self.addCleanup(lambda: (handlers.unregister_type(ContractType.RENT), real is None or handlers.register_type(real)))
        self.landlord2 = self.found(self.third, "industrial", "Locadora 2", 0)
        self.tenant = {"kind": "player", "id": self.worker.pk}

    def rent(self, days=3, **over):
        p = {"type": "rent", "role": "landlord", "proposer": self.seller_ref, "counterparty": self.tenant, "terms": {"amount_cents": 500},
             "frequency": "daily", "starts_on": self.day0 + 1, "ends_on": self.day0 + days}
        p.update(over)
        res = services.propose(self.boss.pk, p)
        self.assertTrue(res.ok, res)
        cid = res.detail["contract"]
        self.assertTrue(services.accept(self.worker.pk, cid, self.tenant).ok)
        return cid

    def cede(self, cid, to, side=Side.A, reason="test"):
        return services.reassign_party(cid, side, (PartyKind.COMPANY, to), reason=reason, ref="t:1")

    def audit_ok(self):
        report = audit_contracts()
        self.assertTrue(report.ok, report.findings)


class ReassignTests(PartyChangeBase):
    def test_the_next_occurrences_are_paid_to_the_new_party_and_the_history_keeps_both(self):
        cid = self.rent()
        self.tick(1)                                                                      # 1ª ocorrência: paga a Siderúrgica
        first = self.company_money(self.firm)
        res = self.cede(cid, self.landlord2)
        self.assertTrue(res.ok, res)
        self.assertEqual((res.detail["closed"], res.detail["sequence"]), (False, 1))
        c = self.c(cid)
        self.assertEqual((c.party_a_kind, c.party_a_id, c.status), ("company", self.landlord2, "active"))
        self.assertEqual(c.sealed_parties, ["company", self.firm, "player", self.worker.pk])        # o selo guarda quem contratou
        mine = self.company_money(self.landlord2)
        self.tick(2)
        self.assertEqual(self.company_money(self.landlord2) - mine, 500)
        self.assertEqual(self.company_money(self.firm), first - 2_000)                    # só a folha do Dono da Siderúrgica no dia 2
        executions = list(c.executions.order_by("sequence"))
        self.assertEqual([e.parties[1] for e in executions], [self.firm, self.landlord2])
        change = ContractPartyChange.objects.get()
        self.assertEqual((change.seq, change.side, change.from_id, change.to_id, change.reason, change.ref),
                         (1, "a", self.firm, self.landlord2, "test", "t:1"))
        self.assertEqual([e["kind"] for e in services.contract_view(cid)["events"]].count("party_changed"), 1)
        self.audit_ok()

    def test_the_seal_of_the_terms_still_holds_and_nobody_edits_the_party_outside_the_service(self):
        cid = self.rent()
        self.assertTrue(self.cede(cid, self.landlord2).ok)
        c = self.c(cid)
        self.assertEqual(c.terms_hash, c.frozen_digest())
        c.party_a_id = self.firm
        with self.assertRaises(ContractsImmutableError):
            c.save()
        c = self.c(cid)
        c.terms = {"amount_cents": 1}
        with self.assertRaises(ContractsImmutableError):
            c.save()
        with self.assertRaises(ContractsImmutableError):
            ContractPartyChange.objects.get().delete()

    def test_refusals(self):
        cid = self.rent()
        self.assertEqual(services.reassign_party(10 ** 9, Side.A, (PartyKind.COMPANY, 1), reason="t", ref="x").code, "CONTRACT_NOT_FOUND")
        self.assertEqual(services.reassign_party(cid, Side.A, (PartyKind.PLAYER, self.third.pk), reason="t", ref="x").code, "PARTY_KIND_NOT_ALLOWED")
        self.assertEqual(self.cede(cid, 10 ** 9).code, "PARTY_NOT_FOUND")
        self.assertEqual(self.cede(cid, self.firm).code, "SAME_PARTY_CHANGE")
        proposed = services.propose(self.boss.pk, {"type": "rent", "role": "landlord", "proposer": self.seller_ref, "counterparty": self.tenant,
                                                   "terms": {"amount_cents": 500}, "frequency": "daily", "starts_on": self.day0 + 1,
                                                   "ends_on": self.day0 + 2}).detail["contract"]
        self.assertEqual(self.cede(proposed, self.landlord2).code, "NOT_RUNNING")             # só contrato em vigor
        self.assertEqual(ContractPartyChange.objects.count(), 0)

    def test_the_new_party_can_break_and_the_old_one_no_longer_can(self):
        cid = self.rent(days=5)
        self.assertTrue(self.cede(cid, self.landlord2).ok)
        self.assertEqual(services.break_contract(self.boss.pk, cid, self.seller_ref).code, "NOT_A_PARTY")
        res = services.break_contract(self.third.pk, cid, {"kind": "company", "id": self.landlord2})
        self.assertTrue(res.ok, res)
        self.assertEqual(self.c(cid).status, "broken")
        self.audit_ok()

    def test_two_successive_cessions_chain_and_audit(self):
        cid = self.rent()
        third_company = self.found(self.boss, "industrial", "Locadora 3", 0)
        self.assertTrue(self.cede(cid, self.landlord2).ok)
        self.assertTrue(self.cede(cid, third_company).ok)
        self.assertEqual([(x.seq, x.from_id, x.to_id) for x in ContractPartyChange.objects.order_by("seq")],
                         [(1, self.firm, self.landlord2), (2, self.landlord2, third_company)])
        self.assertEqual(self.c(cid).party_a_id, third_company)
        self.audit_ok()

    def test_old_debts_stay_with_the_party_they_were_owed_to(self):
        loan = self.active_loan(terms={"principal_cents": 100_000, "interest_rate": "0.02", "installments": 2})
        from ledger import services as ledger
        self.assertTrue(ledger.transfer(ledger.player_account(self.borrower.pk).pk, ledger.player_account(self.boss.pk).pk,
                                        ledger.available_of(ledger.player_account(self.borrower.pk).pk), Nature.DONATION, key="drain",
                                        reference_kind="t", reference_id="1").ok)
        self.tick(1)                                                                      # a 1ª parcela falha: vira obrigação do credor de então
        from ledger.models import Obligation
        before = list(Obligation.objects.values_list("pk", "creditor_id"))
        self.assertTrue(before)
        res = services.reassign_party(loan, Side.A, (PartyKind.PLAYER, self.boss.pk), reason="t", ref="t:2")
        self.assertTrue(res.ok, res)
        self.assertEqual(list(Obligation.objects.values_list("pk", "creditor_id")), before)
        self.audit_ok()


class MergeTests(PartyChangeBase):
    def test_a_party_that_becomes_the_counterparty_closes_the_contract_without_penalty(self):
        cid = self.propose_supply(penalty_cents=50_000)
        self.assertTrue(services.accept(self.third.pk, cid, self.buyer_ref).ok)
        circulation = self.circulation()
        res = self.cede(cid, self.mill)                                                  # o vendedor passa a ser o próprio comprador
        self.assertTrue(res.ok, res)
        self.assertTrue(res.detail["closed"])
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason, c.party_a_id), ("closed", "parties_merged", self.firm))
        self.assertEqual(Entry.objects.filter(nature=Nature.PENALTY.value).count(), 0)
        self.assertEqual(self.circulation(), circulation)
        self.assertEqual(ContractPartyChange.objects.count(), 0)
        closed = ContractEvent.objects.get(contract=c, kind=EventKind.CLOSED.value)
        self.assertEqual(closed.data["merged_into"], ["company", self.mill])
        self.tick(2)
        self.assertEqual(c.executions.count(), 0)                                        # nada mais roda
        self.audit_ok()


class EndedHookTests(PartyChangeBase):
    def test_the_type_is_told_when_the_contract_closes_or_breaks(self):
        done = self.rent(days=1)
        self.tick(1)
        self.assertEqual(self.c(done).status, "closed")
        broken = self.rent(starts_on=self.day0 + 3, ends_on=self.day0 + 7)
        self.assertTrue(services.break_contract(self.worker.pk, broken, self.tenant).ok)
        self.assertEqual(sorted(EndedProbe.ended), sorted([(done, "closed"), (broken, "broken")]))
        event = ContractEvent.objects.get(contract_id=broken, kind=EventKind.BROKEN.value)
        self.assertEqual(event.data["on_ended"], {"probe": True})
        self.audit_ok()
