"""
Atribuição do imposto pago ao CONTRIBUINTE (design/14 §14.3.7; decisão do GD, 2026-11-03).

  • Imposto retido sobre REMUNERAÇÃO (`tax_income` lançado na mesma transação de um pagamento de remuneração, ou na quitação
    de obrigação de remuneração): o contribuinte é o jogador BENEFICIÁRIO, que suporta o imposto economicamente. A empresa ou
    o governo que apenas recolhe e remete NÃO recebe o crédito.
  • Demais impostos (`tax_sales`, `tax_property` e `tax_income` que não seja de remuneração): a conta pagadora do lançamento
    (`from_account`), a entidade efetivamente responsável pelo tributo.

Como o beneficiário é identificado (nunca por substituição global de `from_account`):
  1. natureza `tax_income` + a MESMA transação tem a perna líquida de natureza de remuneração (WAGE, MILITARY_PAY,
     OWNER_SALARY, POLITICAL_SALARY): beneficiário = conta de destino dessa perna;
  2. sem perna líquida (alíquota de 100%, nada líquido a pagar), pela REFERÊNCIA da transação: `remuneration:<pedido>` →
     `RemunerationRequest.player_id`; `settle:<lote>:<obrigação>` → credor de uma `Obligation` de remuneração;
  3. nenhuma das duas: fica a conta pagadora (e o caso é contado em `unresolved` para a auditoria).
Só jogadores e empresas entram no ranking.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from django.db.models import BigIntegerField, Case, CharField, Exists, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce

from ledger.constants import REMUNERATION_NATURES, TAX_NATURES, AccountKind, Nature
from ledger.models import Account, Entry, Obligation, RemunerationRequest

_REMUNERATION = [n.value for n in REMUNERATION_NATURES]
_KINDS = [AccountKind.PLAYER.value, AccountKind.COMPANY.value]
_INCOME = Nature.TAX_INCOME.value

Entity = Tuple[str, int]        # (kind da conta, owner_id)


def _window_entries(first_day: int, last_day: int):
    return Entry.objects.filter(nature__in=[n.value for n in TAX_NATURES], reversed_by__isnull=True,
                                competence_day__range=(first_day, last_day))


def _net_leg(field: str):
    return Subquery(Entry.objects.filter(transaction_id=OuterRef("transaction_id"), nature__in=_REMUNERATION)
                    .order_by("seq").values(field)[:1])


def taxpayer_totals(first_day: int, last_day: int) -> Tuple[Dict[Entity, int], int]:
    """Imposto efetivamente pago, por contribuinte, nos dias de competência `[first_day, last_day]`; e quantos não resolveram."""
    income = Q(nature=_INCOME)
    qs = (_window_entries(first_day, last_day)
          .annotate(payee_kind=Case(When(income, then=_net_leg("to_account__kind")), default=None, output_field=CharField()),
                    payee_owner=Case(When(income, then=_net_leg("to_account__owner_id")), default=None,
                                     output_field=BigIntegerField()))
          .annotate(tp_kind=Coalesce("payee_kind", "from_account__kind", output_field=CharField()),
                    tp_owner=Coalesce("payee_owner", "from_account__owner_id", output_field=BigIntegerField())))
    totals: Dict[Entity, int] = defaultdict(int)
    for r in (qs.filter(tp_kind__in=_KINDS).exclude(income & Q(payee_kind__isnull=True))
              .values("tp_kind", "tp_owner").annotate(total=Sum("amount"))):
        totals[(r["tp_kind"], r["tp_owner"])] += r["total"]
    # `tax_income` sem perna líquida: resolve pela referência da transação (alíquota de 100%)
    unresolved = 0
    for e in (_window_entries(first_day, last_day).filter(income)
              .annotate(has_net=Exists(Entry.objects.filter(transaction_id=OuterRef("transaction_id"), nature__in=_REMUNERATION)))
              .filter(has_net=False).select_related("transaction", "from_account")):
        entity = _resolve_by_reference(e.transaction.key)
        if entity is None:
            unresolved += 1
            entity = (e.from_account.kind, e.from_account.owner_id)
        if entity[0] in _KINDS:
            totals[entity] += e.amount
    return dict(totals), unresolved


def _resolve_by_reference(tx_key: str):
    if tx_key.startswith("remuneration:"):
        pid = RemunerationRequest.objects.filter(key=tx_key[len("remuneration:"):]).values_list("player_id", flat=True).first()
        return None if pid is None else (AccountKind.PLAYER.value, pid)
    if tx_key.startswith("settle:"):
        try:
            ob_id = int(tx_key.rsplit(":", 1)[1])
        except ValueError:
            return None
        ob = (Obligation.objects.filter(pk=ob_id, nature__in=_REMUNERATION).select_related("creditor").first())
        return None if ob is None else (ob.creditor.kind, ob.creditor.owner_id)
    return None


def ranked(totals: Dict[Entity, int]) -> List[Tuple[Entity, int]]:
    return sorted(totals.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][1]))
