"""Empréstimo entre jogadores (design/18 §18.2; checklist 18.13 itens 1, 2, 4, 7-11)."""
from ledger import obligations
from ledger import services as ledger
from ledger.constants import Nature
from ledger.models import Entry, Obligation
from contracts import services
from contracts.constants import Status
from contracts.models import ContractExecution

from .base import ContractBase


class LoanTests(ContractBase):
    def drain(self, player, keep=0):
        """O jogador entrega o dinheiro (doação) a outro jogador, deixando `keep` centavos."""
        balance = ledger.balance_of(ledger.player_account(player.pk).pk)
        if balance > keep:
            res = ledger.transfer(ledger.player_account(player.pk).pk, ledger.player_account(self.boss.pk).pk, balance - keep,
                                  Nature.DONATION, key=f"drain:{player.pk}:{balance}", reference_kind="test", reference_id="1")
            self.assertTrue(res.ok, res)

    def test_the_principal_moves_when_both_accept_and_the_installments_are_paid_with_simple_interest(self):
        lender0, borrower0, money = self.money(self.lender), self.money(self.borrower), self.circulation()
        cid = self.active_loan()
        self.assertEqual((self.money(self.lender), self.money(self.borrower)), (lender0 - 100_000, borrower0 + 100_000))
        c = self.c(cid)
        self.assertEqual((c.status, c.anchor_day, c.next_due_day, c.last_due_day), (Status.ACTIVE.value, self.day0, self.day0 + 1, self.day0 + 2))
        self.tick(1)
        self.assertEqual((self.money(self.lender), self.money(self.borrower)), (lender0 - 50_000 + 1_000, borrower0 + 50_000 - 1_000))
        self.tick(2)
        self.assertEqual((self.money(self.lender), self.money(self.borrower)), (lender0 + 2_000, borrower0 - 2_000))   # 2% de juros no total
        self.assertEqual(self.circulation(), money)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason), (Status.CLOSED.value, "completed"))
        natures = [(e.nature, e.amount) for e in Entry.objects.filter(transaction__key__startswith=f"contract:{cid}:").order_by("pk")]
        self.assertEqual(natures, [("loan_principal", 100_000), ("loan_repayment", 50_000), ("loan_interest", 1_000),
                                   ("loan_repayment", 50_000), ("loan_interest", 1_000)])
        self.assertEqual(self.events(cid), ["created", "accepted", "accepted", "activated", "disbursed", "executed", "executed", "closed"])

    def test_the_last_installment_closes_the_rounding_remainder(self):
        cid = self.active_loan(terms={"principal_cents": 100_001, "interest_rate": "0.025", "installments": 3})
        handler = __import__("contracts.handlers", fromlist=["x"]).get_handler("loan")
        c = self.c(cid)
        parts = [handler.parts(c, s) for s in range(3)]
        self.assertEqual(sum(p for p, _ in parts), 100_001)
        self.assertEqual(sum(i for _, i in parts), 2_500)                  # 100.001 × 2,5% = 2.500,025 → 2.500
        self.tick(3)
        self.assertEqual(self.c(cid).status, Status.CLOSED.value)

    def test_a_single_payment_loan_pays_everything_after_term_days(self):
        cid = self.active_loan(frequency="once", terms={"principal_cents": 10_000, "interest_rate": "0.10", "installments": 1, "term_days": 5})
        self.assertEqual(self.c(cid).next_due_day, self.day0 + 5)
        lender = self.money(self.lender)
        self.tick(4)
        self.assertEqual(self.c(cid).next_sequence, 0)
        self.tick(5)
        self.assertEqual((self.money(self.lender), self.c(cid).status), (lender + 11_000, Status.CLOSED.value))

    def test_a_lender_without_the_principal_cannot_activate_and_the_acceptance_is_undone(self):
        cid = self.propose_loan(terms={"principal_cents": 10 ** 11, "interest_rate": "0", "installments": 1}, frequency="daily",
                                penalty_cents=0)
        res = services.accept(self.borrower.pk, cid, {"kind": "player", "id": self.borrower.pk})
        self.assertRefused(res, "LENDER_INSUFFICIENT_FUNDS")
        c = self.c(cid)
        self.assertEqual((c.status, c.accepted_b_at), (Status.PROPOSED.value, None))
        self.assertEqual(self.events(cid), ["created", "accepted"])

    def test_a_missed_installment_becomes_a_pending_obligation_and_the_contract_defaults(self):
        cid = self.active_loan()
        self.drain(self.borrower)
        lender = self.money(self.lender)
        self.tick(1)
        c = self.c(cid)
        e = ContractExecution.objects.get(contract=c, sequence=0)
        self.assertEqual((c.status, e.status, e.failure_code, e.responsible, e.pending_cents), (Status.DEFAULTED.value, "failed", "INSUFFICIENT_FUNDS", "b", 51_000))
        self.assertEqual(sorted((o.nature, o.amount_due, o.status) for o in Obligation.objects.filter(reference_kind="contract")),
                         [("loan_interest", 1_000, "open"), ("loan_repayment", 50_000, "open")])
        self.assertEqual(self.money(self.lender), lender)                    # nada foi pago, e nenhum dinheiro apareceu
        self.assertEqual(ledger.balance_of(ledger.player_account(self.borrower.pk).pk), 0)

    def test_the_debt_is_settled_when_cash_arrives_and_the_contract_leaves_the_default_and_closes(self):
        cid = self.active_loan()
        self.drain(self.borrower)
        self.tick(1)
        self.tick(2)                                                      # a 2ª parcela também falha: 2 obrigações por parcela
        self.assertEqual(Obligation.objects.filter(reference_kind="contract").count(), 4)
        self.assertEqual(self.c(cid).status, Status.DEFAULTED.value)
        self.fund(self.borrower, 2_000)                                      # R$ 2.000 chegam
        lender = self.money(self.lender)
        self.tick(3)
        self.assertEqual(self.money(self.lender), lender + 102_000)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason), (Status.CLOSED.value, "completed_with_failures"))
        kinds = self.events(cid)
        self.assertEqual(kinds.count("obligation_settled"), 4)
        self.assertEqual(Obligation.objects.filter(reference_kind="contract", status="open").count(), 0)

    def test_partial_cash_pays_the_oldest_debt_first_and_keeps_the_contract_in_default(self):
        cid = self.active_loan()
        self.drain(self.borrower)
        self.tick(1)
        ledger.transfer(ledger.player_account(self.boss.pk).pk, ledger.player_account(self.borrower.pk).pk, 30_000, Nature.DONATION,
                        key="small", reference_kind="test", reference_id="2")
        self.tick(2)                                                      # paga R$ 300 da parcela 1, a mais antiga; parcela 2 falha
        paid = {o.reference_id: o.amount_paid for o in Obligation.objects.filter(reference_kind="contract")}
        self.assertEqual(sum(paid.values()), 30_000)
        self.assertEqual(self.c(cid).status, Status.DEFAULTED.value)
        self.assertEqual(self.c(cid).next_sequence, 2)

    def test_a_borrower_who_breaks_pays_the_penalty_and_the_remaining_principal_becomes_a_debt_without_future_interest(self):
        cid = self.active_loan()
        self.tick(1)
        lender, borrower = self.money(self.lender), self.money(self.borrower)
        res = services.break_contract(self.borrower.pk, cid, {"kind": "player", "id": self.borrower.pk})
        self.assertTrue(res.ok, res)
        self.assertEqual((self.money(self.lender), self.money(self.borrower)), (lender + 10_000, borrower - 10_000))
        ob = Obligation.objects.get(key=f"contract:{cid}:remaining")
        self.assertEqual((ob.amount_due, ob.nature), (50_000, "loan_repayment"))
        view = services.contract_view(cid)
        cancelled = [e for e in view["events"] if e["kind"] == "remaining_cancelled"][0]["data"]
        self.assertEqual((cancelled["remaining_principal_cents"], cancelled["cancelled_interest_cents"], cancelled["occurrences_cancelled"]), (50_000, 1_000, 1))
        self.assertEqual(view["status"], "broken")
        self.tick(2)                                                      # a dívida é cobrada pela quitação diária
        self.assertEqual(Obligation.objects.get(pk=ob.pk).status, "paid")
        self.assertIn("obligation_settled", self.events(cid))

    def test_the_lender_can_also_break_and_pays_the_penalty_to_the_borrower(self):
        cid = self.active_loan()
        lender, borrower = self.money(self.lender), self.money(self.borrower)
        self.assertTrue(services.break_contract(self.lender.pk, cid, {"kind": "player", "id": self.lender.pk}).ok)
        self.assertEqual((self.money(self.lender), self.money(self.borrower)), (lender - 10_000, borrower + 10_000))
        self.assertEqual(self.c(cid).end_reason, "voluntary_break_by_a")

    def test_loan_terms_are_validated(self):
        p = self.lender.pk
        for terms, code in (({"principal_cents": 0, "interest_rate": "0.02", "installments": 2}, "INVALID_AMOUNT"),
                            ({"principal_cents": 1000, "interest_rate": 0.02, "installments": 2}, "INVALID_INTEREST_RATE"),
                            ({"principal_cents": 1000, "interest_rate": "1.5", "installments": 2}, "INVALID_INTEREST_RATE"),
                            ({"principal_cents": 1000, "interest_rate": "0.0000001", "installments": 2}, "INVALID_INTEREST_RATE"),
                            ({"principal_cents": 1000, "interest_rate": "0.02", "installments": 0}, "INVALID_TERMS"),
                            ({"principal_cents": 1000, "interest_rate": "0.02"}, "INVALID_TERMS")):
            self.assertRefused(services.propose(p, self.loan_proposal(terms=terms)), code)
        self.assertRefused(services.propose(p, self.loan_proposal(frequency="once")), "INVALID_TERMS")                  # once exige term_days e 1 parcela
        self.assertRefused(services.propose(p, self.loan_proposal(starts_on=self.day0 + 3)), "INVALID_SCHEDULE")
        self.assertRefused(services.propose(p, self.loan_proposal(penalty_cents=100_001)), "INVALID_PENALTY")           # multa ≤ principal
        self.assertRefused(services.propose(p, self.loan_proposal(proposer={"kind": "company", "id": self.firm})), "PARTY_KIND_NOT_ALLOWED")
