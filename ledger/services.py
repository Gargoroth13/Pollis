"""
Serviços do registro monetário (design/24): ÚNICO ponto de entrada para mover dinheiro.

Jogadores, bots, sistemas e governos usam estas mesmas funções (CLAUDE.md §5.4). Cada operação:
  1. valida valor (centavos inteiros), naturezas e rotas (SINK só recebe; só SCENARIO_GRANT emite...);
  2. abre transação de banco e trava as contas em ORDEM CRESCENTE DE ID (sem deadlock);
  3. aplica as pernas em sequência, sem saldo negativo (disponível = bruto − reservas ativas);
  4. grava lançamentos imutáveis com saldos antes/depois, referência e `Explained`;
  5. devolve `ActionResult` (recusa é CÓDIGO, nunca exceção) — a mesma chave de idempotência devolve o resultado original.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from django.db import IntegrityError, transaction
from django.db.models import Sum

from core import clock as game_clock
from core.breakdown import Calc, Explained
from players.services import ActionResult

from .constants import (MAX_AMOUNT, OPERATIONAL_KINDS, REMUNERATION_NATURES, RETENTION_IN_NATURES,
                        RETENTION_OUT_NATURES, SINGLETON_KINDS, SINK_NATURES, TAX_NATURES, AccountKind, HoldStatus,
                        Nature, ObligationStatus)
from .models import (Account, Entry, Hold, LedgerScenario, Obligation, ScenarioGrantLine, Transaction)
from .money import amount_problem, competence_day_of, is_centavos, percent_of


class _Refuse(Exception):
    """Interna: aborta a transação de banco devolvendo uma recusa estruturada."""

    def __init__(self, result: ActionResult):
        self.result = result


class LedgerRefusal(Exception):
    """Recusa de infraestrutura (conta de dono inexistente...) em funções que devolvem objetos, não `ActionResult`."""

    def __init__(self, result: ActionResult):
        self.result = result
        super().__init__(f"{result.code}: {result.detail}")


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def _fail(code: str, **detail):
    raise _Refuse(_refuse(code, **detail))


# --- contas -------------------------------------------------------------------------------------------------------------

def _owner_problem(kind: AccountKind, owner_id: int, owner_ref: str) -> Optional[ActionResult]:
    if kind in SINGLETON_KINDS:
        return None if owner_id == 0 and not owner_ref else _refuse("ACCOUNT_OWNER_INVALID", kind=kind.value)
    if kind == AccountKind.RETENTION:
        return None if owner_id == 0 and owner_ref else _refuse("ACCOUNT_OWNER_INVALID", kind=kind.value)
    if owner_ref or not isinstance(owner_id, int) or owner_id <= 0:
        return _refuse("ACCOUNT_OWNER_INVALID", kind=kind.value, owner_id=owner_id)
    # Só os donos que JÁ existem são validados; Empresas e milícias validam no app dono (design/24 §24.3.2).
    if kind == AccountKind.PLAYER:
        from players.models import Player
        exists = Player.objects.filter(pk=owner_id).exists()
    elif kind == AccountKind.STATE:
        from geography.models import State
        exists = State.objects.filter(pk=owner_id).exists()
    elif kind == AccountKind.MUNICIPALITY:
        from geography.models import City
        exists = City.objects.filter(pk=owner_id).exists()
    else:
        exists = True
    return None if exists else _refuse("ACCOUNT_OWNER_NOT_FOUND", kind=kind.value, owner_id=owner_id)


def get_or_create_account(kind: AccountKind, owner_id: int = 0, owner_ref: str = "", purpose: str = "") -> Account:
    """Conta de `(tipo, dono)`; cria se não existe (idempotente). `LedgerRefusal` se o dono é inválido."""
    kind = AccountKind(kind)
    problem = _owner_problem(kind, owner_id, owner_ref)
    if problem is not None:
        raise LedgerRefusal(problem)
    account, _ = Account.objects.get_or_create(kind=kind.value, owner_id=owner_id, owner_ref=owner_ref,
                                               defaults={"purpose": purpose, "created_at": game_clock.now()})
    return account


def player_account(player_id: int) -> Account:
    return get_or_create_account(AccountKind.PLAYER, player_id)


def union_account() -> Account:
    return get_or_create_account(AccountKind.UNION)


def sink_account() -> Account:
    return get_or_create_account(AccountKind.SINK)


def issuance_account() -> Account:
    return get_or_create_account(AccountKind.ISSUANCE)


def close_account(account_id: int) -> ActionResult:
    """Encerra a conta (nunca a exclui). Exige saldo zero, sem reservas ativas e que não seja singleton."""
    with transaction.atomic():
        account = Account.objects.select_for_update().filter(pk=account_id).first()
        if account is None:
            return _refuse("ACCOUNT_NOT_FOUND", account=account_id)
        if AccountKind(account.kind) in SINGLETON_KINDS:
            return _refuse("ACCOUNT_NOT_CLOSABLE", account=account_id)
        if account.balance != 0 or reserved_of(account_id) != 0:
            return _refuse("ACCOUNT_NOT_EMPTY", account=account_id, balance=account.balance)
        Account.objects.filter(pk=account_id).update(closed=True)
        return ActionResult(True, "OK", {"account": account_id})


# --- saldo bruto, reservado, disponível ---------------------------------------------------------------------------------

def reserved_of(account_id: int) -> int:
    return Hold.objects.filter(account_id=account_id, status=HoldStatus.ACTIVE.value).aggregate(s=Sum("amount"))["s"] or 0


def pending_total(account_id: int) -> int:
    """Soma do que a conta (devedora) ainda deve em obrigações pendentes (NÃO é dinheiro, §24.9)."""
    rows = Obligation.objects.filter(debtor_id=account_id, status=ObligationStatus.OPEN.value).values_list("amount_due", "amount_paid")
    return sum(due - paid for due, paid in rows)


def balance_of(account_id: int) -> int:
    """Saldo BRUTO em centavos (inclui o reservado)."""
    return Account.objects.values_list("balance", flat=True).get(pk=account_id)


def available_of(account_id: int) -> int:
    """Disponível para gastar = saldo bruto − reservas ativas (nunca entra na conservação, §24.3.3)."""
    return balance_of(account_id) - reserved_of(account_id)


@dataclass(frozen=True)
class FundsQuote:
    ok: bool
    requested: int
    gross: int
    reserved: int
    available: int
    shortfall: int
    pending_obligations: int
    explained: Explained

    def to_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "requested": self.requested, "gross": self.gross, "reserved": self.reserved,
                "available": self.available, "shortfall": self.shortfall, "pending_obligations": self.pending_obligations,
                "explained": self.explained.to_dict()}


def _quote_from(account_id: int, requested: int, gross: int, at: Optional[int]) -> FundsQuote:
    reserved = reserved_of(account_id)
    explained = Calc("gross_balance", gross).add("reserved", -reserved).result(at)
    available = explained.value
    shortfall = max(0, requested - int(available))
    return FundsQuote(shortfall == 0, requested, gross, reserved, int(available), shortfall,
                      pending_total(account_id), explained)


def quote(account_id: int, amount: int) -> ActionResult:
    """Consulta SEM mover dinheiro (o `check_action` do Action Registry usa): cabe `amount` no disponível da conta?"""
    problem = amount_problem(amount)
    if problem:
        return _refuse(problem, amount=amount)
    account = Account.objects.filter(pk=account_id).first()
    if account is None:
        return _refuse("ACCOUNT_NOT_FOUND", account=account_id)
    q = _quote_from(account_id, amount, account.balance, game_clock.now())
    return ActionResult(q.ok, "OK" if q.ok else "INSUFFICIENT_FUNDS", q.to_dict())


def can_afford(account_id: int, amount: int) -> bool:
    return quote(account_id, amount).ok


# --- rotas permitidas ---------------------------------------------------------------------------------------------------

def _route_problem(origin: Account, dest: Account, nature: Nature) -> Optional[str]:
    ok_, dk = AccountKind(origin.kind), AccountKind(dest.kind)
    if ok_ == AccountKind.SINK:
        return "SINK_NOT_SPENDABLE"
    if dk == AccountKind.ISSUANCE:
        return "ISSUANCE_NOT_ALLOWED"
    if ok_ == AccountKind.ISSUANCE:
        if nature != Nature.SCENARIO_GRANT:
            return "ISSUANCE_NOT_ALLOWED"
        return None if dk in OPERATIONAL_KINDS else "NATURE_ACCOUNT_MISMATCH"
    if nature == Nature.SCENARIO_GRANT:
        return "ISSUANCE_NOT_ALLOWED"
    if dk == AccountKind.SINK and nature not in SINK_NATURES:
        return "NATURE_ACCOUNT_MISMATCH"
    if nature in SINK_NATURES and dk != AccountKind.SINK:
        return "NATURE_ACCOUNT_MISMATCH"
    if ok_ == AccountKind.RETENTION and nature not in RETENTION_OUT_NATURES:
        return "NATURE_ACCOUNT_MISMATCH"
    if dk == AccountKind.RETENTION and nature not in RETENTION_IN_NATURES:
        return "NATURE_ACCOUNT_MISMATCH"
    if nature == Nature.RETENTION_IN and dk != AccountKind.RETENTION:
        return "NATURE_ACCOUNT_MISMATCH"
    if nature in (Nature.RETENTION_RELEASE, Nature.RETENTION_REFUND) and ok_ != AccountKind.RETENTION:
        return "NATURE_ACCOUNT_MISMATCH"
    return None


# --- transação (núcleo) -------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Leg:
    from_id: int
    to_id: int
    amount: int
    nature: Nature
    category: str = ""
    operation: str = ""
    explained: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class HoldUse:
    """Consome (parcial ou totalmente) uma reserva ANTES de checar o disponível: pagar o que estava reservado."""
    hold_id: int
    amount: int


def _hash(legs: Sequence[Leg], reference: Tuple[str, str], competence_day: Optional[int], uses: Sequence[HoldUse],
          reverses: Optional[int]) -> str:
    payload = [[[l.from_id, l.to_id, l.amount, Nature(l.nature).value, l.category, l.operation] for l in legs],
               list(reference), competence_day, [[u.hold_id, u.amount] for u in uses], reverses]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _result_of(tx: Transaction, already: bool) -> ActionResult:
    entries = list(tx.entries.order_by("seq"))
    return ActionResult(True, "OK", {"transaction_id": tx.pk, "seqs": [e.seq for e in entries], "already_posted": already,
                                     "amount": sum(e.amount for e in entries)})


def post_transaction(legs: Sequence[Leg], *, key: str, reference_kind: str, reference_id, at: Optional[int] = None,
                     competence_day: Optional[int] = None, actor: str = "system", uses: Sequence[HoldUse] = (),
                     reverses: Optional[int] = None, _internal: bool = False) -> ActionResult:
    """
    Grava TODAS as pernas ou nenhuma. `key` é a chave de idempotência: repetir o mesmo conteúdo devolve o resultado original
    (`already_posted=True`); a mesma chave com conteúdo diferente recusa (`IDEMPOTENCY_CONFLICT`).
    Recusas: KEY_REQUIRED, REFERENCE_REQUIRED, EMPTY_TRANSACTION, NATURE_INVALID, NATURE_REQUIRES_PAYROLL, AMOUNT_*,
    SAME_ACCOUNT, ACCOUNT_NOT_FOUND, ACCOUNT_CLOSED, SINK_NOT_SPENDABLE, ISSUANCE_NOT_ALLOWED, NATURE_ACCOUNT_MISMATCH,
    HOLD_NOT_FOUND, HOLD_INSUFFICIENT, INSUFFICIENT_FUNDS, IDEMPOTENCY_CONFLICT.
    """
    legs = list(legs)
    reference_id = str(reference_id)
    if not key:
        return _refuse("KEY_REQUIRED")
    if not reference_kind or not reference_id:
        return _refuse("REFERENCE_REQUIRED")
    if not legs:
        return _refuse("EMPTY_TRANSACTION")
    for l in legs:
        try:
            nature = Nature(l.nature)
        except ValueError:
            return _refuse("NATURE_INVALID", nature=str(l.nature))
        problem = amount_problem(l.amount)
        if problem:
            return _refuse(problem, amount=l.amount)
        if l.from_id == l.to_id:
            return _refuse("SAME_ACCOUNT", account=l.from_id)
        if nature in REMUNERATION_NATURES and not _internal:
            return _refuse("NATURE_REQUIRES_PAYROLL", nature=nature.value)
    for u in uses:
        problem = amount_problem(u.amount)
        if problem:
            return _refuse(problem, amount=u.amount)
    payload_hash = _hash(legs, (reference_kind, reference_id), competence_day, uses, reverses)
    at = game_clock.now() if at is None else at
    day = competence_day_of(at) if competence_day is None else competence_day
    try:
        with transaction.atomic():
            existing = Transaction.objects.filter(key=key).first()
            if existing is not None:
                if existing.payload_hash != payload_hash:
                    return _refuse("IDEMPOTENCY_CONFLICT", key=key)
                return _result_of(existing, True)
            return _post(legs, key, payload_hash, reference_kind, reference_id, at, day, actor, list(uses), reverses)
    except _Refuse as r:
        return r.result


def _post(legs: List[Leg], key: str, payload_hash: str, reference_kind: str, reference_id: str, at: int, day: int,
          actor: str, uses: List[HoldUse], reverses: Optional[int]) -> ActionResult:
    ids = sorted({i for l in legs for i in (l.from_id, l.to_id)})
    locked = {a.pk: a for a in Account.objects.select_for_update().filter(pk__in=ids).order_by("pk")}   # ordem crescente
    for i in ids:
        if i not in locked:
            _fail("ACCOUNT_NOT_FOUND", account=i)
        if locked[i].closed:
            _fail("ACCOUNT_CLOSED", account=i)
    for l in legs:
        problem = _route_problem(locked[l.from_id], locked[l.to_id], Nature(l.nature))
        if problem:
            _fail(problem, from_account=l.from_id, to_account=l.to_id, nature=Nature(l.nature).value)
    # reservas consumidas primeiro: pagar o que estava reservado
    reserved_cache: Dict[int, int] = {}
    for u in uses:
        hold = Hold.objects.select_for_update().filter(pk=u.hold_id).first()
        if hold is None or hold.status != HoldStatus.ACTIVE.value:
            _fail("HOLD_NOT_FOUND", hold=u.hold_id)
        if u.amount > hold.amount:
            _fail("HOLD_INSUFFICIENT", hold=u.hold_id, remaining=hold.amount, requested=u.amount)
        if hold.account_id not in {l.from_id for l in legs}:
            _fail("HOLD_ACCOUNT_MISMATCH", hold=u.hold_id)
        left = hold.amount - u.amount
        Hold.objects.filter(pk=hold.pk).update(
            amount=left, status=HoldStatus.CONSUMED.value if left == 0 else HoldStatus.ACTIVE.value,
            resolved_at=at if left == 0 else None)
    running = {i: locked[i].balance for i in ids}
    try:
        tx = _create_transaction(key, payload_hash, actor, at)
    except IntegrityError:                  # corrida por chave: outra requisição gravou primeiro
        raise _Refuse(_refuse("IDEMPOTENCY_CONFLICT", key=key))
    entries: List[Entry] = []
    for n, l in enumerate(legs):
        origin, dest = locked[l.from_id], locked[l.to_id]
        if AccountKind(origin.kind) != AccountKind.ISSUANCE:
            reserved = reserved_cache.get(l.from_id)
            if reserved is None:
                reserved = reserved_cache[l.from_id] = reserved_of(l.from_id)
            available = running[l.from_id] - reserved
            if available < l.amount:
                q = _quote_from(l.from_id, l.amount, running[l.from_id], at)
                _fail("INSUFFICIENT_FUNDS", account=l.from_id, **q.to_dict())
        if running[l.to_id] + l.amount > MAX_AMOUNT and AccountKind(dest.kind) != AccountKind.SINK:
            _fail("AMOUNT_TOO_LARGE", account=l.to_id, balance=running[l.to_id], amount=l.amount)
        fb, tb = running[l.from_id], running[l.to_id]
        running[l.from_id] = fb - l.amount
        running[l.to_id] = tb + l.amount
        entries.append(Entry(
            transaction=tx, from_account=origin, to_account=dest, amount=l.amount, nature=Nature(l.nature).value,
            competence_day=day, at=at, category=l.category, operation=l.operation, reference_kind=reference_kind,
            reference_id=reference_id, actor=actor, from_balance_before=fb, from_balance_after=running[l.from_id],
            to_balance_before=tb, to_balance_after=running[l.to_id], explained=l.explained or {},
            reverses_id=reverses if n == 0 else None))
    for e in entries:       # um a um: `seq` crescente na ordem das pernas
        e.save()
    for i in ids:
        if running[i] != locked[i].balance:
            Account.objects.filter(pk=i).update(balance=running[i])
    return _result_of(tx, False)


def _create_transaction(key: str, payload_hash: str, actor: str, at: int) -> Transaction:
    with transaction.atomic():      # savepoint: a violação da chave única não envenena a transação externa
        return Transaction.objects.create(key=key, payload_hash=payload_hash, actor=actor, at=at)


def transfer(from_id: int, to_id: int, amount: int, nature: Nature, *, key: str, reference_kind: str, reference_id,
             at: Optional[int] = None, actor: str = "system", category: str = "", operation: str = "",
             explained: Optional[Dict[str, Any]] = None, uses: Sequence[HoldUse] = ()) -> ActionResult:
    """Uma perna. Remuneração (`WAGE`, `MILITARY_PAY`, `OWNER_SALARY`, `POLITICAL_SALARY`) NÃO passa por aqui."""
    return post_transaction([Leg(from_id, to_id, amount, nature, category, operation, explained)], key=key,
                            reference_kind=reference_kind, reference_id=reference_id, at=at, actor=actor, uses=uses)


# --- reservas -----------------------------------------------------------------------------------------------------------

def hold(account_id: int, amount: int, *, key: str, reference_kind: str, reference_id, at: Optional[int] = None) -> ActionResult:
    """Reserva `amount` do saldo bruto da conta (fica indisponível, continua da conta). Idempotente por `key`."""
    problem = amount_problem(amount)
    if problem:
        return _refuse(problem, amount=amount)
    if not key or not reference_kind or not str(reference_id):
        return _refuse("REFERENCE_REQUIRED")
    at = game_clock.now() if at is None else at
    with transaction.atomic():
        account = Account.objects.select_for_update().filter(pk=account_id).first()
        if account is None:
            return _refuse("ACCOUNT_NOT_FOUND", account=account_id)
        if account.closed:
            return _refuse("ACCOUNT_CLOSED", account=account_id)
        if AccountKind(account.kind) in (AccountKind.SINK, AccountKind.ISSUANCE):
            return _refuse("SINK_NOT_SPENDABLE", account=account_id)
        existing = Hold.objects.filter(key=key).first()
        if existing is not None:
            same = (existing.account_id, existing.original_amount, existing.reference_kind, existing.reference_id) == (
                account_id, amount, reference_kind, str(reference_id))
            return ActionResult(True, "OK", {"hold_id": existing.pk, "already_posted": True}) if same else _refuse(
                "IDEMPOTENCY_CONFLICT", key=key)
        available = account.balance - reserved_of(account_id)
        if available < amount:
            q = _quote_from(account_id, amount, account.balance, at)
            return _refuse("INSUFFICIENT_AVAILABLE", account=account_id, **q.to_dict())
        h = Hold.objects.create(key=key, account=account, original_amount=amount, amount=amount,
                                reference_kind=reference_kind, reference_id=str(reference_id), created_at=at)
        return ActionResult(True, "OK", {"hold_id": h.pk, "already_posted": False, "amount": amount})


def release_hold(hold_id: int, *, at: Optional[int] = None) -> ActionResult:
    """Libera o que resta da reserva (volta a ficar disponível). Liberar de novo é inofensivo (idempotente)."""
    at = game_clock.now() if at is None else at
    with transaction.atomic():
        h = Hold.objects.select_for_update().filter(pk=hold_id).first()
        if h is None:
            return _refuse("HOLD_NOT_FOUND", hold=hold_id)
        if h.status == HoldStatus.ACTIVE.value:
            Hold.objects.filter(pk=h.pk).update(status=HoldStatus.RELEASED.value, resolved_at=at)
            return ActionResult(True, "OK", {"hold_id": hold_id, "released": h.amount, "already_posted": False})
        return ActionResult(True, "OK", {"hold_id": hold_id, "released": 0, "already_posted": True, "status": h.status})


# --- retenções genéricas ------------------------------------------------------------------------------------------------

def open_retention(purpose: str, owner_ref: str) -> Account:
    """Conta de custódia identificada por `owner_ref` opaco (ex.: `contract:123`). Idempotente."""
    return get_or_create_account(AccountKind.RETENTION, 0, owner_ref, purpose)


def retain(from_id: int, retention_id: int, amount: int, *, key: str, reference_kind: str, reference_id,
           at: Optional[int] = None, actor: str = "system", uses: Sequence[HoldUse] = ()) -> ActionResult:
    """Move dinheiro da conta do pagador para a custódia: o valor SAIU do dono e não está disponível a ninguém."""
    return transfer(from_id, retention_id, amount, Nature.RETENTION_IN, key=key, reference_kind=reference_kind,
                    reference_id=reference_id, at=at, actor=actor, uses=uses)


def release_retention(retention_id: int, destination_id: int, *, key: str, reference_kind: str, reference_id,
                      amount: Optional[int] = None, refund: bool = False, at: Optional[int] = None,
                      actor: str = "system") -> ActionResult:
    """
    Move da custódia para um destino ESCOLHIDO por quem chama (o registro não inventa beneficiário). `amount=None` = todo o
    saldo. `refund=True` usa `RETENTION_REFUND` (devolução ao pagador), senão `RETENTION_RELEASE`.
    """
    with transaction.atomic():
        r = Account.objects.select_for_update().filter(pk=retention_id).first()
        if r is None or AccountKind(r.kind) != AccountKind.RETENTION:
            return _refuse("ACCOUNT_NOT_FOUND", account=retention_id)
        value = r.balance if amount is None else amount
        if value <= 0:
            return _refuse("RETENTION_EMPTY", account=retention_id, balance=r.balance)
        return transfer(retention_id, destination_id, value,
                        Nature.RETENTION_REFUND if refund else Nature.RETENTION_RELEASE, key=key,
                        reference_kind=reference_kind, reference_id=reference_id, at=at, actor=actor)


# --- roteamento tributário (interface; sem módulo militar) --------------------------------------------------------------

TerritoryRef = Tuple[str, int]
TaxResolver = Callable[[Optional[TerritoryRef], int], Optional[int]]
_tax_resolvers: Dict[str, TaxResolver] = {}


def register_tax_resolver(name: str, fn: TaxResolver) -> None:
    """Outro módulo (P1.17: ações de milícia) decide, por território e instante, se o imposto vai a uma conta de retenção."""
    if name in _tax_resolvers:
        raise ValueError(f"Resolvedor tributário duplicado: {name}")
    _tax_resolvers[name] = fn


def unregister_tax_resolver(name: str) -> None:
    _tax_resolvers.pop(name, None)


def clear_tax_resolvers() -> None:  # para testes
    _tax_resolvers.clear()


def territory_str(ref: Optional[TerritoryRef]) -> str:
    return "" if ref is None else f"{ref[0]}:{ref[1]}"


def territory_from_str(text: str) -> Optional[TerritoryRef]:
    if not text:
        return None
    kind, _, ident = text.partition(":")
    return kind, int(ident)


def _tax_destination(territory: Optional[TerritoryRef], at: int) -> Tuple[int, Optional[str], Dict[str, Any]]:
    answers: Dict[str, int] = {}
    for name in sorted(_tax_resolvers):
        out = _tax_resolvers[name](territory, at)
        if out is not None:
            answers[name] = out
    if len(set(answers.values())) > 1:
        _fail("TAX_ROUTE_AMBIGUOUS", answers=answers)
    if not answers:
        return union_account().pk, None, {"destination": "union", "territory": territory_str(territory)}
    name, account_id = sorted(answers.items())[0]
    acc = Account.objects.filter(pk=account_id).first()
    if acc is None or AccountKind(acc.kind) != AccountKind.RETENTION or acc.closed:
        _fail("TAX_ROUTE_INVALID", resolver=name, account=account_id)
    return account_id, name, {"destination": "retention", "resolver": name, "territory": territory_str(territory)}


def route_tax(territory: Optional[TerritoryRef] = None, at: Optional[int] = None) -> ActionResult:
    """Destino de um imposto atribuído a um território: a `UNION`, ou a retenção indicada por um resolvedor registrado."""
    at = game_clock.now() if at is None else at
    try:
        account_id, resolver, info = _tax_destination(territory, at)
    except _Refuse as r:
        return r.result
    return ActionResult(True, "OK", {"account_id": account_id, "resolver": resolver, **info})


def tax_legs(payer_id: int, gross: int, tax: int, territory: Optional[TerritoryRef], at: int,
             tax_nature: Nature) -> Tuple[List[Leg], Dict[str, Any]]:
    """
    Divisão do imposto retido (R2): pagador paga `gross`; o líquido vai ao beneficiário (perna do chamador) e `tax` ao destino
    tributário. Se o destino é a PRÓPRIA conta pagadora (governo federal comprando, imposto à União), não há lançamento de uma
    conta para ela mesma: a compensação fica só no `Explained` (sem lançamento fictício).
    """
    info: Dict[str, Any] = {"tax": tax}
    if tax == 0:
        return [], info
    dest_id, resolver, route = _tax_destination(territory, at)
    info.update(route)
    if dest_id == payer_id:
        info["self_compensated"] = True
        return [], info
    info["self_compensated"] = False
    return [Leg(payer_id, dest_id, tax, tax_nature, operation="tax", explained=dict(info))], info


def post_taxed_payment(payer_id: int, payee_id: int, gross: int, *, nature: Nature, tax_rate: Decimal,
                       territory: Optional[TerritoryRef] = None, tax_nature: Nature = Nature.TAX_SALES, key: str,
                       reference_kind: str, reference_id, at: Optional[int] = None, actor: str = "system",
                       competence_day: Optional[int] = None, category: str = "", operation: str = "",
                       uses: Sequence[HoldUse] = (), tax_amount: Optional[int] = None,
                       explained_extra: Optional[Dict[str, Any]] = None, _internal: bool = False) -> ActionResult:
    """
    Pagamento com imposto retido do valor (R1/R2): `payer → payee` (líquido) e `payer → destino tributário` (imposto).
    `tax_amount` (centavos) substitui o cálculo por alíquota: usado na quitação parcial de obrigação, em que o imposto de cada
    parcela vem do acumulado (arredondado UMA vez; a última parcela fecha o resto).
    """
    problem = amount_problem(gross)
    if problem:
        return _refuse(problem, amount=gross)
    if isinstance(tax_rate, float) or not Decimal(0) <= Decimal(tax_rate) <= Decimal(1):
        return _refuse("TAX_RATE_INVALID", rate=str(tax_rate))
    if tax_nature not in TAX_NATURES:
        return _refuse("NATURE_INVALID", nature=str(tax_nature))
    at = game_clock.now() if at is None else at
    if tax_amount is None:
        tax = percent_of(gross, Decimal(tax_rate))
    elif not is_centavos(tax_amount) or not 0 <= tax_amount <= gross:
        return _refuse("TAX_AMOUNT_INVALID", tax=tax_amount, gross=gross)
    else:
        tax = tax_amount
    net = gross - tax
    try:
        with transaction.atomic():
            tlegs, info = tax_legs(payer_id, gross, tax, territory, at, tax_nature)
            info.update({"gross": gross, "net": net, "tax_rate": str(tax_rate), **(explained_extra or {})})
            legs = ([Leg(payer_id, payee_id, net, nature, category, operation, dict(info))] if net > 0 else []) + tlegs
            if not legs:        # imposto de 100% compensado: nada a mover
                return ActionResult(True, "OK", {"transaction_id": None, "seqs": [], "already_posted": False, "amount": 0, **info})
            result = post_transaction(legs, key=key, reference_kind=reference_kind, reference_id=reference_id, at=at,
                                      competence_day=competence_day, actor=actor, uses=uses, _internal=_internal)
            if result.ok:
                result.detail.update({"gross": gross, "tax": tax, "net": net, "taxed": info})
            return result
    except _Refuse as r:
        return r.result


# --- estorno técnico ----------------------------------------------------------------------------------------------------

def reverse(seq: int, reason: str, *, key: str, actor: str = "system", at: Optional[int] = None) -> ActionResult:
    """Estorno técnico: lançamento oposto que referencia o original (que permanece). Nunca de emissão, remuneração ou sumidouro."""
    if not reason:
        return _refuse("REASON_REQUIRED")
    with transaction.atomic():
        e = Entry.objects.select_related("from_account", "to_account").filter(pk=seq).first()
        if e is None:
            return _refuse("ENTRY_NOT_FOUND", seq=seq)
        nature = Nature(e.nature)
        if Entry.objects.filter(reverses_id=seq).exists():
            return _refuse("REVERSAL_NOT_POSSIBLE", seq=seq, why="already_reversed")
        if nature in (Nature.SCENARIO_GRANT, Nature.REVERSAL) or nature in REMUNERATION_NATURES:
            return _refuse("REVERSAL_NOT_POSSIBLE", seq=seq, why="nature")
        if AccountKind(e.to_account.kind) in (AccountKind.SINK, AccountKind.ISSUANCE):
            return _refuse("REVERSAL_NOT_POSSIBLE", seq=seq, why="sink_or_issuance")
        result = post_transaction(
            [Leg(e.to_account_id, e.from_account_id, e.amount, Nature.REVERSAL, operation="reversal",
                 explained={"reverses": seq, "reason": reason})],
            key=key, reference_kind="entry", reference_id=seq, at=at, actor=actor, reverses=seq,
            competence_day=e.competence_day)
        if not result.ok and result.code == "INSUFFICIENT_FUNDS":
            return _refuse("REVERSAL_NOT_POSSIBLE", seq=seq, why="insufficient_funds", **result.detail)
        return result


# --- cenário e dotações (única fonte de emissão) ------------------------------------------------------------------------

def create_scenario(name: str, lines: Dict[str, Optional[int]]) -> LedgerScenario:
    """Cenário monetário com linhas de dotação por papel. Valor `None` = NÃO especificado (impede ativar)."""
    sc, _ = LedgerScenario.objects.get_or_create(name=name, defaults={"created_at": game_clock.now()})
    for role, amount in lines.items():
        set_grant_line(name, role, amount)
    return sc


def set_grant_line(scenario: str, role: str, amount: Optional[int]) -> ScenarioGrantLine:
    if amount is not None and (not isinstance(amount, int) or isinstance(amount, bool) or amount < 0 or amount > MAX_AMOUNT):
        raise ValueError(f"dotação inválida: {amount!r}")
    sc = LedgerScenario.objects.get(name=scenario)
    line, _ = ScenarioGrantLine.objects.update_or_create(scenario=sc, role=role, defaults={"amount": amount})
    return line


def activate_scenario(name: str, required_roles: Iterable[str]) -> ActionResult:
    """
    Ativa o cenário se TODA dotação exigida está explícita (0 é válido). Valor ausente → recusa `SCENARIO_GRANT_UNSPECIFIED`
    e lista as pendências (nenhum valor é inventado). Só um cenário fica ativo.
    """
    with transaction.atomic():
        sc = LedgerScenario.objects.select_for_update().filter(name=name).first()
        if sc is None:
            return _refuse("SCENARIO_NOT_FOUND", scenario=name)
        have = {l.role: l.amount for l in sc.lines.all()}
        missing = sorted(r for r in set(required_roles) if have.get(r) is None)
        if missing:
            return _refuse("SCENARIO_GRANT_UNSPECIFIED", scenario=name, missing=missing)
        LedgerScenario.objects.exclude(pk=sc.pk).update(active=False)
        LedgerScenario.objects.filter(pk=sc.pk).update(active=True)
        return ActionResult(True, "OK", {"scenario": name, "roles": sorted(set(required_roles))})


def active_scenario() -> Optional[LedgerScenario]:
    return LedgerScenario.objects.filter(active=True).first()


def grant_scenario_allocation(scenario: str, account_id: int, amount: int, *, role: str = "", at: Optional[int] = None,
                              actor: str = "scenario") -> ActionResult:
    """
    Dotação: `ISSUANCE → conta`, natureza `SCENARIO_GRANT`, referência `scenario:<nome>`. ÚNICA fonte de dinheiro novo.
    Idempotente por `(cenário, conta)`: uma dotação por conta. Valor 0 não gera lançamento (é registrado na linha do cenário).
    """
    if not LedgerScenario.objects.filter(name=scenario).exists():
        return _refuse("SCENARIO_NOT_FOUND", scenario=scenario)
    return post_transaction(
        [Leg(issuance_account().pk, account_id, amount, Nature.SCENARIO_GRANT, operation="grant",
             explained={"scenario": scenario, "role": role})],
        key=f"grant:{scenario}:{account_id}", reference_kind="scenario", reference_id=scenario, at=at, actor=actor)


def grant_for_role(account_id: int, role: str, *, at: Optional[int] = None) -> ActionResult:
    """Dotação do papel no cenário ATIVO (linha explícita). Zero explícito vale e não emite; ausente recusa."""
    sc = active_scenario()
    if sc is None:
        return ActionResult(True, "NO_ACTIVE_SCENARIO", {"granted": 0})
    line = sc.lines.filter(role=role).first()
    if line is None or line.amount is None:
        return _refuse("SCENARIO_GRANT_UNSPECIFIED", scenario=sc.name, missing=[role])
    if line.amount == 0:
        return ActionResult(True, "OK", {"granted": 0, "explicit_zero": True, "scenario": sc.name})
    result = grant_scenario_allocation(sc.name, account_id, line.amount, role=role, at=at)
    if result.ok:
        result.detail["granted"] = line.amount
    return result
