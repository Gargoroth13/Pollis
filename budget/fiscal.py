"""
Situação fiscal de um governo (09 §9-§11, §33; 24 §24.16): saldo, orçamento comprometido, receitas e despesas CLASSIFICADAS, e o teto de déficit.

Tudo é LEITURA do registro monetário (`ledger.Entry`, `Hold`, `Obligation`), nada é guardado aqui: o estado atual nunca substitui o log (09 §34).
Cada função devolve a estrutura de fatores junto com o valor (20; CLAUDE.md §6), não texto.

CLASSIFICAÇÃO (24 §24.16; `params.NOT_REVENUE`/`NOT_EXPENSE`): entrou na conta = receita, saiu = despesa, exceto o que o `24` manda não contar
(dotações, títulos, retido; transferências a níveis inferiores, principal da dívida). ESTORNO (`REVERSAL`) cancela a classificação do lançamento original.
JANELA: móvel de 360 dias, ou desde a abertura da conta se menor, referência anualizada; menos de 30 dias de histórico = o teto NÃO bloqueia.
HORIZONTE do compromisso novo (`C_360`): pagamentos nos 360 dias a partir de HOJE (inclusive).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from django.db.models import Q, Sum

from core import clock as game_clock
from core.breakdown import Calc, Explained
from ledger import services as ledger
from ledger.models import Account, Entry, Hold, Obligation
from ledger.constants import HoldStatus, Nature, ObligationStatus
from ledger.money import competence_day_of

from . import params, periods
from .constants import Level
from .govs import account_of


@dataclass(frozen=True)
class Flows:
    """Receitas e despesas contáveis de um intervalo de dias de competência (inclusive), por natureza e por categoria."""
    first_day: int
    last_day: int
    revenue: int
    expense: int
    revenue_by_nature: Dict[str, int]
    expense_by_nature: Dict[str, int]
    expense_by_category: Dict[str, int]
    excluded_revenue: Dict[str, int]
    excluded_expense: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {"first_day": self.first_day, "last_day": self.last_day, "revenue": self.revenue, "expense": self.expense,
                "surplus": self.revenue - self.expense, "revenue_by_nature": dict(self.revenue_by_nature),
                "expense_by_nature": dict(self.expense_by_nature), "expense_by_category": dict(self.expense_by_category),
                "excluded_revenue": dict(self.excluded_revenue), "excluded_expense": dict(self.excluded_expense)}


def _counts_revenue(nature: Nature) -> bool:
    return nature not in params.NOT_REVENUE


def _counts_expense(nature: Nature) -> bool:
    return nature not in params.NOT_EXPENSE


def flows(account_id: int, first_day: int, last_day: int) -> Flows:
    """Receitas/despesas contáveis do período; lê só `Entry` (imutável). Estorno cancela a classificação do original."""
    rev, exp = defaultdict(int), defaultdict(int)
    ex_rev, ex_exp, by_cat = defaultdict(int), defaultdict(int), defaultdict(int)
    base = Entry.objects.filter(competence_day__gte=first_day, competence_day__lte=last_day)
    for row in base.filter(to_account_id=account_id).exclude(nature=Nature.REVERSAL.value).values("nature").annotate(s=Sum("amount")):
        nature = Nature(row["nature"])
        (rev if _counts_revenue(nature) else ex_rev)[nature.value] += row["s"]
    out = base.filter(from_account_id=account_id).exclude(nature=Nature.REVERSAL.value)
    for row in out.values("nature", "category").annotate(s=Sum("amount")):
        nature = Nature(row["nature"])
        if _counts_expense(nature):
            exp[nature.value] += row["s"]
            by_cat[row["category"] or "uncategorized"] += row["s"]
        else:
            ex_exp[nature.value] += row["s"]
    for e in base.filter(nature=Nature.REVERSAL.value).filter(Q(to_account_id=account_id) | Q(from_account_id=account_id)).select_related("reverses"):
        orig = e.reverses
        if orig is None:
            continue
        nature = Nature(orig.nature)
        if e.to_account_id == account_id and orig.from_account_id == account_id:        # devolveu uma despesa
            if _counts_expense(nature):
                exp[nature.value] -= e.amount
                by_cat[orig.category or "uncategorized"] -= e.amount
            else:
                ex_exp[nature.value] -= e.amount
        elif e.from_account_id == account_id and orig.to_account_id == account_id:      # desfez uma receita
            (rev if _counts_revenue(nature) else ex_rev)[nature.value] -= e.amount
    clean = lambda d: {k: v for k, v in sorted(d.items()) if v != 0}
    return Flows(first_day, last_day, sum(rev.values()), sum(exp.values()), clean(rev), clean(exp), clean(by_cat), clean(ex_rev), clean(ex_exp))


def history_days(account: Account, today: int) -> int:
    """Dias de histórico da conta (a abertura e hoje contam)."""
    return max(0, today - competence_day_of(account.created_at) + 1)


def window_days(account: Account, today: int) -> int:
    """24 §24.16: 360 dias, ou desde a abertura da conta se menor."""
    return min(params.WINDOW_DAYS, history_days(account, today))


@dataclass(frozen=True)
class DeficitCheck:
    allowed: bool            # o novo compromisso cabe no teto (ou o teto ainda não bloqueia)
    blocking: bool           # o teto vale (≥ 30 dias de histórico)
    explained: Explained
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {"allowed": self.allowed, "blocking": self.blocking, "data": self.data, "explained": self.explained.to_dict()}


def commitment_360(schedule: Iterable[Tuple[int, int]], today: int) -> int:
    """C_360: soma dos pagamentos do cronograma `(dia, centavos)` dentro de [hoje, hoje + 359]."""
    return sum(amount for day, amount in schedule if today <= day < today + params.WINDOW_DAYS)


def deficit_check(level: Level, ident: int, schedule: Sequence[Tuple[int, int]] = (), at: Optional[int] = None,
                  ceiling_pct: Optional[Decimal] = None) -> DeficitCheck:
    """
    Teto de déficit (24 §24.16) para um NOVO compromisso discricionário com cronograma `schedule` (vazio = situação atual).
        R_ref = R × 360/n ; Δ_anual = (E − R) × 360/n ; Δ_proj = Δ_anual + C_360 ; exigido Δ_proj ≤ teto% × R_ref.
    A decisão usa aritmética RACIONAL exata; os passos mostram os valores em Decimal.
    """
    at = game_clock.now() if at is None else at
    today = competence_day_of(at)
    account = account_of(level, ident)
    pct = params.DEFICIT_CEILING_PCT if ceiling_pct is None else Decimal(ceiling_pct)
    n = window_days(account, today)
    c360 = commitment_360(schedule, today)
    if n <= 0:
        f = Flows(today, today, 0, 0, {}, {}, {}, {}, {})
        n_eff = 0
    else:
        f = flows(account.pk, today - n + 1, today)
        n_eff = n
    blocking = n_eff >= params.MIN_WINDOW_DAYS
    if n_eff > 0:
        ann = Fraction(params.WINDOW_DAYS, n_eff)
        r_ref = Fraction(f.revenue) * ann
        delta_annual = Fraction(f.expense - f.revenue) * ann
        limit = Fraction(pct) / 100 * r_ref
        delta_proj = delta_annual + c360
        within = delta_proj <= limit
    else:
        r_ref = delta_annual = limit = Fraction(0)
        delta_proj = Fraction(c360)
        within = True
    as_dec = lambda fr: Decimal(fr.numerator) / Decimal(fr.denominator)
    calc = (Calc("deficit_annualized", as_dec(delta_annual)).add("new_commitment_360", c360)
            .cap("deficit_ceiling", as_dec(limit)) if n_eff > 0 else Calc("deficit_annualized", 0).add("new_commitment_360", c360))
    explained = calc.result(at)
    data = {"window_days": n_eff, "history_days": history_days(account, today), "min_window_days": params.MIN_WINDOW_DAYS, "revenue_window": f.revenue,
            "expense_window": f.expense, "revenue_reference": str(as_dec(r_ref)), "deficit_annualized": str(as_dec(delta_annual)),
            "commitment_360": c360, "deficit_projected": str(as_dec(delta_proj)), "ceiling_pct": str(pct), "ceiling_limit": str(as_dec(limit)),
            "headroom": str(as_dec(limit - delta_proj)), "blocking": blocking, "within_ceiling": within,
            "restricted_by": "deficit_ceiling" if (not within and blocking) else None}
    return DeficitCheck(within or not blocking, blocking, explained, data)


# --- visão fiscal pública (09 §33) ------------------------------------------------------------------------------------------------

def commitments(account_id: int) -> List[Dict[str, Any]]:
    """Orçamento comprometido (09 §10): as reservas ativas da conta (24 §24.7)."""
    return [{"hold": h.pk, "amount": h.amount, "original": h.original_amount, "reference": [h.reference_kind, h.reference_id], "since": h.created_at}
            for h in Hold.objects.filter(account_id=account_id, status=HoldStatus.ACTIVE.value).order_by("pk")]


def fiscal_view(level: Level, ident: int, at: Optional[int] = None) -> Dict[str, Any]:
    """Os dados fiscais PÚBLICOS do governo (09 §33): situação, receitas e despesas do período de 30 dias, comprometido, teto de déficit."""
    at = game_clock.now() if at is None else at
    today = competence_day_of(at)
    account = account_of(level, ident)
    balance = ledger.balance_of(account.pk)
    held = commitments(account.pk)
    reserved = sum(h["amount"] for h in held)
    period = periods.period_of(today)
    first, last = periods.bounds_of(period)
    current = flows(account.pk, first, min(last, today))
    rolling = flows(account.pk, today - params.PERIOD_DAYS + 1, today)
    pending = ledger.pending_total(account.pk)
    return {
        "government": {"level": level.value, "id": ident, "account": account.pk, "opened_day": competence_day_of(account.created_at)},
        "position": {"balance": balance, "committed": reserved, "available": balance - reserved, "pending_obligations": pending,
                     "explained": Calc("gross_balance", balance).add("committed", -reserved).result(at).to_dict()},
        "commitments": held,
        "period": {"index": period, "first_day": first, "last_day": last, **current.to_dict()},
        "rolling_30_days": rolling.to_dict(),
        "deficit": deficit_check(level, ident, (), at).to_dict(),
        "public_debt": None,          # a dívida pública (títulos) vem na etapa seguinte da P1.09; None ≠ 0
    }


def ledger_log(level: Level, ident: int, limit: int = 50, before_seq: Optional[int] = None) -> List[Dict[str, Any]]:
    """Log financeiro público do governo (09 §34): lançamentos com origem, destino, valor, natureza, categoria, referência e saldos antes/depois."""
    account = account_of(level, ident)
    qs = Entry.objects.filter(Q(from_account_id=account.pk) | Q(to_account_id=account.pk))
    if before_seq is not None:
        qs = qs.filter(seq__lt=before_seq)
    out = []
    for e in qs.order_by("-seq")[:max(1, min(int(limit), 500))]:
        incoming = e.to_account_id == account.pk
        out.append({"seq": e.seq, "at": e.at, "competence_day": e.competence_day, "direction": "in" if incoming else "out",
                    "from_account": e.from_account_id, "to_account": e.to_account_id, "amount": e.amount, "nature": e.nature,
                    "category": e.category, "operation": e.operation, "reference": [e.reference_kind, e.reference_id],
                    "balance_before": e.to_balance_before if incoming else e.from_balance_before,
                    "balance_after": e.to_balance_after if incoming else e.from_balance_after})
    return out
