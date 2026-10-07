"""
Serviços de Localização e Viagem. Jogadores reais e bots chamam as MESMAS funções (design/21).

Integração com o estado do jogador (players): nada é duplicado.
  - a localização inicial nasce num hook de criação do jogador;
  - o bloqueio de ações durante a viagem é um PROVEDOR DE BLOQUEIO consultado por players.services.perform_action;
  - partir usa players.services.locked_player (transação + trava + catch-up lazy);
  - a CHEGADA usa o sistema de tempo: handler no ciclo de 10 min (em ordem) + hook de acesso (instante exato).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Dict, List, Optional

from core import clock as game_clock
from core.breakdown import Explained
from geography import services as geo
from geography.balance import get_scenario
from geography.models import Lot
from players import services as player_services
from players.actions import Action
from players.hooks import ActivityContext
from players.models import Player
from players.services import ActionResult

from . import rules
from .balance import get_travel_balance
from .models import Journey, PlayerLocation


class WorldNotGenerated(Exception):
    """Não há nenhum lote: sem mundo não existe localização física válida para dar ao jogador."""


# --- localização inicial -----------------------------------------------------

InitialLocationProvider = Callable[[Player], Optional[Lot]]
_initial_providers: Dict[str, InitialLocationProvider] = {}


def register_initial_location_provider(name: str, fn: InitialLocationProvider) -> None:
    """
    04 §24: a localização inicial vem "das regras de Geografia e criação do jogador". Esse sistema de criação (contexto de
    nascimento, 01 §1) ainda não existe; quando existir, registra aqui o lote inicial. O primeiro provedor (por nome)
    que devolver um lote vence.
    """
    if name in _initial_providers:
        raise ValueError(f"Provedor de localização inicial duplicado: {name}")
    _initial_providers[name] = fn


def clear_initial_location_providers() -> None:  # para testes
    _initial_providers.clear()


def default_initial_lot() -> Optional[Lot]:
    """
    Padrão PROVISÓRIO enquanto não há sistema de criação: o PRIMEIRO lote do mundo em ordem territorial (estado, cidade,
    bairro, lote), determinístico. Não é regra de design: é só um lote válido e reproduzível.
    """
    return (Lot.objects.order_by("neighborhood__city__state_id", "neighborhood__city__index",
                                 "neighborhood__index", "index").first())


def resolve_initial_lot(player: Player) -> Lot:
    for name in sorted(_initial_providers):
        lot = _initial_providers[name](player)
        if lot is not None:
            return lot
    lot = default_initial_lot()
    if lot is None:
        raise WorldNotGenerated("Gere o mundo (manage.py generate_world) antes de criar jogadores.")
    return lot


def on_player_created(player: Player, now: int) -> None:
    """Hook de criação (dentro da transação de create_player): se falhar, o jogador não é criado."""
    PlayerLocation.objects.create(player=player, lot=resolve_initial_lot(player))


# --- bloqueio de ações durante a viagem -------------------------------------

def presence_block(player: Player, action: Action, now: int, activity: Optional[ActivityContext]) -> Optional[str]:
    """
    Provedor de bloqueio (04 §6, §20): enquanto viaja, o jogador não executa ação que dependa de presença física.
    Só ações que dependem de presença são recusadas; as demais seguem normalmente.
    """
    if not rules.requires_presence(action, activity, get_travel_balance()):
        return None
    if Journey.objects.filter(player=player, completed=False, arrives_at__gt=now).exists():
        return "TRAVELING"
    return None


# --- chegada (sistema de tempo) ---------------------------------------------

def complete_journey(journey: Journey) -> None:
    """Chegada: a localização passa a ser o destino. O instante de chegada É `arrives_at` (nunca o do acesso)."""
    PlayerLocation.objects.filter(player_id=journey.player_id).update(lot_id=journey.destination_id)
    journey.completed = True
    journey.save(update_fields=["completed"])


def settle_arrivals(player: Player, now: int) -> None:
    """Hook de acesso (On Access, 04 §22): conclui o que já chegou até `now`, mesmo entre dois ciclos."""
    for journey in Journey.objects.filter(player=player, completed=False, arrives_at__lte=now):
        complete_journey(journey)


# --- partir e consultar -------------------------------------------------------

def estimate_travel(origin: Lot, destination: Lot, at: Optional[int] = None) -> Explained:
    """Tempo-base entre dois lotes, com detalhamento (sem estado: serve para a interface mostrar antes de confirmar)."""
    sc = get_scenario()
    return rules.travel_time(geo.distance_between(origin, destination), sc.travel_minutes_per_unit, at)


def start_travel(player_id: int, destination_lot_id: int) -> ActionResult:
    """
    Inicia uma viagem do lote atual ao lote de destino. Recusas são CÓDIGOS (como em players), não exceções.
    Sem custo de Energia, Burnout ou dinheiro: o design não define nenhum.
    """
    tbal = get_travel_balance()
    with player_services.locked_player(player_id) as (player, now, _bal):
        origin = PlayerLocation.objects.select_related("lot").get(player=player).lot
        destination = Lot.objects.filter(pk=destination_lot_id).first()
        if destination is None:
            return ActionResult(False, "INVALID_DESTINATION", {"destination": destination_lot_id})
        if Journey.objects.filter(player=player, completed=False).exists():
            return ActionResult(False, "ALREADY_TRAVELING")
        blocked = rules.departure_block(player, now, tbal)
        if blocked is not None:
            return ActionResult(False, blocked)
        if destination.pk == origin.pk:
            return ActionResult(False, "SAME_LOCATION")
        time = estimate_travel(origin, destination, now)
        seconds = rules.duration_seconds(time.value)
        journey = Journey.objects.create(player=player, origin=origin, destination=destination,
                                         departed_at=now, arrives_at=now + seconds)
        return ActionResult(True, "OK", {"journey_id": journey.pk, "departed_at": now, "arrives_at": journey.arrives_at,
                                         "duration_seconds": seconds, "travel_time": time})


@dataclass(frozen=True)
class LocationState:
    at: int
    lot: Lot                          # onde está; em viagem, o lote de ORIGEM
    traveling: bool
    destination: Optional[Lot]
    departed_at: Optional[int]
    arrives_at: Optional[int]
    remaining_seconds: Optional[int]


def get_location(player_id: int) -> LocationState:
    """Sincroniza o jogador (conclui o que chegou) e devolve onde ele está e se está viajando."""
    player = player_services.sync_player(player_id)
    now = game_clock.now()
    lot = PlayerLocation.objects.select_related("lot").get(player=player).lot
    journey = Journey.objects.select_related("destination").filter(player=player, completed=False).first()
    if journey is None:
        return LocationState(now, lot, False, None, None, None, None)
    return LocationState(now, lot, True, journey.destination, journey.departed_at, journey.arrives_at,
                         max(0, journey.arrives_at - now))
