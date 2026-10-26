"""
Aluguel (design/10 §9-13) como TIPO do motor de contratos (design/18 §18.2; `contracts.handlers.register_type`): o motor cuida de proposta,
aceite, agenda, falha, multa, quebra e histórico; aqui vive o que o ALUGUEL exige — termos (lote + unidade + valor), a unidade presa ao
inquilino enquanto o contrato vale, o pagamento `RENT` ao proprietário VIGENTE e o anúncio de unidades.

  Contrato `rent`: A = locador (proprietário do lote: jogador ou empresa), B = inquilino (jogador). Termos: {"lot", "unit", "amount_cents"}.
  `unit` é o ÍNDICE da unidade no imóvel (1..n). Periodicidade: diária, semanal ou mensal; `starts_on` futuro e `ends_on` obrigatórios.
  Inadimplência (10 §11-12): a parcela sem caixa vira obrigação do registro monetário; `max_failures` (falhas consecutivas) é a tolerância
  antes da quebra por inadimplência, que encerra a ocupação (`on_ended`). Não existe sistema financeiro especial do aluguel.
  Venda do imóvel (10 §13): `on_property_sold` cede a posição de locador ao novo proprietário; o inquilino segue morando.

PROTOCOLO de trava: jogador(es) → empresa(s) → LOTE → contrato (a venda) | contrato → LOTE (a ativação; ninguém trava o mesmo contrato e
outro do mesmo lote em ordem inversa porque a venda só cede contratos já em vigor).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union

from django.db import transaction

from contracts import handlers, schedule
from contracts import services as contract_services
from contracts.constants import MAX_OCCURRENCES, REFERENCE_KIND, ContractType, Frequency, PartyKind, Responsible, Side
from contracts.handlers import Outcome, Prepared
from contracts.models import Contract
from core import clock as game_clock
from geography.models import Lot
from ledger import obligations as ledger_obligations
from ledger import services as ledger
from ledger.constants import Nature
from ledger.models import Entry
from market.constants import MAX_UNIT_PRICE_CENTS
from players.models import Player
from players.services import ActionResult

from . import housing
from .common import acting_player, authority, is_int, lock, parse_party, positive, refuse
from .constants import RENT_FREQUENCIES, OwnerKind, RentListingStatus
from .models import ActiveResidence, Building, RentListing, Tenancy, Unit
from .titles import owner_of_lot

TERM_KEYS = frozenset({"lot", "unit", "amount_cents"})
LISTING_KEYS = frozenset({"unit", "owner", "amount", "frequency"})
LISTING_OPTIONAL = frozenset({"penalty", "max_failures"})
RENT_KEYS = frozenset({"listing", "tenant", "starts_on", "ends_on"})
CANCEL_KEYS = frozenset({"listing", "owner"})


def _unit_of(lot_id: int, index: int) -> Optional[Unit]:
    return Unit.objects.select_related("building").filter(building__lot_id=lot_id, index=index).first()


class RentHandler(handlers.Handler):
    type = ContractType.RENT
    role_a, role_b = "landlord", "tenant"
    kinds_a = frozenset({PartyKind.PLAYER, PartyKind.COMPANY})
    kinds_b = frozenset({PartyKind.PLAYER})                              # residencial: quem mora é jogador (aluguel comercial: P1.07c)
    obligation_backed = True
    RESPONSIBILITY = {"INSUFFICIENT_FUNDS": Responsible.B}               # quem não paga é o inquilino

    def prepare(self, p, today, a, b):
        terms = p.get("terms")
        if not isinstance(terms, dict) or set(terms) != TERM_KEYS:
            return handlers.refuse("INVALID_TERMS", expected=sorted(TERM_KEYS))
        lot_id, index, amount = terms["lot"], terms["unit"], terms["amount_cents"]
        if not positive(lot_id) or not positive(index):
            return handlers.refuse("INVALID_TERMS", why="lot e unit são inteiros positivos")
        if not is_int(amount) or not 0 < amount <= MAX_UNIT_PRICE_CENTS:
            return handlers.refuse("INVALID_AMOUNT", amount_cents=repr(amount)[:40], max=MAX_UNIT_PRICE_CENTS)
        freq = p["frequency"]
        if freq.value not in RENT_FREQUENCIES:
            return handlers.refuse("INVALID_FREQUENCY", frequency=freq.value, allowed=list(RENT_FREQUENCIES))
        unit = _unit_of(lot_id, index)
        if unit is None:
            return handlers.refuse("UNIT_NOT_FOUND", lot=lot_id, unit=index)
        if owner_of_lot(lot_id) != (OwnerKind(a[0]), a[1]):
            return handlers.refuse("LANDLORD_NOT_OWNER", lot=lot_id, landlord=[a[0], a[1]])
        starts_on, ends_on = p.get("starts_on"), p.get("ends_on")
        if not is_int(starts_on) or starts_on <= today:
            return handlers.refuse("INVALID_SCHEDULE", why="starts_on deve ser um dia futuro (inteiro)", today=today)
        if not is_int(ends_on) or ends_on < starts_on:
            return handlers.refuse("INVALID_SCHEDULE", why="ends_on deve ser inteiro e não anterior a starts_on")
        n = schedule.count_until(starts_on, freq, ends_on)
        if n is None:
            return handlers.refuse("TOO_MANY_OCCURRENCES", max=MAX_OCCURRENCES)
        return Prepared({"lot": lot_id, "unit": index, "amount_cents": amount}, starts_on, ends_on, n, amount * n)

    def acceptance_refusal(self, contract, today):
        if contract.starts_on <= today:
            return handlers.refuse("STARTS_ON_PASSED", starts_on=contract.starts_on, today=today)
        return self._activation_refusal(contract)

    def _activation_refusal(self, contract) -> Optional[ActionResult]:
        t = contract.terms
        unit = _unit_of(t["lot"], t["unit"])
        if unit is None:
            return handlers.refuse("UNIT_NOT_FOUND", lot=t["lot"], unit=t["unit"])
        if owner_of_lot(t["lot"]) != (OwnerKind(contract.party_a_kind), contract.party_a_id):
            return handlers.refuse("LANDLORD_NOT_OWNER", lot=t["lot"], landlord=[contract.party_a_kind, contract.party_a_id])
        lease = housing.running_lease(unit.pk)
        if lease is not None and lease.pk != contract.pk:
            return handlers.refuse("UNIT_LEASED", unit=unit.pk, contract=lease.pk)
        resident = ActiveResidence.objects.filter(unit=unit).exclude(player_id=contract.party_b_id).first()
        if resident is not None:
            return handlers.refuse("UNIT_OCCUPIED", unit=unit.pk)
        return None

    def anchor(self, contract, activation_day):
        return contract.starts_on, schedule.shift(contract.starts_on, Frequency(contract.frequency), contract.occurrences - 1)

    def due_day(self, contract, sequence):
        return schedule.shift(contract.starts_on, Frequency(contract.frequency), sequence)

    def contract_value(self, contract):
        return contract.terms["amount_cents"] * contract.occurrences

    def activate(self, contract, at):
        """Entrar em vigor prende a unidade ao inquilino. Decide com o LOTE travado (a venda e outras ativações travam o mesmo lote)."""
        t = contract.terms
        list(Lot.objects.select_for_update().filter(pk=t["lot"]))
        refusal = self._activation_refusal(contract)
        if refusal is not None:
            return refusal
        unit = _unit_of(t["lot"], t["unit"])
        Tenancy.objects.create(contract_id=contract.pk, unit=unit, tenant_kind=contract.party_b_kind, tenant_id=contract.party_b_id,
                               created_at=at)
        return ActionResult(True, "OK", {"unit": unit.pk, "lot": t["lot"]})

    def execute(self, contract, sequence, due_day, at):
        amount = contract.terms["amount_cents"]
        landlord = handlers.account_of(contract.party_a_kind, contract.party_a_id)
        tenant = handlers.account_of(contract.party_b_kind, contract.party_b_id)
        key = f"contract:{contract.pk}:exec:{sequence}"
        ref = f"{contract.pk}:{sequence}"
        if ledger.available_of(tenant) >= amount:
            res = ledger.post_transaction(
                [ledger.Leg(tenant, landlord, amount, Nature.RENT, "rent", "rent_payment",
                            {"contract": contract.pk, "sequence": sequence, "lot": contract.terms["lot"], "unit": contract.terms["unit"]})],
                key=key, reference_kind=REFERENCE_KIND, reference_id=ref, at=at, competence_day=due_day)
            if res.ok:
                return Outcome(True, ledger_key=key, detail={"amount_cents": amount, "landlord": [contract.party_a_kind, contract.party_a_id]})
        ob = ledger_obligations.open_obligation(tenant, landlord, amount, Nature.RENT, key=f"{key}:rent", reference_kind=REFERENCE_KIND,
                                                reference_id=f"{ref}:rent", competence_day=due_day, at=at)
        if not ob.ok:
            raise RuntimeError(f"obrigação do aluguel {contract.pk}/{sequence}: {ob.code} {ob.detail}")
        return Outcome(False, detail={"required": amount, "obligation": ob.detail.get("obligation_id")}, code="INSUFFICIENT_FUNDS",
                       responsible=Responsible.B, pending_cents=amount)

    def on_ended(self, contract, at, status):
        """O contrato acabou: o inquilino perde o direito à unidade e volta à moradia inicial, se morava nela."""
        tenancy = Tenancy.objects.filter(contract_id=contract.pk).select_related("unit").first()
        if tenancy is None:
            return {}
        gone, _ = ActiveResidence.objects.filter(unit=tenancy.unit, player_id=tenancy.tenant_id).delete()
        return {"unit": tenancy.unit_id, "residence_cleared": bool(gone)}

    def audit_success(self, report, c, e, key):
        a_kind, a_id, b_kind, b_id = e.parties or c.current_parties()
        entries = list(Entry.objects.filter(transaction__key=key))
        ok = (len(entries) == 1 and entries[0].nature == Nature.RENT.value and entries[0].amount == c.terms["amount_cents"]
              and entries[0].from_account_id == handlers.account_of(b_kind, b_id) and entries[0].to_account_id == handlers.account_of(a_kind, a_id))
        if not ok:
            report.add(3, "RENT_PAYMENT_MISMATCH", contract=c.pk, sequence=e.sequence)


# --- venda do imóvel alugado (10 §13) ---------------------------------------------------------------------------------------------

def on_property_sold(lot: Lot, buyer: Tuple[OwnerKind, int], reason: str, ref: str, at: int) -> Dict[str, Any]:
    """
    Chamado pela venda do imóvel, com o lote travado: os aluguéis em vigor passam ao novo proprietário e continuam (o inquilino não é
    despejado); os anúncios de aluguel do vendedor caem; quem morava por ser o proprietário antigo volta à moradia inicial.
    """
    ceded: List[int] = []
    merged: List[int] = []
    unit_ids = list(Unit.objects.filter(building__lot=lot).values_list("pk", flat=True))
    for contract_id in sorted(Tenancy.objects.filter(unit_id__in=unit_ids).values_list("contract_id", flat=True)):
        c = Contract.objects.filter(pk=contract_id).first()
        if c is None or c.status not in ("active", "defaulted"):
            continue
        res = contract_services.reassign_party(contract_id, Side.A, (PartyKind(buyer[0].value), buyer[1]), reason=reason, ref=ref, at=at)
        if not res.ok:
            raise RuntimeError(f"cessão do aluguel {contract_id}: {res.code} {res.detail}")
        (merged if res.detail["closed"] else ceded).append(contract_id)
    cancelled = RentListing.objects.filter(unit_id__in=unit_ids, status=RentListingStatus.OPEN.value).update(
        status=RentListingStatus.CANCELLED.value, closed_at=at, close_reason="property_sold")
    dropped = housing.drop_unentitled_residents(lot.pk)
    return {"leases_ceded": ceded, "leases_merged": merged, "rent_listings_cancelled": cancelled, "residents_dropped": dropped}


# --- anúncio de aluguel (10 §9) ---------------------------------------------------------------------------------------------------

def _listing_params(target: Any, keys: frozenset, optional: frozenset = frozenset()) -> Optional[dict]:
    if not isinstance(target, dict) or not keys <= set(target) or not set(target) <= keys | optional:
        return None
    return target


def list_rent_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    p = _listing_params(target, LISTING_KEYS, LISTING_OPTIONAL)
    if p is None:
        return refuse("INVALID_PARAMS", expected=sorted(LISTING_KEYS), optional=sorted(LISTING_OPTIONAL))
    owner = parse_party(p["owner"])
    if isinstance(owner, ActionResult):
        return owner
    if not positive(p["unit"]) or not positive(p["amount"]) or p["amount"] > MAX_UNIT_PRICE_CENTS:
        return refuse("INVALID_PARAMS", unit=repr(p["unit"])[:30], amount=repr(p["amount"])[:30])
    if p["frequency"] not in RENT_FREQUENCIES:
        return refuse("INVALID_FREQUENCY", frequency=repr(p["frequency"])[:20], allowed=list(RENT_FREQUENCIES))
    penalty, max_failures = p.get("penalty", 0), p.get("max_failures")
    if not is_int(penalty) or penalty < 0:
        return refuse("INVALID_PENALTY", penalty=repr(penalty)[:30])
    if max_failures is not None and (not is_int(max_failures) or max_failures < 1):
        return refuse("INVALID_MAX_FAILURES", max_failures=repr(max_failures)[:30])
    unit = Unit.objects.select_related("building").filter(pk=p["unit"]).first()
    if unit is None:
        return refuse("UNIT_NOT_FOUND", unit=p["unit"])
    refusal = authority(actor_id, *owner)
    if refusal is not None:
        return refusal
    if owner_of_lot(unit.building.lot_id) != owner:
        return refuse("NOT_LOT_OWNER", lot=unit.building.lot_id)
    if housing.running_lease(unit.pk) is not None:
        return refuse("UNIT_LEASED", unit=unit.pk)
    if ActiveResidence.objects.filter(unit=unit).exists():
        return refuse("UNIT_OCCUPIED", unit=unit.pk)
    if RentListing.objects.filter(unit=unit, status=RentListingStatus.OPEN.value).exists():
        return refuse("ALREADY_LISTED_FOR_RENT", unit=unit.pk)
    return None


def list_rent(actor_id: Any, target: Any) -> ActionResult:
    """O proprietário anuncia uma unidade para aluguel ao valor que escolher (10 §9). Recusas: ver `list_rent_refusal`."""
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    p = _listing_params(target, LISTING_KEYS, LISTING_OPTIONAL)
    owner = parse_party(p["owner"]) if p is not None else None
    with transaction.atomic():
        lock(actor_id, [owner] if isinstance(owner, tuple) else [])
        if p is not None and positive(p["unit"]):
            lot_id = Unit.objects.filter(pk=p["unit"]).values_list("building__lot_id", flat=True).first()
            if lot_id is not None:
                list(Lot.objects.select_for_update().filter(pk=lot_id))
        refusal = list_rent_refusal(actor_id, target)
        if refusal is not None:
            return refusal
        row = RentListing.objects.create(unit_id=p["unit"], landlord_kind=owner[0].value, landlord_id=owner[1], amount_cents=p["amount"],
                                         frequency=p["frequency"], penalty_cents=p.get("penalty", 0), max_failures=p.get("max_failures"),
                                         listed_at=game_clock.now())
        return ActionResult(True, "OK", {"rent_listing": row.pk, "unit": p["unit"], "amount_cents": p["amount"], "frequency": p["frequency"]})


def unlist_rent_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    p = _listing_params(target, CANCEL_KEYS)
    if p is None or not positive(p["listing"]):
        return refuse("INVALID_PARAMS", expected=sorted(CANCEL_KEYS))
    owner = parse_party(p["owner"])
    if isinstance(owner, ActionResult):
        return owner
    row = RentListing.objects.filter(pk=p["listing"]).first()
    if row is None:
        return refuse("RENT_LISTING_NOT_FOUND", listing=p["listing"])
    refusal = authority(actor_id, *owner)
    if refusal is not None:
        return refusal
    if row.status != RentListingStatus.OPEN.value:
        return refuse("RENT_LISTING_NOT_OPEN", status=row.status)
    if (row.landlord_kind, row.landlord_id) != (owner[0].value, owner[1]):
        return refuse("NOT_SELLER", listing=row.pk)
    return None


def unlist_rent(actor_id: Any, target: Any) -> ActionResult:
    """O locador retira o anúncio de aluguel."""
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    p = _listing_params(target, CANCEL_KEYS)
    owner = parse_party(p["owner"]) if p is not None else None
    with transaction.atomic():
        lock(actor_id, [owner] if isinstance(owner, tuple) else [])
        if p is not None and positive(p["listing"]):
            list(RentListing.objects.select_for_update().filter(pk=p["listing"]))
        refusal = unlist_rent_refusal(actor_id, target)
        if refusal is not None:
            return refusal
        RentListing.objects.filter(pk=p["listing"]).update(status=RentListingStatus.CANCELLED.value, closed_at=game_clock.now(),
                                                           close_reason="withdrawn")
        return ActionResult(True, "OK", {"rent_listing": p["listing"], "status": RentListingStatus.CANCELLED.value})


def _proposal(row: RentListing, unit: Unit, tenant: Tuple[OwnerKind, int], starts_on: Any, ends_on: Any) -> Dict[str, Any]:
    proposal = {"type": "rent", "role": "landlord", "proposer": {"kind": row.landlord_kind, "id": row.landlord_id},
                "counterparty": {"kind": tenant[0].value, "id": tenant[1]},
                "terms": {"lot": unit.building.lot_id, "unit": unit.index, "amount_cents": row.amount_cents},
                "frequency": row.frequency, "starts_on": starts_on, "ends_on": ends_on, "penalty_cents": row.penalty_cents}
    if row.max_failures is not None:
        proposal["max_failures"] = row.max_failures
    return proposal


def rent_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    """Recusas de alugar pelo anúncio que só LEEM: as do anúncio e as MESMAS da proposta + aceite do contrato (`parse_proposal`/`accept_refusal`)."""
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    p = _listing_params(target, RENT_KEYS)
    if p is None or not positive(p["listing"]):
        return refuse("INVALID_PARAMS", expected=sorted(RENT_KEYS))
    tenant = parse_party(p["tenant"])
    if isinstance(tenant, ActionResult):
        return tenant
    row = RentListing.objects.filter(pk=p["listing"]).first()
    if row is None:
        return refuse("RENT_LISTING_NOT_FOUND", listing=p["listing"])
    if row.status != RentListingStatus.OPEN.value:
        return refuse("RENT_LISTING_NOT_OPEN", status=row.status)
    if tenant[0] is not OwnerKind.PLAYER:
        return refuse("TENANT_MUST_BE_PLAYER", party=[tenant[0].value, tenant[1]])
    refusal = authority(actor_id, *tenant)
    if refusal is not None:
        return refusal
    if (row.landlord_kind, row.landlord_id) == (tenant[0].value, tenant[1]):
        return refuse("SELF_RENT", listing=row.pk)
    unit = Unit.objects.select_related("building").get(pk=row.unit_id)
    if owner_of_lot(unit.building.lot_id) != (OwnerKind(row.landlord_kind), row.landlord_id):
        return refuse("LANDLORD_NOT_OWNER", lot=unit.building.lot_id)
    landlord_actor = acting_player(OwnerKind(row.landlord_kind), row.landlord_id)
    if landlord_actor is None:
        return refuse("LANDLORD_WITHOUT_OWNER", landlord=[row.landlord_kind, row.landlord_id])
    parsed = contract_services.parse_proposal(landlord_actor, _proposal(row, unit, tenant, p["starts_on"], p["ends_on"]))
    if isinstance(parsed, ActionResult):
        return parsed
    return None


def rent_unit(actor_id: Any, target: Any) -> ActionResult:
    """
    O interessado aluga a unidade anunciada nas condições do anúncio, escolhendo `starts_on`/`ends_on` (10 §9): UM ato que propõe em nome do
    locador e aceita em nome do inquilino pelo motor de contratos; se o aceite falhar nada fica. Recusas: ver `rent_refusal` e as do aceite
    (UNIT_LEASED, UNIT_OCCUPIED, LANDLORD_NOT_OWNER, ...).
    """
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    p = _listing_params(target, RENT_KEYS)
    tenant = parse_party(p["tenant"]) if p is not None else None
    with transaction.atomic():
        peek = RentListing.objects.filter(pk=p["listing"]).first() if p is not None and positive(p["listing"]) else None
        parties = [tenant] if isinstance(tenant, tuple) else []
        extra: Tuple[int, ...] = ()
        if peek is not None:
            parties.append((OwnerKind(peek.landlord_kind), peek.landlord_id))
            landlord_actor = acting_player(OwnerKind(peek.landlord_kind), peek.landlord_id)
            extra = () if landlord_actor is None else (landlord_actor,)
        lock(actor_id, parties, extra)
        if peek is not None:
            list(RentListing.objects.select_for_update().filter(pk=peek.pk))
        refusal = rent_refusal(actor_id, target)
        if refusal is not None:
            return refusal
        row = RentListing.objects.get(pk=p["listing"])
        unit = Unit.objects.select_related("building").get(pk=row.unit_id)
        landlord_actor = acting_player(OwnerKind(row.landlord_kind), row.landlord_id)
        proposed = contract_services.propose(landlord_actor, _proposal(row, unit, tenant, p["starts_on"], p["ends_on"]))
        if not proposed.ok:
            return proposed
        contract_id = proposed.detail["contract"]
        accepted = contract_services.accept(actor_id, contract_id, {"kind": tenant[0].value, "id": tenant[1]})
        if not accepted.ok or not accepted.detail.get("activated"):
            transaction.set_rollback(True)
            return accepted if not accepted.ok else refuse("NOT_ACTIVATED", contract=contract_id)
        RentListing.objects.filter(pk=row.pk).update(status=RentListingStatus.RENTED.value, closed_at=game_clock.now(),
                                                     contract_id=contract_id, close_reason="rented")
        return ActionResult(True, "OK", {"contract": contract_id, "unit": unit.pk, "lot": unit.building.lot_id, "amount_cents": row.amount_cents,
                                         "starts_on": p["starts_on"], "ends_on": p["ends_on"]})


def register() -> None:
    handlers.register_type(RentHandler())
