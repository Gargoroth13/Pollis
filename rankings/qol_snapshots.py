"""
Melhor QoL pessoal (design/14 §14.3.4): snapshots periódicas com REFERÊNCIA DE TEMPO COMUM (decisão do GD, 2026-11-03).

A QoL não é guardada (players.qol): é função do estado do jogador em um instante. Para comparar jogadores é preciso o valor
de TODOS no MESMO instante `reference_at` (múltiplo do intervalo, padrão 1 h, alinhado ao ciclo de 10 min do 04).
Como cada instante é obtido, sem recalcular o mundo a cada acesso à página:
  1. `advance`: quando um jogador avança (ação, sync) atravessando um `reference_at` de snapshot ABERTA, o catch-up é dividido
     nesse instante (`players.hooks.register_checkpoint`) e a QoL é lida ali, ANTES de qualquer mudança posterior (uma ação, um
     efeito substituído). Assim jogadores ativos não deixam a snapshot incompleta por terem agido depois da referência.
  2. `sweep`: ao finalizar, os jogadores ainda não processados além da referência são levados até ela (`sync_player_until`,
     a MESMA `_catch_up` do 04: nenhuma regra duplicada) e capturados pelo mesmo caminho.
Uma snapshot só é COMPLETE quando todos os elegíveis (`created_at_game <= reference_at`) estão representados exatamente em
`reference_at`. Quem já tinha sido processado além da referência sem captura não tem valor reconstruível: a snapshot fica
INCOMPLETE (nunca se mistura instantes) e a página continua mostrando a última COMPLETE. Retenção: as últimas N COMPLETE.
"""
from __future__ import annotations

import contextvars
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from core import clock as game_clock
from core.timeline import SECONDS_PER_TEN_MINUTES, Tick
from players import hooks as player_hooks, qol
from players.models import Player
from players.services import sync_player_until

from . import params
from .models import QolSnapshot, QolSnapshotEntry

_log = logging.getLogger(__name__)
CHECKPOINT_NAME = "rankings_qol"
_source: contextvars.ContextVar[str] = contextvars.ContextVar("qol_capture_source", default="advance")
_QUANT = Decimal("1e-12")


def interval() -> int:
    value = params.QOL_SNAPSHOT_INTERVAL_SECONDS
    if not isinstance(value, int) or isinstance(value, bool) or value < SECONDS_PER_TEN_MINUTES \
            or value % SECONDS_PER_TEN_MINUTES:
        raise ValueError("o intervalo das snapshots de QoL deve ser múltiplo (inteiro, > 0) do ciclo de 10 minutos")
    return value


def reference_for(at: int) -> int:
    """Maior instante de referência (múltiplo do intervalo) menor ou igual a `at`."""
    i = interval()
    return (at // i) * i


def next_reference_after(at: int) -> int:
    i = interval()
    return (at // i + 1) * i


def _exact(value: Decimal) -> Decimal:
    q = value.quantize(_QUANT)
    if q != value:
        raise ValueError(f"QoL com mais de 12 casas decimais não é armazenável sem arredondar: {value}")
    return q


# --- captura ao avançar o jogador (checkpoint do catch-up) --------------------------------------------------------------

def _provider(player: Player, start: int, end: int) -> Sequence[int]:
    i = interval()
    first = (start // i + 1) * i
    if first > end:
        return []                                  # caminho comum: nenhum instante de referência atravessado, sem consulta
    # só as duas últimas referências atravessadas: quem ficou ausente por mais tempo é levado pelas varreduras já finalizadas
    instants = [t for t in range(first, end + 1, i) if t > end - 2 * i]
    if player.created_at_game > max(instants, default=0):
        return []
    open_refs = set(QolSnapshot.objects.filter(reference_at__in=instants, status=QolSnapshot.OPEN)
                    .values_list("reference_at", flat=True))
    known = set(QolSnapshot.objects.filter(reference_at__in=instants).values_list("reference_at", flat=True))
    wanted = []
    for t in instants:
        if t in open_refs:
            wanted.append(t)
        elif t not in known:
            _open(t, game_clock.now())             # a referência ainda não tinha linha (tick atrasado): abre agora
            wanted.append(t)
    return [t for t in wanted if player.created_at_game <= t]


def _capture(player: Player, at: int, bal) -> None:
    capture(player, at, bal, source=_source.get())


def capture(player: Player, reference_at: int, bal=None, source: str = "advance") -> bool:
    """Grava a QoL do jogador em `reference_at` (o jogador JÁ processado até lá). Idempotente; só em snapshot ABERTA."""
    snap = QolSnapshot.objects.filter(reference_at=reference_at, status=QolSnapshot.OPEN).first()
    if snap is None or player.created_at_game > reference_at:
        return False
    ex = qol.qol_current(player, reference_at, bal)
    value = _exact(ex.value)
    try:
        with transaction.atomic():
            QolSnapshotEntry.objects.create(snapshot=snap, player_id=player.pk, qol=value, explained=ex.to_dict(), source=source)
    except IntegrityError:
        return False                               # já havia entrada: o primeiro valor (exato) é o que vale
    return True


# --- ciclo de vida -------------------------------------------------------------------------------------------------------

def _open(reference_at: int, now: int) -> QolSnapshot:
    try:
        with transaction.atomic():
            return QolSnapshot.objects.get_or_create(reference_at=reference_at, defaults={"opened_at": now})[0]
    except IntegrityError:
        return QolSnapshot.objects.get(reference_at=reference_at)


def ensure_open(at: Optional[int] = None) -> QolSnapshot:
    """Garante que existe a snapshot da PRÓXIMA referência (aberta com antecedência, antes de qualquer jogador cruzá-la)."""
    at = game_clock.now() if at is None else at
    return _open(next_reference_after(at), at)


def finalize(reference_at: int, now: Optional[int] = None) -> QolSnapshot:
    """
    Finaliza uma snapshot ABERTA cujo instante já passou: varre os elegíveis sem entrada e marca COMPLETE ou INCOMPLETE.
    Cada jogador é processado em transação própria (sem segurar travas do mundo); retomável e idempotente.
    """
    now = game_clock.now() if now is None else now
    if reference_at > now:
        raise ValueError("a referência ainda não aconteceu")
    snap = QolSnapshot.objects.get(reference_at=reference_at)
    if snap.status != QolSnapshot.OPEN:
        return snap
    started = time.perf_counter()
    swept = skipped_beyond = 0
    with CaptureQueriesContext(connection) as queries:
        last_pk = 0
        while True:
            batch = list(Player.objects.filter(created_at_game__lte=reference_at, pk__gt=last_pk)
                         .exclude(pk__in=QolSnapshotEntry.objects.filter(snapshot=snap).values("player_id"))
                         .order_by("pk").values_list("pk", flat=True)[:params.QOL_SWEEP_BATCH])
            if not batch:
                break
            for pk in batch:
                token = _source.set("sweep")
                try:
                    p = sync_player_until(pk, reference_at)      # a captura acontece no checkpoint do catch-up
                    if p.processed_until == reference_at:        # já estava exatamente na referência: nada a atravessar
                        with transaction.atomic():
                            capture(Player.objects.select_for_update().get(pk=pk), reference_at, source="sweep")
                finally:
                    _source.reset(token)
                if p.processed_until > reference_at and not QolSnapshotEntry.objects.filter(snapshot=snap, player_id=pk).exists():
                    skipped_beyond += 1                          # processado além da referência sem captura: irrecuperável
                else:
                    swept += 1
            last_pk = batch[-1]
        with transaction.atomic():
            snap = QolSnapshot.objects.select_for_update().get(pk=snap.pk)
            if snap.status != QolSnapshot.OPEN:
                return snap
            eligible = Player.objects.filter(created_at_game__lte=reference_at).count()
            represented = QolSnapshotEntry.objects.filter(snapshot=snap).count()
            missing = eligible - represented
            by_source = {s: QolSnapshotEntry.objects.filter(snapshot=snap, source=s).count() for s in ("advance", "sweep")}
            snap.eligible, snap.represented, snap.missing = eligible, represented, missing
            snap.status = QolSnapshot.COMPLETE if missing == 0 else QolSnapshot.INCOMPLETE
            snap.finalized_at = now
            snap.metrics = {"duration_ms": round((time.perf_counter() - started) * 1000, 2),
                            "queries": len(queries), "swept_by_this_run": swept, "unrecoverable_in_this_run": skipped_beyond,
                            "entries_by_source": by_source, "lag_seconds": now - reference_at}
            snap.save()
    if snap.status != QolSnapshot.COMPLETE:
        _log.warning("snapshot de QoL %s INCOMPLETA: %s de %s jogadores sem valor exato", reference_at, missing, eligible)
    return snap


def prune(retain: Optional[int] = None) -> int:
    """Mantém as últimas N COMPLETE; apaga as COMPLETE mais antigas e as INCOMPLETE anteriores à mais antiga mantida."""
    retain = params.QOL_SNAPSHOT_RETAIN_COMPLETE if retain is None else retain
    if retain < 1:
        raise ValueError("retain deve ser >= 1")
    keep = list(QolSnapshot.objects.filter(status=QolSnapshot.COMPLETE).order_by("-reference_at")
                .values_list("reference_at", flat=True)[:retain])
    if len(keep) < retain:
        return 0
    oldest_kept = keep[-1]
    _, per_model = QolSnapshot.objects.filter(reference_at__lt=oldest_kept).exclude(status=QolSnapshot.OPEN).delete()
    return per_model.get(QolSnapshot._meta.label, 0)          # snapshots apagadas (as entradas saem em cascata)


def process_due(now: Optional[int] = None) -> List[QolSnapshot]:
    """Finaliza as snapshots abertas já vencidas, abre a próxima e aplica a retenção. Chamado FORA das transações do mundo."""
    now = game_clock.now() if now is None else now
    done = [finalize(ref, now) for ref in QolSnapshot.objects.filter(status=QolSnapshot.OPEN, reference_at__lte=now)
            .order_by("reference_at").values_list("reference_at", flat=True)]
    ensure_open(now)
    prune()
    return done


def world_tick(tick: Tick, context) -> None:
    """Tick de 10 min do mundo: abre a próxima referência (barato) e, DEPOIS do commit do mundo, finaliza as vencidas."""
    ensure_open(tick.at)
    if QolSnapshot.objects.filter(status=QolSnapshot.OPEN, reference_at__lte=tick.at).exists():
        at = tick.at
        transaction.on_commit(lambda: process_due(at))


def latest_complete() -> Optional[QolSnapshot]:
    return QolSnapshot.objects.filter(status=QolSnapshot.COMPLETE).order_by("-reference_at").first()


def connect() -> None:
    if CHECKPOINT_NAME not in player_hooks.checkpoint_names():
        player_hooks.register_checkpoint(CHECKPOINT_NAME, _provider, _capture)
