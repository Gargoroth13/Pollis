"""
Tipos de contrato (design/18 §18.2) como HANDLERS registrados no motor: o motor (`services`) cuida de proposta, aceite, histórico,
agenda, falha, multa e quebra; o handler sabe só o que o TIPO exige (termos, papéis, o que acontece em cada ocorrência).
Aluguel (P1.07), governamental (P1.09) e militar (P1.17) entram com `register_type`, sem tocar no motor.

PROTOCOLO de trava (chamador): Jogador(es) crescente → Empresa(s) crescente → Contrato → estoque → registro monetário.
Os handlers rodam já dentro dessa ordem; nunca travam nada acima do que está travado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, FrozenSet, List, Optional, Union

from django.db import transaction

from catalog import services as catalog
from companies import stock as company_stock
from companies import trade
from companies.constants import StockOperation
from companies.models import Company, StockItem
from ledger import obligations as ledger_obligations
from ledger import services as ledger
from ledger.constants import Nature
from ledger.money import competence_day_of, percent_of
from market import recording as market_recording
from market.constants import MAX_QUANTITY, MAX_UNIT_PRICE_CENTS
from players.services import ActionResult

from . import params, schedule
from .constants import MAX_OCCURRENCES, REFERENCE_KIND, ContractType, Frequency, PartyKind, Responsible, Side
from .models import Contract


def refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


@dataclass
class Prepared:
    """Resultado da validação de uma proposta: tudo que o contrato vai guardar, já normalizado."""
    terms: Dict[str, Any]
    starts_on: Optional[int]
    ends_on: Optional[int]
    occurrences: int
    penalty_limit: int                         # multa máxima permitida pelo tipo (18.8)


@dataclass
class Outcome:
    """O que uma ocorrência produziu. Falha: código, responsável, pendências (18.6)."""
    ok: bool
    ledger_key: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)
    code: str = ""
    responsible: Optional[Responsible] = None
    pending_quantity: Optional[int] = None
    pending_cents: Optional[int] = None


class Handler:
    type: ContractType
    role_a: str = "a"
    role_b: str = "b"
    obligation_backed: bool = False            # a falha vira dívida no registro monetário e a inadimplência cessa quando ela é quitada
    kinds_a: FrozenSet[PartyKind] = frozenset({PartyKind.PLAYER, PartyKind.COMPANY})
    kinds_b: FrozenSet[PartyKind] = frozenset({PartyKind.PLAYER, PartyKind.COMPANY})

    def prepare(self, proposal: Dict[str, Any], today: int, a: tuple, b: tuple) -> Union[Prepared, ActionResult]:
        raise NotImplementedError

    def acceptance_refusal(self, contract: Contract, today: int) -> Optional[ActionResult]:
        """Recusa de aceite que só LÊ (o aceite revalida o que o tempo pode ter mudado)."""
        return None

    def anchor(self, contract: Contract, activation_day: int) -> tuple:
        """(dia âncora, dia da última ocorrência) ao entrar em vigor."""
        raise NotImplementedError

    def due_day(self, contract: Contract, sequence: int) -> int:
        raise NotImplementedError

    def activate(self, contract: Contract, at: int) -> ActionResult:
        """Efeito de entrar em vigor (já travado, em transação). Não-OK desfaz o aceite."""
        return ActionResult(True, "OK", {})

    def execute(self, contract: Contract, sequence: int, due_day: int, at: int) -> Outcome:
        raise NotImplementedError

    def on_terminated(self, contract: Contract, at: int, cause: str) -> Dict[str, Any]:
        """Ao quebrar: resolve o que restava da obrigação sem criar nem esconder dinheiro. Devolve o que foi feito (vai ao histórico)."""
        return {}

    def contract_value(self, contract: Contract) -> int:
        """Valor total do objeto (para auditoria e limite de multa)."""
        raise NotImplementedError


_HANDLERS: Dict[ContractType, Handler] = {}


def register_type(handler: Handler) -> None:
    if handler.type in _HANDLERS and _HANDLERS[handler.type] is not handler:
        raise ValueError(f"tipo de contrato já registrado: {handler.type.value}")
    _HANDLERS[handler.type] = handler


def unregister_type(type_: ContractType) -> None:
    _HANDLERS.pop(type_, None)


def get_handler(type_: Any) -> Optional[Handler]:
    try:
        return _HANDLERS.get(ContractType(type_))
    except ValueError:
        return None


def registered_types() -> List[str]:
    return sorted(t.value for t in _HANDLERS)


def account_of(kind: Union[str, PartyKind], entity_id: int) -> int:
    from market.constants import PartyKind as MarketPartyKind          # enumeração própria do mercado (mesmos valores)
    return market_recording.party_account_id(MarketPartyKind(PartyKind(kind).value), entity_id)


# --- Fornecimento (18.2) ------------------------------------------------------------------------------------------------

class SupplyHandler(Handler):
    """
    Empresa A (fornecedora) entrega `quantity` de `product` à empresa B (compradora) a `unit_price_cents` BRUTOS em cada ocorrência;
    a entrega do estoque e o pagamento são UM ato (tudo ou nada). O imposto sobre vendas é retido do pagamento (11 §11.1).
    """
    type = ContractType.SUPPLY
    role_a, role_b = "seller", "buyer"
    kinds_a = kinds_b = frozenset({PartyKind.COMPANY})

    TERM_KEYS = frozenset({"product", "quantity", "unit_price_cents"})

    def prepare(self, p, today, a, b):
        terms = p.get("terms")
        if not isinstance(terms, dict) or set(terms) != self.TERM_KEYS:
            return refuse("INVALID_TERMS", expected=sorted(self.TERM_KEYS))
        product, qty, price = terms["product"], terms["quantity"], terms["unit_price_cents"]
        if not isinstance(product, str) or catalog.get_product(product) is None:
            return refuse("UNKNOWN_PRODUCT", key=repr(product)[:40])
        if not is_int(qty) or not 0 < qty <= MAX_QUANTITY:
            return refuse("INVALID_QUANTITY", quantity=repr(qty)[:40], max=MAX_QUANTITY)
        if not is_int(price) or not 0 < price <= MAX_UNIT_PRICE_CENTS:
            return refuse("INVALID_PRICE", unit_price_cents=repr(price)[:40], max=MAX_UNIT_PRICE_CENTS)
        freq = p["frequency"]
        starts_on, ends_on = p.get("starts_on"), p.get("ends_on")
        if not is_int(starts_on) or starts_on <= today:
            return refuse("INVALID_SCHEDULE", why="starts_on deve ser um dia futuro (inteiro)", today=today)
        if freq is Frequency.ONCE:
            if ends_on not in (None, starts_on):
                return refuse("INVALID_SCHEDULE", why="frequência única: sem ends_on (ou igual a starts_on)")
            ends_on = starts_on
        elif not is_int(ends_on) or ends_on < starts_on:
            return refuse("INVALID_SCHEDULE", why="ends_on deve ser inteiro e não anterior a starts_on")
        n = schedule.count_until(starts_on, freq, ends_on)
        if n is None:
            return refuse("TOO_MANY_OCCURRENCES", max=MAX_OCCURRENCES)
        refusal = trade.purchase_refusal(b[1], product)
        if refusal is not None:
            return refusal
        return Prepared({"product": product, "quantity": qty, "unit_price_cents": price}, starts_on, ends_on, n, qty * price * n)

    def acceptance_refusal(self, contract, today):
        if contract.starts_on <= today:
            return refuse("STARTS_ON_PASSED", starts_on=contract.starts_on, today=today)
        return None

    def anchor(self, contract, activation_day):
        return contract.starts_on, schedule.shift(contract.starts_on, Frequency(contract.frequency), contract.occurrences - 1)

    def due_day(self, contract, sequence):
        return schedule.shift(contract.starts_on, Frequency(contract.frequency), sequence)

    def contract_value(self, contract):
        t = contract.terms
        return t["quantity"] * t["unit_price_cents"] * contract.occurrences

    def execute(self, contract, sequence, due_day, at):
        t = contract.terms
        qty, price, product = t["quantity"], t["unit_price_cents"], t["product"]
        gross = qty * price
        key = f"contract:{contract.pk}:exec:{sequence}"
        seller_acc, buyer_acc = account_of(contract.party_a_kind, contract.party_a_id), account_of(contract.party_b_kind, contract.party_b_id)
        pending = dict(pending_quantity=qty, pending_cents=gross)

        def fail(code, who, **detail):
            return Outcome(False, detail=detail, code=code, responsible=who, **pending)

        try:
            with transaction.atomic():
                item = StockItem.objects.filter(company_id=contract.party_a_id, product__key=product).first()
                if item is None or item.quantity < qty:
                    return fail("INSUFFICIENT_STOCK", Responsible.A, have=0 if item is None else item.quantity, required=qty)
                if ledger.available_of(buyer_acc) < gross:
                    return fail("INSUFFICIENT_FUNDS", Responsible.B, required=gross, available=ledger.available_of(buyer_acc))
                out = company_stock.debit_stock(contract.party_a_id, product, qty, operation=StockOperation.SALE,
                                                destination=f"company:{contract.party_b_id}", key=f"{key}:out",
                                                reference_kind=REFERENCE_KIND, reference_id=contract.pk, at=at)
                if not out.ok:
                    raise _Step(out.code, Responsible.A, out.detail)
                inc = company_stock.credit_stock(contract.party_b_id, product, qty, operation=StockOperation.PURCHASE,
                                                 origin=f"company:{contract.party_a_id}", key=f"{key}:in",
                                                 reference_kind=REFERENCE_KIND, reference_id=contract.pk, quality=item.quality, at=at)
                if not inc.ok:
                    raise _Step(inc.code, Responsible.B, inc.detail)
                pay = ledger.post_taxed_payment(
                    buyer_acc, seller_acc, gross, nature=Nature.SALE, tax_rate=params.SALES_TAX_RATE, key=key,
                    reference_kind=REFERENCE_KIND, reference_id=f"{contract.pk}:{sequence}", at=at, competence_day=due_day,
                    operation="contract_supply", explained_extra={"contract": contract.pk, "sequence": sequence})
                if not pay.ok:
                    raise _Step(pay.code, Responsible.B, pay.detail)
                rec = market_recording.record_sale(
                    product_key=product, quantity=qty, unit_price_cents=price, buyer_kind="company", buyer_id=contract.party_b_id,
                    seller_kind="company", seller_id=contract.party_a_id, channel="contract", ledger_key=key)
                if not rec.ok:
                    raise _Step("RECORDING_" + rec.code, Responsible.SYSTEM, rec.detail)
                return Outcome(True, ledger_key=key, detail={"quantity": qty, "gross_cents": gross, "tax_cents": pay.detail["tax"],
                                                             "net_cents": pay.detail["net"], "product": product})
        except _Step as s:
            return fail(s.code, s.responsible, **s.detail)


class _Step(Exception):
    def __init__(self, code, responsible, detail):
        self.code, self.responsible, self.detail = code, responsible, dict(detail or {})


# --- Empréstimo entre jogadores (18.2) ------------------------------------------------------------------------------------

class LoanHandler(Handler):
    """
    Jogador A (credor) entrega o principal ao jogador B (tomador) quando o contrato entra em vigor e B devolve em `installments`
    parcelas iguais (a última fecha o resto) na frequência do contrato; os juros são SIMPLES sobre o principal, divididos pelas
    parcelas. Parcela sem caixa vira obrigação pendente no registro monetário (24 §24.9), nunca saldo negativo.
    """
    type = ContractType.LOAN
    role_a, role_b = "lender", "borrower"
    kinds_a = kinds_b = frozenset({PartyKind.PLAYER})
    obligation_backed = True

    def prepare(self, p, today, a, b):
        terms = p.get("terms")
        freq = p["frequency"]
        keys = {"principal_cents", "interest_rate", "installments"} | ({"term_days"} if freq is Frequency.ONCE else set())
        if not isinstance(terms, dict) or set(terms) != keys:
            return refuse("INVALID_TERMS", expected=sorted(keys))
        principal, n = terms["principal_cents"], terms["installments"]
        if not is_int(principal) or principal <= 0 or principal > MAX_UNIT_PRICE_CENTS:
            return refuse("INVALID_AMOUNT", principal_cents=repr(principal)[:40])
        if not is_int(n) or not 1 <= n <= MAX_OCCURRENCES:
            return refuse("INVALID_TERMS", why="installments inteiro entre 1 e o limite", max=MAX_OCCURRENCES)
        rate = terms["interest_rate"]
        try:
            if isinstance(rate, (float, bool)) or not isinstance(rate, (str, int, Decimal)):
                raise InvalidOperation
            rate_d = Decimal(rate)
            if not Decimal(0) <= rate_d <= params.MAX_INTEREST_RATE or rate_d != rate_d.quantize(Decimal("0.000001")):
                raise InvalidOperation
        except InvalidOperation:
            return refuse("INVALID_INTEREST_RATE", interest_rate=repr(rate)[:40], max=str(params.MAX_INTEREST_RATE))
        norm = {"principal_cents": principal, "interest_rate": format(rate_d.quantize(Decimal("0.000001")), "f"), "installments": n}
        if freq is Frequency.ONCE:
            term_days = terms["term_days"]
            if n != 1 or not is_int(term_days) or not 1 <= term_days <= 36500:
                return refuse("INVALID_TERMS", why="frequência única: 1 parcela e term_days inteiro ≥ 1")
            norm["term_days"] = term_days
        if p.get("starts_on") is not None or p.get("ends_on") is not None:
            return refuse("INVALID_SCHEDULE", why="empréstimo não tem starts_on/ends_on: a agenda parte do aceite")
        return Prepared(norm, None, None, n, principal)

    def interest_total(self, contract) -> int:
        t = contract.terms
        return percent_of(t["principal_cents"], Decimal(t["interest_rate"]))

    def parts(self, contract, sequence: int) -> tuple:
        """(principal, juros) da parcela: iguais; a última fecha o resto (arredondamento só no fim, nada se perde)."""
        t, n = contract.terms, contract.occurrences
        total_i = self.interest_total(contract)
        p, i = t["principal_cents"] // n, total_i // n
        if sequence == n - 1:
            p, i = t["principal_cents"] - p * (n - 1), total_i - i * (n - 1)
        return p, i

    def anchor(self, contract, activation_day):
        return activation_day, self._due(contract, activation_day, contract.occurrences - 1)

    def _due(self, contract, anchor_day, sequence):
        if Frequency(contract.frequency) is Frequency.ONCE:
            return anchor_day + contract.terms["term_days"]
        return schedule.shift(anchor_day, Frequency(contract.frequency), sequence + 1)

    def due_day(self, contract, sequence):
        return self._due(contract, contract.anchor_day, sequence)

    def contract_value(self, contract):
        return contract.terms["principal_cents"]

    def activate(self, contract, at):
        t = contract.terms
        lender, borrower = account_of(contract.party_a_kind, contract.party_a_id), account_of(contract.party_b_kind, contract.party_b_id)
        res = ledger.transfer(lender, borrower, t["principal_cents"], Nature.LOAN_PRINCIPAL, key=f"contract:{contract.pk}:disburse",
                              reference_kind=REFERENCE_KIND, reference_id=contract.pk, at=at, operation="loan_disbursement",
                              explained={"contract": contract.pk, "principal_cents": t["principal_cents"]})
        if not res.ok:
            return refuse("LENDER_" + res.code if res.code == "INSUFFICIENT_FUNDS" else res.code, **res.detail)
        return ActionResult(True, "OK", {"ledger_key": f"contract:{contract.pk}:disburse", "principal_cents": t["principal_cents"]})

    def execute(self, contract, sequence, due_day, at):
        principal, interest = self.parts(contract, sequence)
        total = principal + interest
        lender, borrower = account_of(contract.party_a_kind, contract.party_a_id), account_of(contract.party_b_kind, contract.party_b_id)
        key = f"contract:{contract.pk}:exec:{sequence}"
        ref = f"{contract.pk}:{sequence}"
        if ledger.available_of(borrower) >= total:
            legs = [ledger.Leg(borrower, lender, principal, Nature.LOAN_REPAYMENT, "", "loan_installment",
                               {"contract": contract.pk, "sequence": sequence, "part": "principal"})] if principal else []
            if interest:
                legs.append(ledger.Leg(borrower, lender, interest, Nature.LOAN_INTEREST, "", "loan_installment",
                                       {"contract": contract.pk, "sequence": sequence, "part": "interest"}))
            res = ledger.post_transaction(legs, key=key, reference_kind=REFERENCE_KIND, reference_id=ref, at=at, competence_day=due_day)
            if res.ok:
                return Outcome(True, ledger_key=key, detail={"principal_cents": principal, "interest_cents": interest})
        opened = {}
        for part, amount, nature in (("principal", principal, Nature.LOAN_REPAYMENT), ("interest", interest, Nature.LOAN_INTEREST)):
            if amount <= 0:
                continue
            ob = ledger_obligations.open_obligation(borrower, lender, amount, nature, key=f"{key}:{part}", reference_kind=REFERENCE_KIND,
                                                    reference_id=f"{ref}:{part}", competence_day=due_day, at=at)
            if not ob.ok:
                raise RuntimeError(f"obrigação do contrato {contract.pk}/{sequence}: {ob.code} {ob.detail}")
            opened[part] = ob.detail.get("obligation_id")
        return Outcome(False, detail={"required": total, "obligations": opened}, code="INSUFFICIENT_FUNDS",
                       responsible=Responsible.B, pending_cents=total)

    def on_terminated(self, contract, at, cause):
        """Quebra: o principal das parcelas ainda não vencidas vira dívida imediata; os juros delas deixam de existir (não houve prazo)."""
        remaining = sum(self.parts(contract, s)[0] for s in range(contract.next_sequence, contract.occurrences))
        cancelled_interest = sum(self.parts(contract, s)[1] for s in range(contract.next_sequence, contract.occurrences))
        out = {"remaining_principal_cents": remaining, "cancelled_interest_cents": cancelled_interest}
        if remaining > 0:
            ob = ledger_obligations.open_obligation(
                account_of(contract.party_b_kind, contract.party_b_id), account_of(contract.party_a_kind, contract.party_a_id),
                remaining, Nature.LOAN_REPAYMENT, key=f"contract:{contract.pk}:remaining", reference_kind=REFERENCE_KIND,
                reference_id=f"{contract.pk}:remaining:principal", competence_day=competence_day_of(at), at=at)
            if not ob.ok:
                raise RuntimeError(f"saldo devedor do contrato {contract.pk}: {ob.code} {ob.detail}")
            out["obligation"] = ob.detail.get("obligation_id")
        return out


def register_builtin() -> None:
    register_type(SupplyHandler())
    register_type(LoanHandler())
