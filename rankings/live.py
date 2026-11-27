"""
Rankings ao vivo (design/14 §14.3) e a visão dos históricos. SÓ LEEM dados dos sistemas de origem (14.2): nada aqui cria
pontuação própria. Posições: valores iguais ocupam a MESMA posição (14.2); a ordem dentro do empate é só de exibição (id).

Cada linha: `rank`, `entity_type`, `entity_id`, `name`, `value` e `detail` (dado estruturado do que compõe o valor, doc 20).
Janelas (14.6): dias de competência FECHADOS `[hoje−N, hoje−1]`; o resultado não muda com o horário em que a página é aberta.
Categorias sem fonte na main devolvem `available=False` com o estado e a dependência, nunca valores inventados.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from django.db.models import Exists, F, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce

from core import clock as game_clock
from core.breakdown import Calc
from ledger.constants import AccountKind, ObligationStatus
from ledger.models import Account, Obligation
from ledger.money import competence_day_of
from players.models import Player

from . import display, params, qol_snapshots, taxes
from .constants import ENTITY_COMPANY, ENTITY_PLAYER, Cat, Group, Status, spec
from .models import ActivityStreak, RankingHistorico

_namers: Dict[str, Callable[[int], Optional[str]]] = {}


def register_entity_namer(entity_type: str, namer: Callable[[int], Optional[str]]) -> None:
    """Quem possui a entidade (empresas, escolas...) registra como nomeá-la; sem nomeador a página mostra `tipo #id`."""
    _namers[entity_type] = namer


def clear_entity_namers() -> None:           # para testes
    _namers.clear()


def entity_name(entity_type: str, entity_id: int, player_names: Optional[Dict[int, str]] = None) -> str:
    if entity_type == ENTITY_PLAYER:
        name = (player_names or {}).get(entity_id)
        if name is None:
            name = Player.objects.filter(pk=entity_id).values_list("user__username", flat=True).first()
        return name or f"jogador #{entity_id}"
    namer = _namers.get(entity_type)
    named = namer(entity_id) if namer else None
    return named or f"{entity_type} #{entity_id}"


def _player_names(ids) -> Dict[int, str]:
    return dict(Player.objects.filter(pk__in=list(ids)).values_list("pk", "user__username"))


def _limit(limit: Optional[int]) -> int:
    limit = params.PAGE_SIZE if limit is None else limit
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit inválido")
    return min(limit, params.MAX_PAGE_SIZE)


def assign_ranks(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """`rows` já em ordem decrescente de valor (ou crescente, para quem pede): empatados na mesma posição; a seguinte pula."""
    prev, prev_rank = object(), 0
    for i, row in enumerate(rows, start=1):
        if row["value"] != prev:
            prev, prev_rank = row["value"], i
        row["rank"] = prev_rank
    return rows


# --- patrimônio líquido (14.3.1) ----------------------------------------------------------------------------------------

def net_worth_explained(balance: int, receivable: int, owed: int, at: int):
    """
    Patrimônio líquido = saldo bruto + créditos a receber − obrigações a pagar (decisão do GD, 2026-11-03).
      saldo bruto         `Account.balance`, inclui o reservado (o dinheiro continua do jogador)
      créditos a receber  restante (`amount_due − amount_paid`) das obrigações ABERTAS em que o jogador é credor
      obrigações a pagar  restante das obrigações ABERTAS em que o jogador é devedor
    Obrigações pagas ou canceladas não entram. Só o que o ledger reconhece: sem imóveis, empresas ou estoque, que dependem de
    regras de avaliação dos sistemas donos. Valor em centavos, exato; pode ser negativo.
    """
    return Calc("balance", balance).add("receivables", receivable).add("open_obligations", -owed).result(at)


def _open_sum(side: str):
    """Soma do restante das obrigações abertas em que a conta (OuterRef pk) é `debtor` ou `creditor`."""
    return (Obligation.objects.filter(**{side: OuterRef("pk")}, status=ObligationStatus.OPEN.value)
            .values(side).annotate(s=Sum(F("amount_due") - F("amount_paid"))).values("s"))


def _player_accounts():
    return (Account.objects.filter(kind=AccountKind.PLAYER.value, closed=False)
            .filter(Exists(Player.objects.filter(pk=OuterRef("owner_id"))))
            .annotate(owed=Coalesce(Subquery(_open_sum("debtor")), 0), receivable=Coalesce(Subquery(_open_sum("creditor")), 0),
                      net=F("balance") + F("receivable") - F("owed")))


def net_worth_components(balance: int, receivable: int, owed: int) -> Dict[str, Any]:
    """
    Detalhamento SEPARADO do patrimônio (decisão do GD, 2026-11-04): créditos a receber e obrigações a pagar aparecem cada um no
    seu lado, com as regras condicionais que se aplicam. Chaves estáveis (a UI traduz); valores em centavos.
      receivables_nominal_value  o crédito conta pelo valor NOMINAL restante: sem desconto de solvência/inadimplência e sem
                                 garantia de recuperação (não há provisão para devedores duvidosos nesta versão).
    """
    return {"balance": balance, "receivables": receivable, "obligations_payable": owed,
            "rules": [{"key": "receivables_nominal_value", "applies": receivable > 0},
                      {"key": "paid_and_cancelled_obligations_excluded", "applies": True}]}


def _net_worth_payload(row: Dict[str, Any], at: int) -> Dict[str, Any]:
    ex = net_worth_explained(row["balance"], row["receivable"], row["owed"], at)
    return {"value": row["net"], "balance": row["balance"], "receivables": row["receivable"], "obligations_open": row["owed"],
            "components": net_worth_components(row["balance"], row["receivable"], row["owed"]), "explained": ex.to_dict()}


_NW_FIELDS = ("owner_id", "balance", "receivable", "owed", "net")


def net_worth_of(player_id: int, at: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Patrimônio líquido do jogador com o detalhamento; None se o jogador não tem conta no ledger (ausente ≠ zero)."""
    at = game_clock.now() if at is None else at
    row = _player_accounts().filter(owner_id=player_id).values(*_NW_FIELDS).first()
    return None if row is None else _net_worth_payload(row, at)


def net_worth_of_accounts(account_ids, at: Optional[int] = None) -> List[Dict[str, Any]]:
    """Patrimônio líquido dos jogadores donos das contas (as que não são de jogador são ignoradas), do maior ao menor."""
    at = game_clock.now() if at is None else at
    rows = _player_accounts().filter(pk__in=list(account_ids)).order_by("-net", "owner_id").values(*_NW_FIELDS)
    return [{"player_id": r["owner_id"], **_net_worth_payload(r, at)} for r in rows]


def net_worth_rows(limit: Optional[int] = None, at: Optional[int] = None) -> List[Dict[str, Any]]:
    at = game_clock.now() if at is None else at
    rows = list(_player_accounts().order_by("-net", "owner_id").values(*_NW_FIELDS)[:_limit(limit)])
    names = _player_names(r["owner_id"] for r in rows)
    out = [{"entity_type": ENTITY_PLAYER, "entity_id": r["owner_id"], "name": entity_name(ENTITY_PLAYER, r["owner_id"], names),
            "value": r["net"], "detail": {**net_worth_explained(r["balance"], r["receivable"], r["owed"], at).to_dict(),
                                          "components": net_worth_components(r["balance"], r["receivable"], r["owed"])}}
           for r in rows]
    return assign_ranks(out)


# --- maior contribuinte (14.3.7) ----------------------------------------------------------------------------------------

def taxpayer_window(at: int) -> Dict[str, int]:
    today = competence_day_of(at)
    return {"first_day": today - params.TAXPAYER_WINDOW_DAYS, "last_day": today - 1, "days": params.TAXPAYER_WINDOW_DAYS}


def taxpayer_rows(limit: Optional[int] = None, at: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Imposto EFETIVAMENTE pago (lançamento `tax_*` não estornado) por contribuinte na janela. Atribuição em `rankings.taxes`:
    o imposto retido sobre remuneração é do jogador beneficiário; os demais, da conta pagadora (jogador ou empresa).
    """
    at = game_clock.now() if at is None else at
    w = taxpayer_window(at)
    totals, unresolved = taxes.taxpayer_totals(w["first_day"], w["last_day"])
    top = taxes.ranked(totals)[:_limit(limit)]
    names = _player_names(owner for (kind, owner), _ in top if kind == AccountKind.PLAYER.value)
    out = []
    for (kind, owner), total in top:
        et = ENTITY_PLAYER if kind == AccountKind.PLAYER.value else ENTITY_COMPANY
        out.append({"entity_type": et, "entity_id": owner, "name": entity_name(et, owner, names), "value": total,
                    "detail": {"window": w, "source": "ledger.Entry tax_*", "unresolved_in_window": unresolved}})
    return assign_ranks(out)


# --- conta mais antiga (14.3.10) ----------------------------------------------------------------------------------------

def oldest_account_rows(limit: Optional[int] = None, at: Optional[int] = None) -> List[Dict[str, Any]]:
    """Idade = agora − criação da conta; não exige atividade. Valores iguais ⇔ mesmo instante de criação."""
    at = game_clock.now() if at is None else at
    rows = list(Player.objects.order_by("created_at_game", "pk").values("pk", "created_at_game", "user__username")[:_limit(limit)])
    out = [{"entity_type": ENTITY_PLAYER, "entity_id": r["pk"], "name": r["user__username"], "value": at - r["created_at_game"],
            "detail": {"created_at": r["created_at_game"], "now": at}} for r in rows]
    return assign_ranks(out)


# --- maior tempo ativo (14.3.11) ----------------------------------------------------------------------------------------

def active_time_rows(limit: Optional[int] = None, at: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Ao vivo (decisão do GD, 2026-11-03): ordena pela sequência CORRENTE. Só entram contas cuja sequência ainda está ativa
    (intervalo desde a última ação INFERIOR a 72 h). Valor = `consulta − current_start`. O recorde histórico (14.4.3) usa a
    melhor sequência já alcançada (`best_length`): as duas categorias têm finalidades distintas.
    """
    at = game_clock.now() if at is None else at
    rows = list(ActivityStreak.objects.filter(last_action_at__gt=at - params.STREAK_MAX_GAP_SECONDS, current_start__lte=at)
                .order_by("current_start", "player_id")
                .values("player_id", "player__user__username", "best_start", "best_end", "best_length", "current_start",
                        "last_action_at")[:_limit(limit)])
    out = [{"entity_type": ENTITY_PLAYER, "entity_id": r["player_id"], "name": r["player__user__username"],
            "value": at - r["current_start"],
            "detail": {"current_start": r["current_start"], "last_action_at": r["last_action_at"], "as_of": at,
                       "best_start": r["best_start"], "best_end": r["best_end"], "best_length": r["best_length"],
                       "max_gap_seconds": params.STREAK_MAX_GAP_SECONDS}} for r in rows]
    return assign_ranks(out)


def qol_rows(limit: Optional[int] = None, at: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Melhor QoL pessoal: SÓ a última snapshot COMPLETA (todos os elegíveis no mesmo `reference_at`). Nunca mistura instantes e
    nunca recalcula jogadores no acesso. Sem snapshot completa ainda: lista vazia (não há valor comparável a mostrar).
    """
    snap = qol_snapshots.latest_complete()
    if snap is None:
        return []
    rows = list(snap.entries.order_by("-qol", "player_id").values("player_id", "player__user__username", "qol", "explained")
                [:_limit(limit)])
    out = [{"entity_type": ENTITY_PLAYER, "entity_id": r["player_id"], "name": r["player__user__username"], "value": r["qol"],
            "detail": {"reference_at": snap.reference_at, "explained": r["explained"]}} for r in rows]
    return assign_ranks(out)


_ROWS = {
    Cat.QOL: qol_rows,
    Cat.NET_WORTH: net_worth_rows,
    Cat.TAXPAYER: taxpayer_rows,
    Cat.OLDEST_ACCOUNT: oldest_account_rows,
    Cat.ACTIVE_TIME: active_time_rows,
}


def _meta(category: Cat) -> Dict[str, Any]:
    s = spec(category)
    return {"category": s.key.value, "number": s.number, "label": s.label, "design_ref": s.design_ref, "group": s.group.value,
            "status": s.status.value, "unit": s.unit, "window_days": s.window_days, "source": s.source, "depends_on": s.depends_on}


def live_ranking(category, limit: Optional[int] = None, at: Optional[int] = None) -> Dict[str, Any]:
    """Um ranking ao vivo. Categoria histórica ou inexistente → ValueError; pendente/fora de escopo → `available=False`."""
    s = spec(category)
    if s.group != Group.LIVE:
        raise ValueError(f"{s.key.value} é um ranking histórico")
    at = game_clock.now() if at is None else at
    out = _meta(s.key)
    fn = _ROWS.get(s.key)
    if s.status != Status.ACTIVE or fn is None:
        return {**out, "available": False, "as_of": at, "entries": []}
    entries = fn(limit=limit, at=at)
    for e in entries:
        e["display"] = display.fmt(s.unit, e["value"])
        comp = (e.get("detail") or {}).get("components")
        if comp is not None:                       # patrimônio: valores formatados de cada parcela, para a tela
            comp["display"] = {k: display.fmt_centavos(comp[k]) for k in ("balance", "receivables", "obligations_payable")}
    out.update({"available": True, "as_of": at, "entries": entries})
    if s.key == Cat.TAXPAYER:
        out["window"] = taxpayer_window(at)
    if s.key == Cat.QOL:
        snap = qol_snapshots.latest_complete()
        out["snapshot"] = None if snap is None else {
            "reference_at": snap.reference_at, "finalized_at": snap.finalized_at, "players": snap.represented,
            "interval_seconds": params.QOL_SNAPSHOT_INTERVAL_SECONDS}
        out["as_of"] = at if snap is None else snap.reference_at     # a QoL mostrada é a do instante de referência
    return out


def historical_ranking(category) -> Dict[str, Any]:
    """Um recorde histórico: o registro atual (ou None, se ainda não houve) com entidade, valor, data e metadados."""
    s = spec(category)
    if s.group != Group.HISTORICAL:
        raise ValueError(f"{s.key.value} é um ranking ao vivo")
    out = _meta(s.key)
    rec = RankingHistorico.objects.filter(category=s.key.value).first()
    out["available"] = s.status == Status.ACTIVE
    out["record"] = None if rec is None else {
        "entity_type": rec.entity_type, "entity_id": rec.entity_id, "name": entity_name(rec.entity_type, rec.entity_id),
        "value": rec.value, "display": display.fmt(s.unit, rec.value), "recorded_at": rec.recorded_at,
        "updated_at": rec.updated_at, "metadata": rec.metadata}
    return out


def page_data(limit: Optional[int] = None, at: Optional[int] = None) -> Dict[str, Any]:
    """Tudo que a página pública mostra, separado em ao vivo e histórico (14.8)."""
    from .constants import HISTORICAL, LIVE
    at = game_clock.now() if at is None else at
    return {"as_of": at, "live": [live_ranking(c.key, limit, at) for c in LIVE],
            "historical": [historical_ranking(c.key) for c in HISTORICAL]}
