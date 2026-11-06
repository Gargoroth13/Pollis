"""
Outbox durável da atividade (design/14a §3.6; decisão do GD, 2026-11-04). A menor estrutura que garante a integridade da
sequência de atividade — não é um barramento de eventos.

  gravação  `record_event` roda DENTRO da transação da ação (gravador do Action Registry): ação e evento são confirmados juntos;
            se o evento não puder ser gravado, a ação não é confirmada. Recusas não geram evento.
  processo  `process_player` atualiza `ActivityStreak` a partir dos eventos pendentes do jogador, em ordem `(at, id)`, sob a
            trava da linha do jogador: dois processadores nunca andam em paralelo no mesmo jogador, e um evento posterior nunca é
            processado enquanto houver um anterior pendente (uma falha PARA o jogador naquele evento e o deixa para retry).
  atomia    a atualização da sequência e a marcação `processed_at` acontecem no mesmo savepoint; reprocessar não duplica nada
            (`activity.record_action` ignora instantes não posteriores à última ação contada).
  falhas    deixam o evento pendente (`attempts`, `last_error`), sem desfazer a ação já confirmada; o próximo ciclo tenta de novo.
Quem processa: o tick do mundo (depois do commit) e `manage.py process_activity_outbox` (worker dedicado, retomável após
reinicialização) são os mecanismos de processamento EM SEGUNDO PLANO. Além deles há a passada imediata do próprio jogador:
`transaction.on_commit()` a executa no MESMO fluxo síncrono, logo depois do commit da ação e antes de a chamada retornar — não é
um worker assíncrono e seu custo é pago por quem agiu (melhor esforço: falha só é registrada; o evento já está durável).
Escalonamento justo (`next_candidates`): menos recentemente tentado primeiro, para que eventos com falha não ocupem as vagas do
lote; `process_pending` pula (`skip_locked`) jogadores que outro processador está tratando. Eventos NUNCA são removidos por
limpeza automática (decisão do GD, 2026-11-06: sem poda durante o Bot Test).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import F, Max, Min
from django.utils import timezone

from core import clock as game_clock
from core.instrument import QueryCounter
from players.models import Player

from . import activity, params
from .models import ActivityEvent

_log = logging.getLogger(__name__)


# --- gravação (dentro da transação da ação) ----------------------------------------------------------------------------------

def record_event(player_id: int, action_id: str, result, at: int) -> ActivityEvent:
    """Gravador do Action Registry: grava o evento obrigatório. Qualquer falha aqui desfaz a ação (exceção sobe)."""
    event = ActivityEvent.objects.create(player_id=player_id, action_id=action_id, at=at)
    if params.ACTIVITY_INLINE_PROCESSING:
        transaction.on_commit(lambda: _process_after_commit(player_id))
    return event


def _process_after_commit(player_id: int) -> None:
    """Passada imediata do jogador depois do commit da ação. Nunca levanta: o evento já está durável e o worker o recupera."""
    try:
        process_player(player_id)
    except Exception:    # noqa: BLE001
        _log.exception("outbox de atividade: passada imediata do jogador %s falhou (fica pendente)", player_id)


# --- processamento -----------------------------------------------------------------------------------------------------------

@dataclass
class PlayerResult:
    player_id: int
    processed: int = 0
    failed: int = 0
    remaining: int = 0          # pendentes que ficaram (por falha ou por limite do lote)


@dataclass
class RunSummary:
    players: int = 0
    skipped_locked: int = 0     # jogadores que outro processador estava tratando
    events_processed: int = 0
    events_failed: int = 0
    players_with_failures: int = 0
    duration_ms: float = 0.0
    queries: int = 0
    db_ms: float = 0.0
    pending_before: Optional[int] = None
    pending_after: Optional[int] = None
    per_player: List[PlayerResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "per_player"}
        d["events_per_second"] = round(self.events_processed / (self.duration_ms / 1000), 1) if self.duration_ms else None
        return d


def process_player(player_id: int, *, limit: Optional[int] = None, now: Optional[int] = None,
                   skip_if_locked: bool = False) -> Optional[PlayerResult]:
    """
    Processa os eventos pendentes do jogador em ordem. Toda a passada roda sob a trava da linha do jogador, lida DEPOIS de
    obtida a trava (o que outro processador confirmou nesse meio-tempo já aparece como processado). Cada evento tem o seu
    savepoint: a falha de um deixa os anteriores confirmados e PARA o jogador (sem pular para um evento posterior).
    `skip_if_locked` (usado pelo worker): se OUTRO processador (ou uma ação do jogador) segura a trava, devolve `None` em vez de
    esperar — o outro já cuida do jogador e o worker segue para o próximo candidato.
    """
    limit = params.ACTIVITY_OUTBOX_PLAYER_BATCH if limit is None else limit
    now = game_clock.now() if now is None else now
    out = PlayerResult(player_id)
    with transaction.atomic():
        locked = Player.objects.select_for_update(skip_locked=skip_if_locked).filter(pk=player_id).values_list("pk", flat=True).first()
        if locked is None:
            if skip_if_locked and Player.objects.filter(pk=player_id).exists():
                return None                                          # existe, mas está travado por outro
            return out                                               # jogador inexistente
        pending = list(ActivityEvent.objects.filter(player_id=player_id, processed_at__isnull=True)
                       .order_by("at", "id")[:limit])
        for event in pending:
            try:
                with transaction.atomic():
                    activity.record_action(player_id, event.at)
                    marked = (ActivityEvent.objects.filter(pk=event.pk, processed_at__isnull=True)
                              .update(processed_at=now, last_error=""))
                    if marked != 1:                                  # nunca deveria: a trava do jogador serializa
                        raise RuntimeError(f"evento {event.pk} já estava processado")
            except Exception as exc:    # noqa: BLE001 - a ação já foi confirmada; o evento fica pendente para retry
                ActivityEvent.objects.filter(pk=event.pk).update(
                    attempts=F("attempts") + 1, last_error=f"{type(exc).__name__}: {exc}"[:500], last_attempt_at=now,
                    attempted_wall_at=timezone.now())
                _log.warning("outbox de atividade: evento %s falhou (%s); jogador %s fica parado nele", event.pk, exc, player_id)
                out.failed = 1
                break
            out.processed += 1
        out.remaining = (0 if out.processed == len(pending) and not out.failed and len(pending) < limit else
                         ActivityEvent.objects.filter(player_id=player_id, processed_at__isnull=True).count())
    return out


def pending_count() -> int:
    return ActivityEvent.objects.filter(processed_at__isnull=True).count()


def next_candidates(exclude: set, limit: int) -> List[int]:
    """
    Escalonamento JUSTO: jogadores com evento pendente, **menos recentemente tentado primeiro** — quem nunca falhou (nenhuma
    tentativa registrada: `NULL`) vem antes de quem já falhou, desempatando pelo evento pendente mais antigo; entre os que já
    falharam, o de tentativa mais antiga vem primeiro (rodízio). Assim jogadores com eventos problemáticos não ocupam as vagas do
    lote indefinidamente nem impedem os saudáveis de progredir. Sem estado compartilhado: o estado do rodízio está nas linhas dos
    próprios eventos, então vários workers concordam sem coordenação.
    """
    qs = ActivityEvent.objects.filter(processed_at__isnull=True)
    if exclude:
        qs = qs.exclude(player_id__in=exclude)
    return list(qs.values("player_id").annotate(first=Min("id"), last_try=Max("attempted_wall_at"))
                .order_by(F("last_try").asc(nulls_first=True), "first").values_list("player_id", flat=True)[:limit])


def process_pending(*, max_players: Optional[int] = None, now: Optional[int] = None) -> RunSummary:
    """
    Uma passada do worker: até `max_players` jogadores com evento pendente, em ordem justa (`next_candidates`). Cada jogador em
    transação própria. Seguro com vários workers ao mesmo tempo: um jogador que outro processador está tratando é PULADO (não
    espera, não repete a tentativa) e a vaga é preenchida pelo próximo candidato. Jogadores que falham nesta passada contam
    para o limite e não são retentados nela (o rodízio os leva ao fim da fila). Nunca remove eventos.
    """
    max_players = params.ACTIVITY_OUTBOX_MAX_PLAYERS if max_players is None else max_players
    now = game_clock.now() if now is None else now
    summary = RunSummary()
    started = time.perf_counter()
    with QueryCounter() as q:
        summary.pending_before = pending_count()
        seen: set = set()
        while summary.players < max_players:
            batch = next_candidates(seen, max_players - summary.players)
            if not batch:
                break
            for pid in batch:
                seen.add(pid)
                r = process_player(pid, now=now, skip_if_locked=True)
                if r is None:
                    summary.skipped_locked += 1
                    continue
                summary.players += 1
                summary.events_processed += r.processed
                summary.events_failed += r.failed
                summary.players_with_failures += 1 if r.failed else 0
                summary.per_player.append(r)
        summary.pending_after = pending_count()
    summary.duration_ms = round((time.perf_counter() - started) * 1000, 2)
    summary.queries, summary.db_ms = q.count, round(q.db_seconds * 1000, 2)
    return summary
