"""
Serviços do núcleo das Empresas (design/02 §16-17). Recusas são CÓDIGOS (`ActionResult`), como no resto do projeto.

PROTOCOLO DE TRAVAMENTO (um só; a ordem evita ciclo, e a lição de PostgreSQL do Inventário vale aqui: inserir uma linha que
referencia `Player`/`Company` toma `FOR KEY SHARE` nela, então quem a referencia a trava antes):
  1. a linha do jogador (`players.Player`);
  2. a linha da empresa (`Company`), quando a operação é sobre uma empresa existente;
  3. o registro monetário (contas em ordem crescente de id, `ledger`).

Nada aqui cria dinheiro (CLAUDE.md §5.2): a fundação MOVE dinheiro do fundador para o caixa federal (`COMPANY_FOUNDING`, 24 Q2) e
o aporte MOVE dinheiro do Dono para a conta da empresa. O Dono não é dono do saldo da empresa (24 §24.3) e não existe retirada.
"""
from __future__ import annotations

from typing import Any, Optional

from django.db import transaction

from core import clock as game_clock
from core.breakdown import Calc, Explained
from ledger import services as ledger
from ledger.constants import MAX_AMOUNT, AccountKind, Nature
from players.models import Player
from players.services import ActionResult

from . import params
from .constants import FOUNDING_COST_CENTS, MAX_NAME_LENGTH, MAX_SALARY_CENTS, CompanyType, PositionKind
from .models import CapitalContribution, Company, Position

_INT64 = 2 ** 63


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def company_account(company_id: int):
    """Conta `COMPANY` da empresa (24 §24.3.2: o app dono valida que a empresa existe)."""
    if not Company.objects.filter(pk=company_id).exists():
        raise ValueError(f"empresa inexistente: {company_id}")
    return ledger.get_or_create_account(AccountKind.COMPANY, company_id)


def owner_of(company_id: int) -> Optional[int]:
    """Jogador que ocupa o cargo Dono (02 §16), ou None."""
    return (Position.objects.filter(company_id=company_id, kind=PositionKind.OWNER.value)
            .values_list("holder_id", flat=True).first())


# --- fundação (02 §17) --------------------------------------------------------------------------------------------------

def founding_cost(company_type) -> Optional[Explained]:
    """Custo de fundação do tipo (02 §17) em centavos, com detalhamento (20); None se o tipo não existe."""
    try:
        t = CompanyType(company_type)
    except ValueError:
        return None
    return Calc("founding_cost", FOUNDING_COST_CENTS[t]).result(game_clock.now())


def founding_refusal(player_id: int, company_type: Any, name: Any, owner_salary: Any) -> Optional[ActionResult]:
    """Recusas que só LEEM: parâmetros, tipo, nome, salário do Dono e saldo para o custo."""
    if not isinstance(company_type, str):
        return _refuse("INVALID_PARAMS", why="type deve ser texto")
    cost = founding_cost(company_type)
    if cost is None:
        return _refuse("INVALID_COMPANY_TYPE", type=company_type[:40], allowed=sorted(t.value for t in CompanyType))
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_NAME_LENGTH:
        return _refuse("INVALID_NAME", max_length=MAX_NAME_LENGTH)
    if not _is_int(owner_salary) or not 0 <= owner_salary <= MAX_SALARY_CENTS:
        return _refuse("INVALID_SALARY", owner_salary=repr(owner_salary)[:40], max=MAX_SALARY_CENTS)
    cents = int(cost.value)
    funds = ledger.quote(ledger.player_account(player_id).pk, cents)
    if not funds.ok:
        return _refuse("INSUFFICIENT_FUNDS", cost=cents, **{k: v for k, v in funds.detail.items() if k not in ("ok", "cost")})
    return None


def found_company(player_id: int, company_type: Any, name: Any, owner_salary: Any) -> ActionResult:
    """
    Funda uma empresa: cobra o custo do tipo (02 §17) do fundador para o caixa federal, cria a empresa com a estrela inicial
    `[PROV]`, a conta `COMPANY` e o cargo Dono (02 §16) ocupado pelo fundador com o salário que ele definiu (centavos). Atômico.
    Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS, INVALID_COMPANY_TYPE, INVALID_NAME, INVALID_SALARY, INSUFFICIENT_FUNDS.
    O fundador pode fundar quantas empresas o dinheiro permitir (o design não limita) e continua livre para ter um emprego.
    """
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    with transaction.atomic():
        Player.objects.select_for_update().get(pk=player_id)                                   # protocolo, 1
        refusal = founding_refusal(player_id, company_type, name, owner_salary)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        cost = founding_cost(company_type)
        cents = int(cost.value)
        sequence = Company.objects.filter(founder_id=player_id).count() + 1
        key = f"company_founding:{player_id}:{sequence}"
        paid = ledger.transfer(
            ledger.player_account(player_id).pk, ledger.union_account().pk, cents, Nature.COMPANY_FOUNDING, key=key,
            reference_kind="company_founding", reference_id=f"{player_id}:{sequence}", at=now, actor=f"player:{player_id}",
            category="company_founding", operation="found_company",
            explained={"type": company_type, "cost": cents})
        if not paid.ok:
            return _refuse(paid.code, **{**paid.detail, "cost": cents})
        company = Company.objects.create(
            name=name.strip(), type=company_type, founder_id=player_id, stars=params.INITIAL_STARS, founded_at=now,
            founding_sequence=sequence, founding_cost=cents, founding_key=key, explained=cost.to_dict())
        Position.objects.create(company=company, kind=PositionKind.OWNER.value, salary=owner_salary, holder_id=player_id,
                                created_at=now)
        account = ledger.get_or_create_account(AccountKind.COMPANY, company.pk)
        return ActionResult(True, "OK", {
            "company": company.pk, "type": company_type, "stars": company.stars, "cost": cents, "cost_explained": cost,
            "account": account.pk, "owner_salary": owner_salary})


# --- aporte de capital --------------------------------------------------------------------------------------------------

def contribution_refusal(player_id: int, company_id: Any, amount: Any) -> Optional[ActionResult]:
    """Recusas que só LEEM: parâmetros, empresa, cargo Dono e saldo."""
    if not _is_int(company_id) or not -_INT64 <= company_id < _INT64:
        return _refuse("INVALID_PARAMS", company=repr(company_id)[:40])
    if not _is_int(amount) or not 0 < amount <= MAX_AMOUNT:
        return _refuse("INVALID_AMOUNT", amount=repr(amount)[:40])
    if not Company.objects.filter(pk=company_id).exists():
        return _refuse("COMPANY_NOT_FOUND", company=company_id)
    if owner_of(company_id) != player_id:
        return _refuse("NOT_OWNER", company=company_id)
    funds = ledger.quote(ledger.player_account(player_id).pk, amount)
    if not funds.ok:
        return _refuse("INSUFFICIENT_FUNDS", amount=amount, **{k: v for k, v in funds.detail.items() if k != "ok"})
    return None


def fund_company(player_id: int, company_id: Any, amount: Any) -> ActionResult:
    """
    O Dono aporta capital: dinheiro do jogador vai para a conta da empresa (24: transferência de dinheiro existente, nunca
    dinheiro novo). Natureza `DONATION`, categoria `company_capital` (a lista de naturezas do 24 é fechada e não tem "aporte";
    doação não é remuneração nem venda e não gera imposto — interpretação técnica registrada no CHANGELOG_DEV).
    Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS, INVALID_AMOUNT, COMPANY_NOT_FOUND, NOT_OWNER, INSUFFICIENT_FUNDS.
    """
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    with transaction.atomic():
        Player.objects.select_for_update().get(pk=player_id)                                   # protocolo, 1
        if _is_int(company_id) and -_INT64 <= company_id < _INT64:
            Company.objects.select_for_update().filter(pk=company_id).first()                  # protocolo, 2
        refusal = contribution_refusal(player_id, company_id, amount)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        sequence = CapitalContribution.objects.filter(company_id=company_id).count() + 1
        key = f"company_capital:{company_id}:{sequence}"
        account = company_account(company_id)
        paid = ledger.transfer(
            ledger.player_account(player_id).pk, account.pk, amount, Nature.DONATION, key=key,
            reference_kind="company_capital", reference_id=f"{company_id}:{sequence}", at=now, actor=f"player:{player_id}",
            category="company_capital", operation="fund_company", explained={"company": company_id, "amount": amount})
        if not paid.ok:
            return _refuse(paid.code, **{**paid.detail, "amount": amount})
        contribution = CapitalContribution.objects.create(company_id=company_id, player_id=player_id, sequence=sequence,
                                                          amount=amount, ledger_key=key, at=now)
        return ActionResult(True, "OK", {"contribution": contribution.pk, "company": company_id, "amount": amount,
                                         "company_balance": ledger.balance_of(account.pk)})
