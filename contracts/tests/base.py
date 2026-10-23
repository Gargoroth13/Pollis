from decimal import Decimal

from companies import production, services as company_services, stock
from contracts import handlers, services
from contracts.audit import audit_contracts
from contracts.constants import ContractType, PartyKind
from contracts.models import Contract
from core import ticks
from ledger import services as ledger
from ledger.audit import ledger_metrics
from ledger.constants import Nature
from ledger.services import Leg
from market import rollup
from market.tests.base import MarketBase
from players.services import ActionResult

D = Decimal


class TestRentHandler(handlers.Handler):
    """Tipo de teste que prova o motor GENÉRICO: empresa (A) aluga a um jogador (B) por `amount_cents` por ocorrência (jogador ↔ empresa)."""
    type = ContractType.RENT
    role_a, role_b = "landlord", "tenant"
    kinds_a = frozenset({PartyKind.COMPANY})
    kinds_b = frozenset({PartyKind.PLAYER})

    def prepare(self, p, today, a, b):
        t = p["terms"]
        if not isinstance(t, dict) or set(t) != {"amount_cents"} or not isinstance(t["amount_cents"], int) or t["amount_cents"] <= 0:
            return handlers.refuse("INVALID_TERMS")
        if not isinstance(p["starts_on"], int) or p["starts_on"] <= today:
            return handlers.refuse("INVALID_SCHEDULE")
        from contracts import schedule
        n = schedule.count_until(p["starts_on"], p["frequency"], p["ends_on"] or p["starts_on"])
        return handlers.Prepared(dict(t), p["starts_on"], p["ends_on"] or p["starts_on"], n, t["amount_cents"] * n)

    def anchor(self, c, day):
        from contracts import schedule
        from contracts.constants import Frequency
        return c.starts_on, schedule.shift(c.starts_on, Frequency(c.frequency), c.occurrences - 1)

    def due_day(self, c, seq):
        from contracts import schedule
        from contracts.constants import Frequency
        return schedule.shift(c.starts_on, Frequency(c.frequency), seq)

    def contract_value(self, c):
        return c.terms["amount_cents"] * c.occurrences

    def execute(self, c, seq, due, at):
        key = f"contract:{c.pk}:exec:{seq}"
        res = ledger.transfer(handlers.account_of(c.party_b_kind, c.party_b_id), handlers.account_of(c.party_a_kind, c.party_a_id),
                              c.terms["amount_cents"], Nature.RENT, key=key, reference_kind="contract", reference_id=f"{c.pk}:{seq}", at=at)
        if res.ok:
            return handlers.Outcome(True, ledger_key=key, detail={"amount_cents": c.terms["amount_cents"]})
        from contracts.constants import Responsible
        return handlers.Outcome(False, code=res.code, responsible=Responsible.B, pending_cents=c.terms["amount_cents"])


class ContractBase(MarketBase):
    """
    Siderúrgica `firm` (Dono boss, 400 de trigo em estoque) fornece à `mill` (Moinho, Dono third, produz Farinha: trigo é insumo
    válido). Empréstimos: boss ↔ third. Ao fim de TODO teste os contratos, o mercado e o registro monetário estão íntegros.
    """

    audit_contracts_at_end = True

    def setUp(self):
        super().setUp()
        self.addCleanup(self._audit_contracts)
        self.mill = self.found(self.third, "industrial", "Moinho", 0)
        self.assertTrue(production.set_production(self.third.pk, self.mill, "flour").ok)
        self.assertTrue(company_services.fund_company(self.third.pk, self.mill, 5_000_000).ok)
        self.lender, self.borrower = self.third, self.worker          # sem salário de Dono: os saldos dos testes de empréstimo ficam exatos
        self.seller_ref = {"kind": "company", "id": self.firm}
        self.buyer_ref = {"kind": "company", "id": self.mill}

    def _audit_contracts(self):
        if self.audit_contracts_at_end:
            report = audit_contracts()
            self.assertTrue(report.ok, report.findings)

    # --- cenários -------------------------------------------------------------------------------------------------------
    def tick(self, day_offset):
        """Leva o relógio à virada do dia `day_offset` depois do de T0 (00:05) e roda os ticks do mundo."""
        self.clk.set(rollup.day_bounds(self.day0 + day_offset)[0] + 300)
        return ticks.advance_world()

    def supply_proposal(self, **over):
        p = {"type": "supply", "role": "seller", "proposer": self.seller_ref, "counterparty": self.buyer_ref,
             "terms": {"product": "wheat", "quantity": 100, "unit_price_cents": 1_000}, "frequency": "daily",
             "starts_on": self.day0 + 1, "ends_on": self.day0 + 3, "penalty_cents": 50_000}
        p.update(over)
        return p

    def propose_supply(self, actor=None, **over):
        res = services.propose((actor or self.boss).pk, self.supply_proposal(**over))
        self.assertTrue(res.ok, res)
        return res.detail["contract"]

    def active_supply(self, **over):
        cid = self.propose_supply(**over)
        res = services.accept(self.third.pk, cid, self.buyer_ref)
        self.assertTrue(res.ok, res)
        self.assertTrue(res.detail["activated"], res)
        return cid

    def loan_proposal(self, **over):
        p = {"type": "loan", "role": "lender", "proposer": {"kind": "player", "id": self.lender.pk},
             "counterparty": {"kind": "player", "id": self.borrower.pk},
             "terms": {"principal_cents": 100_000, "interest_rate": "0.02", "installments": 2}, "frequency": "daily",
             "penalty_cents": 10_000}
        p.update(over)
        return p

    def propose_loan(self, **over):
        res = services.propose(self.lender.pk, self.loan_proposal(**over))
        self.assertTrue(res.ok, res)
        return res.detail["contract"]

    def active_loan(self, **over):
        cid = self.propose_loan(**over)
        res = services.accept(self.borrower.pk, cid, {"kind": "player", "id": self.borrower.pk})
        self.assertTrue(res.ok, res)
        self.assertTrue(res.detail["activated"], res)
        return cid

    def c(self, cid):
        return Contract.objects.get(pk=cid)

    def events(self, cid):
        return [e["kind"] for e in services.contract_view(cid)["events"]]

    def company_money(self, company_id):
        return ledger.balance_of(company_services.company_account(company_id).pk)

    def circulation(self):
        return ledger_metrics()["in_circulation"]
