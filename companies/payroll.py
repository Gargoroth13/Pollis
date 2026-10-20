"""
Salários das Empresas (design/02 §16; 24 §24.12-24.13; 01 §1.7; decisões do GD em `02` §25.2).

  - **Funcionário**: o salário do cargo é devido a CADA ação de Trabalhar (24 §24.13: "o salário de trabalho nasce no ato";
    01 §1.7: o limite é diário, não por clique). Roda como hook de `perform_action` (mesma transação do Trabalho, mesmo caminho
    de jogadores e bots). Natureza `WAGE`, pagador = conta da empresa.
  - **Dono**: o salário do cargo Dono é devido POR DIA, na folha do tick diário do mundo, em UM lote (24 §24.13). Natureza
    `OWNER_SALARY`, pagador = conta da empresa, competência = dia do tick.
  - **Caixa insuficiente**: política `PENDING` (GD 2026-10-19): vira obrigação registrada e auditável (`ledger.Obligation`),
    nunca dinheiro novo, nunca paga duas vezes (chave idempotente do pedido; quitação do registro). No tick diário a empresa
    quita o que o caixa permite, da competência mais antiga para a mais nova (R4), ANTES de pagar a folha do dia. (Um Trabalho
    com caixa disponível é pago na hora, sem fila: a fila só existe na quitação.)
  - `W`, `S`, `T`: `limits_for` é o provedor registrado no registro monetário sob demanda (`ensure_limits_provider`), para não
    colidir com um provedor de outro sistema. W e T usam os padrões das leis (`11` §11.1) até P1.12; S vem de `skills`.

PROTOCOLO: o hook roda com o jogador já travado e trava a empresa antes do registro monetário. A folha (tick, sem jogador) trava, nesta
ordem, contadores (jogador, dia) e contas (id crescente) ANTES de liquidar — a mesma ordem de quem paga um Trabalho.
"""
from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction

from core import ticks
from core.timeline import Tick, TickKind
from ledger import obligations, remuneration
from ledger import services as ledger
from ledger.constants import AccountKind, Nature, ObligationStatus, Policy
from ledger.models import Account, Obligation, RemunerationCounter
from ledger.money import competence_day_of
from players.actions import Action
from players.hooks import ActionHookContext, ActivityContext, register_action_hook, register_activity_provider
from players.models import Player

from . import params
from .constants import PositionKind, PositionStatus
from .jobs import current_job, relevant_skill
from .models import Company, Position, WorkWage
from .services import company_account

WAGE_HOOK = "companies_work_wage"
ACTIVITY_PROVIDER = "companies_job"
TICK_NAME = "companies_daily_payroll"


# --- limites W / S / T --------------------------------------------------------------------------------------------------

def limits_for(player_id: int, nature: Nature, at: int) -> Tuple[int, int, Optional[int]]:
    """
    (W, S, T) em centavos (24 §24.12): `W` e `T` dos padrões das leis (11 §11.1); `S` = nível da skill relevante × 1,5 (01 §1.7) da
    skill do cargo: do emprego para `WAGE`, do cargo Dono para `OWNER_SALARY`. Outras naturezas são de outros sistemas (militar,
    político) e ainda não têm provedor: recusa explícita, nunca um valor inventado.
    """
    from skills.services import salary_cap_for
    if nature == Nature.WAGE:
        job = current_job(player_id)
        if job is None:
            raise ValueError(f"limite de salário de trabalho sem emprego: jogador {player_id}")
        kind = PositionKind(job.kind)
    elif nature == Nature.OWNER_SALARY:
        kind = PositionKind.OWNER
    else:
        raise ValueError(f"natureza sem provedor de limites nas Empresas: {nature.value}")
    s_reais = salary_cap_for(player_id, relevant_skill(kind)).value
    s_cents = int((Decimal(s_reais) * 100).to_integral_value(rounding=ROUND_DOWN))
    return params.MIN_WAGE_PER_DAY_CENTS, s_cents, params.WAGE_CEILING_PER_DAY_CENTS


def ensure_limits_provider() -> None:
    if not remuneration.limits_provider_registered():
        remuneration.register_limits_provider(limits_for)


# --- salário do Trabalho ------------------------------------------------------------------------------------------------

def activity_for(player: Player, action: Action, now: int) -> Optional[ActivityContext]:
    """Contexto do Trabalho de quem tem emprego (02 §6): a skill relevante do cargo é a que ele desenvolve (01 §1.1, §1.8)."""
    if action is not Action.WORK:
        return None
    job = current_job(player.pk)
    if job is None:
        return None
    return ActivityContext(skills=(relevant_skill(job.kind).value,))


def pay_work_wage(ctx: ActionHookContext) -> Optional[Dict[str, Any]]:
    """Hook de `perform_action`: o Trabalho de um funcionário gera o salário do cargo. Sem emprego: nada (Trabalho livre, P0.04)."""
    if ctx.action is not Action.WORK:
        return None
    player_id = ctx.player.pk
    job = current_job(player_id)
    if job is None:
        return None
    ensure_limits_provider()
    Company.objects.select_for_update().filter(pk=job.company_id).first()                        # protocolo: jogador → empresa
    sequence = WorkWage.objects.filter(player_id=player_id).count() + 1
    key = f"work_wage:{player_id}:{sequence}"
    paid = remuneration.pay_remuneration_now(
        key=key, player_id=player_id, payer_id=company_account(job.company_id).pk, nature=Nature.WAGE, due=job.salary,
        earned_at=ctx.now, policy=Policy.PENDING, reference_kind="work_wage", reference_id=f"{player_id}:{sequence}",
        tax_rate=params.INCOME_TAX_RATE)
    if not paid.ok:
        raise RuntimeError(f"salário de trabalho recusado pelo registro monetário: {paid.code} {paid.detail}")
    WorkWage.objects.create(player_id=player_id, position=job, company_id=job.company_id, sequence=sequence, due=job.salary,
                            request_key=key, at=ctx.now)
    d = paid.detail
    return {"company": job.company_id, "position": job.pk, "sequence": sequence, "due": job.salary,
            "recognized": d["recognized"], "discarded": d["discarded"], "paid": d["paid"], "pending": d["pending"], "tax": d["tax"], "net": d["net"],
            "explained": d["explained"]}


# --- folha diária do Dono -----------------------------------------------------------------------------------------------

def _lock_for_payroll(day: int, owner_by_company: Dict[int, int], debt_companies: List[int]) -> Dict[int, Account]:
    """Contadores (jogador, dia) e depois contas, em ordem crescente: a ordem de quem paga um Trabalho (sem deadlock)."""
    for player_id in sorted(set(owner_by_company.values())):
        RemunerationCounter.objects.get_or_create(player_id=player_id, competence_day=day)
    for player_id in sorted(set(owner_by_company.values())):
        RemunerationCounter.objects.select_for_update().get(player_id=player_id, competence_day=day)
    company_ids = sorted(set(owner_by_company) | set(debt_companies))
    ids = {ledger.get_or_create_account(AccountKind.COMPANY, c).pk for c in company_ids}
    ids |= {ledger.player_account(p).pk for p in set(owner_by_company.values())}
    creditors = Obligation.objects.filter(status=ObligationStatus.OPEN.value, debtor_id__in=ids).values_list("creditor_id", flat=True)
    ids |= set(creditors)
    ids.add(ledger.union_account().pk)
    return {a.pk: a for a in Account.objects.select_for_update().filter(pk__in=sorted(ids)).order_by("pk")}


def run_daily_payroll(at: int) -> Dict[str, Any]:
    """
    Folha do dia que abre em `at` (tick diário do mundo): 1) cada empresa com obrigações abertas quita o que o caixa permite
    (mais antiga primeiro); 2) o salário do Dono de cada empresa vira UM pedido de remuneração e o lote é liquidado de uma vez.
    Idempotente: chaves por (empresa, dia). Falha do registro monetário levanta: o tick do mundo desfaz e não avança.
    """
    ensure_limits_provider()
    day = competence_day_of(at)
    owners = list(Position.objects.filter(kind=PositionKind.OWNER.value, status=PositionStatus.FILLED.value, salary__gt=0,
                                          company__founded_at__lt=at).order_by("company_id")
                  .values_list("company_id", "holder_id", "salary"))
    owner_by_company = {c: h for c, h, _ in owners}
    debtors = Obligation.objects.filter(status=ObligationStatus.OPEN.value, debtor__kind=AccountKind.COMPANY.value) \
        .values_list("debtor__owner_id", flat=True)
    debt_companies = sorted(set(debtors))
    if not owners and not debt_companies:
        return {"day": day, "settled": [], "payroll": {"count": 0}}
    with transaction.atomic():
        _lock_for_payroll(day, owner_by_company, debt_companies)
        settled = []
        for company_id in debt_companies:
            result = obligations.settle_obligations(company_account(company_id).pk, batch_key=f"company_debts:{day}:{company_id}",
                                                    at=at)
            if not result.ok:
                raise RuntimeError(f"quitação de obrigações da empresa {company_id}: {result.code} {result.detail}")
            if result.detail["paid"]:
                settled.append({"company": company_id, "total_gross": result.detail["total_gross"]})
        keys = []
        for company_id, holder_id, salary in owners:
            key = f"owner_salary:{company_id}:{day}"
            submitted = remuneration.submit_remuneration(
                key=key, player_id=holder_id, payer_id=company_account(company_id).pk, nature=Nature.OWNER_SALARY, due=salary,
                earned_at=at, policy=Policy.PENDING, reference_kind="owner_payroll", reference_id=f"{company_id}:{day}",
                tax_rate=params.INCOME_TAX_RATE, competence_day=day)
            if not submitted.ok:
                raise RuntimeError(f"folha do Dono da empresa {company_id}: {submitted.code} {submitted.detail}")
            keys.append(key)
        done = remuneration.liquidate_remuneration(batch=f"owner_payroll:{day}", at=at, keys=keys)
        if not done.ok:
            raise RuntimeError(f"liquidação da folha do dia {day}: {done.code} {done.detail}")
    return {"day": day, "settled": settled, "payroll": {"count": done.detail["count"], "processed": done.detail["processed"]}}


def _daily_tick(tick: Tick, ctx: Any) -> None:
    run_daily_payroll(tick.at)


def register() -> None:
    """Liga as Empresas ao Trabalho (hook + atividade) e ao tick diário do mundo. Chamado por `CompaniesConfig.ready`."""
    register_action_hook(WAGE_HOOK, pay_work_wage)
    register_activity_provider(ACTIVITY_PROVIDER, activity_for)
    ticks.register(ticks.WORLD, TickKind.DAILY, TICK_NAME, priority=50)(_daily_tick)
