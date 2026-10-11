"""
Serviços de Localização e Viagem. Jogadores reais e bots chamam as MESMAS funções (design/21).

Integração com o estado do jogador (players): nada é duplicado.
  - a localização inicial nasce num hook de criação do jogador;
  - o bloqueio de ações durante a viagem é um PROVEDOR DE BLOQUEIO consultado por players.services.perform_action;
  - partir usa players.services.locked_player (transação + trava + catch-up lazy);
  - a CHEGADA usa o sistema de tempo: handler no ciclo de 10 min (em ordem) + hook de acesso (instante exato);
  - o CUSTO monetário é calculado aqui e entregue ao sistema de dinheiro por um ponto de integração (payment handler).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Tuple

from core import clock as game_clock
from core.breakdown import Explained
from geography import services as geo
from geography.balance import get_scenario
from geography.models import Lot, State
from players import services as player_services
from players.actions import Action
from players.hooks import ActivityContext
from players.models import Player
from players.services import ActionResult

from . import rules
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
    Decisão do GD (2026-10-07): o jogador começa na CAPITAL. Primeiro lote territorial (determinístico) da cidade
    capital do primeiro estado. Sem distribuição aleatória de spawn. A moradia inicial é garantida, básica, neutra em QoL e
    NÃO consome capacidade dos lotes nem da população: por isso nada é reservado nem contado aqui, e vários jogadores
    na capital não são problema de capacidade. Fallbacks (mundo sem capital definida / capital sem lotes): o primeiro lote
    do mundo, para sempre devolver um lote válido.
    """
    order = ("neighborhood__index", "index")
    state = State.objects.exclude(capital=None).order_by("id").first()
    if state is not None:
        lot = Lot.objects.filter(neighborhood__city_id=state.capital_id).order_by(*order).first()
        if lot is not None:
            return lot
    return Lot.objects.order_by("neighborhood__city__state_id", "neighborhood__city__index", *order).first()


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
    Só ações que dependem de presença são recusadas (Trabalho e Estudo; ver rules.PRESENCE_BY_ACTION); as demais seguem
    normalmente. Roda ANTES de energia, skills e demais efeitos, pois é um provedor de bloqueio.
    """
    if not rules.requires_presence(action, activity):
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


# --- modificadores futuros e pagamento --------------------------------------

@dataclass(frozen=True)
class TravelModifier:
    """
    Ponto de extensão para veículos, estradas, transporte público (04 §21, hoje inexistentes). Fatores MULTIPLICATIVOS sobre
    o tempo-base e o custo-base. `fn(player, origin, destination)` devolve o modificador a aplicar ou None. Ex.: um veículo
    devolve TravelModifier("vehicle", time_factor=0.5, cost_factor=0.3).
    """
    name: str
    time_factor: Decimal = Decimal(1)
    cost_factor: Decimal = Decimal(1)


ModifierProvider = Callable[[Optional[Player], Lot, Lot], Optional[TravelModifier]]
_modifier_providers: Dict[str, ModifierProvider] = {}


def register_travel_modifier(name: str, fn: ModifierProvider) -> None:
    if name in _modifier_providers:
        raise ValueError(f"Modificador de viagem duplicado: {name}")
    _modifier_providers[name] = fn


def unregister_travel_modifier(name: str) -> None:
    _modifier_providers.pop(name, None)


# Ponto de integração com o sistema de DINHEIRO (inexistente hoje). `fn(player, amount, journey_context) -> bool`: True se
# debitou, False se saldo insuficiente. Sem handler, o custo é calculado e registrado (Journey.cost) mas NÃO cobrado.
PaymentHandler = Callable[[Player, Decimal, Dict], bool]
_payment_handler: Optional[Tuple[str, PaymentHandler]] = None


def register_payment_handler(name: str, fn: PaymentHandler) -> None:
    global _payment_handler
    if _payment_handler is not None:
        raise ValueError(f"Já existe um handler de pagamento de viagem: {_payment_handler[0]}")
    _payment_handler = (name, fn)


def unregister_payment_handler(name: str) -> None:
    global _payment_handler
    if _payment_handler is not None and _payment_handler[0] == name:
        _payment_handler = None


# --- partir e consultar -------------------------------------------------------

@dataclass(frozen=True)
class TravelQuote:
    time: Explained            # minutos de jogo, com detalhamento
    cost: Explained            # dinheiro, com detalhamento (não arredondado)
    duration_seconds: int
    amount: Decimal            # custo a cobrar, em centavos


def quote_travel(origin: Lot, destination: Lot, at: Optional[int] = None, player: Optional[Player] = None) -> TravelQuote:
    """Tempo e custo entre dois lotes (sem estado: serve à interface para mostrar antes de confirmar e a bots)."""
    sc = get_scenario()
    distance = geo.distance_between(origin, destination)
    time_mods: List[rules.Modifier] = []
    cost_mods: List[rules.Modifier] = []
    for name in sorted(_modifier_providers):
        m = _modifier_providers[name](player, origin, destination)
        if m is not None:
            time_mods.append((m.name, m.time_factor))
            cost_mods.append((m.name, m.cost_factor))
    time = rules.travel_time(distance, sc.travel_minutes_per_unit, at, time_mods)
    cost = rules.travel_cost(distance, sc.travel_cost_per_unit, at, cost_mods)
    return TravelQuote(time, cost, rules.duration_seconds(time.value), rules.charge_amount(cost.value))


def estimate_travel(origin: Lot, destination: Lot, at: Optional[int] = None) -> Explained:
    """Tempo-base entre dois lotes, com detalhamento (compatível com o P0.06.1 inicial)."""
    return quote_travel(origin, destination, at).time


def start_travel(player_id: int, destination_lot_id: int) -> ActionResult:
    """
    Inicia uma viagem do lote atual ao lote de destino. Recusas são CÓDIGOS (como em players), não exceções.
    NENHUM estado do jogador impede partir (decisão do GD, 2026-10-07): hospitalizado, saúde crítica e burnout ativo podem
    viajar (p.ex. em busca de tratamento). Sem custo de Energia ou Burnout; custo MONETÁRIO sim (ver quote_travel).
    Recusas: INVALID_DESTINATION, ALREADY_TRAVELING, SAME_LOCATION, INSUFFICIENT_FUNDS (só com handler de pagamento).
    """
    with player_services.locked_player(player_id) as (player, now, _bal):
        origin = PlayerLocation.objects.select_related("lot").get(player=player).lot
        destination = Lot.objects.filter(pk=destination_lot_id).first()
        if destination is None:
            return ActionResult(False, "INVALID_DESTINATION", {"destination": destination_lot_id})
        if Journey.objects.filter(player=player, completed=False).exists():
            return ActionResult(False, "ALREADY_TRAVELING")
        if destination.pk == origin.pk:
            return ActionResult(False, "SAME_LOCATION")
        quote = quote_travel(origin, destination, now, player)
        charged = False
        payment = "NO_PAYMENT_SYSTEM"
        if quote.amount == 0:
            payment = "NOT_REQUIRED"
        elif _payment_handler is not None:
            if not _payment_handler[1](player, quote.amount, {"origin": origin, "destination": destination, "at": now}):
                return ActionResult(False, "INSUFFICIENT_FUNDS", {"cost": quote.amount})
            charged, payment = True, "CHARGED"
        journey = Journey.objects.create(player=player, origin=origin, destination=destination, departed_at=now,
                                         arrives_at=now + quote.duration_seconds, cost=quote.amount, charged=charged)
        return ActionResult(True, "OK", {"journey_id": journey.pk, "departed_at": now, "arrives_at": journey.arrives_at,
                                         "duration_seconds": quote.duration_seconds, "travel_time": quote.time,
                                         "travel_cost": quote.cost, "cost": quote.amount, "payment": payment})


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
