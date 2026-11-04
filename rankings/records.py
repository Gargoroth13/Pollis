"""
Rankings históricos (design/14 §14.4–14.5): o recorde atual de cada categoria, em `RankingHistorico`.

Regras comuns (14.4): substituição só por valor ESTRITAMENTE maior (em empate fica quem chegou primeiro); a queda posterior do
valor atual nunca apaga o recorde; o registro guarda a entidade, o valor, quando foi estabelecido e metadados de auditoria.

Concorrência: o recorde é uma única linha por categoria; a decisão "é maior?" é tomada sob `select_for_update` da própria linha
(e a criação concorrente cai no `UNIQUE(category)`). Ordem de travas: Player → ActivityStreak → RankingHistorico.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable, Dict, Optional

from django.db import IntegrityError, transaction
from django.db.models import F

from core import clock as game_clock

from .constants import ENTITY_PLAYER, Cat
from .models import NetWorthCandidate, RankingHistorico

_log = logging.getLogger(__name__)

PPM = 1_000_000                       # o percentual presidencial é guardado em partes por milhão (piso); a comparação é exata


@dataclass(frozen=True)
class RecordOutcome:
    changed: bool
    record: Optional[RankingHistorico]
    reason: str                       # CREATED | REPLACED | NOT_GREATER


def beats(value: int, at: int, rec: Optional[RankingHistorico]) -> bool:
    """Supera o recorde: valor estritamente maior; em empate, só quem o alcançou ANTES (quem chegou primeiro fica)."""
    return rec is None or value > rec.value or (value == rec.value and at < rec.recorded_at)


def current(category: Cat) -> Optional[RankingHistorico]:
    return RankingHistorico.objects.filter(category=Cat(category).value).first()


def _offer(category: Cat, fields: Dict[str, Any], is_better: Callable[[RankingHistorico], bool], at: int) -> RecordOutcome:
    now = max(game_clock.now(), at)
    with transaction.atomic():
        rec = RankingHistorico.objects.select_for_update().filter(category=category.value).first()
        if rec is None:
            try:
                with transaction.atomic():
                    rec = RankingHistorico.objects.create(category=category.value, recorded_at=at, updated_at=now, **fields)
                return RecordOutcome(True, rec, "CREATED")
            except IntegrityError:          # outra transação criou entre a leitura e o insert: decide sob trava
                rec = RankingHistorico.objects.select_for_update().get(category=category.value)
        if not is_better(rec):
            return RecordOutcome(False, rec, "NOT_GREATER")
        for name, value in fields.items():
            setattr(rec, name, value)
        rec.recorded_at, rec.updated_at = at, now
        rec.save()
        return RecordOutcome(True, rec, "REPLACED")


def offer_value_record(category: Cat, entity_type: str, entity_id: int, value: int, at: int,
                       metadata: Optional[Dict[str, Any]] = None) -> RecordOutcome:
    """Recorde por valor inteiro. Só cria/substitui se `value` for estritamente maior que o atual."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return RecordOutcome(False, current(category), "NOT_GREATER")       # nada a registrar: zero/negativo não é recorde
    fields = {"entity_type": entity_type, "entity_id": entity_id, "value": value, "metadata": metadata or {}}
    return _offer(Cat(category), fields, lambda rec: beats(value, at, rec), at)


# --- patrimônio líquido (14.4.1) ----------------------------------------------------------------------------------------

def _net_worth_candidate(nw: Dict[str, Any], at: int):
    return {"balance": nw["balance"], "receivables": nw["receivables"], "obligations_open": nw["obligations_open"],
            "explained": nw["explained"]}


def check_net_worth_record(player_id: int, at: Optional[int] = None) -> RecordOutcome:
    """Compara o patrimônio líquido ATUAL do jogador com o recorde. Barato quando não há recorde novo (leitura sem trava)."""
    from . import live
    at = game_clock.now() if at is None else at
    nw = live.net_worth_of(player_id, at)
    if nw is None:
        return RecordOutcome(False, current(Cat.NET_WORTH_RECORD), "NOT_GREATER")
    value = int(nw["value"])
    rec = current(Cat.NET_WORTH_RECORD)
    if not beats(value, at, rec):
        return RecordOutcome(False, rec, "NOT_GREATER")
    return offer_value_record(Cat.NET_WORTH_RECORD, ENTITY_PLAYER, player_id, value, at, _net_worth_candidate(nw, at))


def on_ledger_operation(account_ids, at: int) -> None:
    """
    Gancho de FIM DE OPERAÇÃO do ledger (`ledger.hooks`): roda dentro da transação da operação financeira COMPLETA, com o
    estado final (saldos e obrigações já atualizados), para todo jogador cujo patrimônio pode ter mudado — inclusive por
    operações automáticas (remuneração, quitação, impostos, abertura/cancelamento de obrigação).
    Confiabilidade: se gravar o recorde falhar, o candidato (valor e instante da operação) é gravado DURAVELMENTE na mesma
    transação e reaplicado depois; se nem isso for possível, o erro propaga e a operação inteira é desfeita. Nunca se
    descarta uma atualização em silêncio.
    """
    from . import live
    for nw in live.net_worth_of_accounts(account_ids, at):
        value = int(nw["value"])
        if value <= 0 or not beats(value, at, current(Cat.NET_WORTH_RECORD)):
            continue
        meta = _net_worth_candidate(nw, at)
        try:
            with transaction.atomic():
                offer_value_record(Cat.NET_WORTH_RECORD, ENTITY_PLAYER, nw["player_id"], value, at, meta)
        except Exception as exc:    # noqa: BLE001 - nada se perde: o candidato fica gravado para reaplicação
            _log.exception("recorde de patrimônio não gravado (player=%s valor=%s); candidato durável criado", nw["player_id"], value)
            NetWorthCandidate.objects.create(player_id=nw["player_id"], value=value, at=at, metadata=meta,
                                             last_error=f"{type(exc).__name__}: {exc}"[:200])


def drain_net_worth_candidates(limit: Optional[int] = None) -> int:
    """Reaplica os candidatos pendentes em ordem cronológica; remove os aplicados. Devolve quantos foram resolvidos."""
    done = 0
    for pk in list(NetWorthCandidate.objects.order_by("at", "id").values_list("pk", flat=True)[:limit]):
        try:
            with transaction.atomic():
                cand = NetWorthCandidate.objects.select_for_update().filter(pk=pk).first()
                if cand is None:            # outro processo já resolveu
                    continue
                offer_value_record(Cat.NET_WORTH_RECORD, ENTITY_PLAYER, cand.player_id, cand.value, cand.at, cand.metadata)
                cand.delete()
                done += 1
        except Exception as exc:    # noqa: BLE001 - permanece pendente, com a contagem de tentativas
            _log.exception("candidato de recorde de patrimônio %s não reaplicado", pk)
            NetWorthCandidate.objects.filter(pk=pk).update(attempts=F("attempts") + 1, last_error=f"{type(exc).__name__}: {exc}"[:200])
    return done


def sweep_net_worth_record(at: Optional[int] = None) -> RecordOutcome:
    """
    Reconciliação (tick diário): reaplica candidatos pendentes e confere o MAIOR patrimônio atual contra o recorde (uma
    consulta). O recorde em si é mantido pelo gancho do ledger; isto só pega o que escapou (e é o que `audit_rankings` aponta).
    """
    from . import live
    at = game_clock.now() if at is None else at
    drain_net_worth_candidates()
    rows = live.net_worth_rows(limit=1, at=at)
    if not rows:
        return RecordOutcome(False, current(Cat.NET_WORTH_RECORD), "NOT_GREATER")
    return check_net_worth_record(rows[0]["entity_id"], at)


# --- maior tempo ativo (14.4.3) -----------------------------------------------------------------------------------------

def check_active_time_record(streak) -> RecordOutcome:
    rec = current(Cat.ACTIVE_TIME_RECORD)
    if not beats(streak.best_length, streak.best_end, rec):
        return RecordOutcome(False, rec, "NOT_GREATER")
    return offer_value_record(Cat.ACTIVE_TIME_RECORD, ENTITY_PLAYER, streak.player_id, streak.best_length, streak.best_end,
                              {"start": streak.best_start, "end": streak.best_end, "length_seconds": streak.best_length})


# --- presidente com maior percentual de votos (14.4.4) ------------------------------------------------------------------

def record_presidential_result(president_player_id: int, election_ref: str, votes: int, total_votes: int,
                               election_date: int) -> RecordOutcome:
    """
    INTERFACE para a integração futura com a Política (P1.11): nenhum sistema a chama ainda e nenhuma eleição é inventada.
    O percentual é `votes / total_votes` (resultado efetivamente registrado); substitui o recorde só se for estritamente maior
    (comparação exata por fração). Guarda presidente, eleição, votos, total, percentual e data da eleição (14.4.4).
    """
    ints = (president_player_id, votes, total_votes, election_date)
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in ints):
        raise ValueError("presidente, votos, total e data devem ser inteiros")
    if not isinstance(election_ref, str) or not election_ref:
        raise ValueError("eleição obrigatória")
    if total_votes <= 0 or not 0 <= votes <= total_votes:
        raise ValueError("votos devem estar entre 0 e o total de votos contabilizados (> 0)")
    value = votes * PPM // total_votes
    metadata = {"election": election_ref, "votes": votes, "total_votes": total_votes,
                "percent": f"{Fraction(votes * 100, total_votes).limit_denominator(10**9)}", "election_date": election_date}
    fields = {"entity_type": ENTITY_PLAYER, "entity_id": president_player_id, "value": value, "metadata": metadata}

    def better(rec: RankingHistorico) -> bool:
        return Fraction(votes, total_votes) > Fraction(rec.metadata["votes"], rec.metadata["total_votes"])

    return _offer(Cat.PRESIDENT_VOTE_RECORD, fields, better, election_date)
