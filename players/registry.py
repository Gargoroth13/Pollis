"""
Action Registry (design/21 §20): o catálogo ÚNICO das ações de jogo que jogadores reais e bots podem pedir.

O registro NÃO é uma segunda implementação das ações. Ele descreve cada ação (contrato do 21 §20) e delega:
  - disponibilidade: à MESMA função que a execução usa (`players.services.action_refusal`, `travel.services.travel_refusal`);
  - execução: ao MESMO serviço de sempre (`perform_action`, `start_travel`), que revalida tudo dentro da própria transação;
  - feedback: aos `Explained` (doc 20) das regras donas do cálculo.
Não há caminho privilegiado para bots (CLAUDE.md §5.4) e nenhuma regra nova vive aqui.

Contrato do descritor (21 §20) e o que cada campo significa HOJE:
  id          estável, minúsculo; independe do nome de apresentação
  name        nome de apresentação
  category    UNSPECIFIED: o design não define taxonomia de categorias de ação
  requirements códigos de recusa que as regras do dono da ação podem produzir (documentação verificada por teste; os
              motivos concretos de um jogador vêm em `ActionAvailability.blocked_by`, inclusive os de provedores externos)
  cost        componentes de custo da ação; os valores concretos vêm de `preview` (Energia vem de Balance, nada hard-coded)
  cooldown    NO_COOLDOWN: não existe mecanismo geral de cooldown no design; as ações são limitadas por Energia e bloqueios
  target      TargetSpec: Trabalhar/Estudar/Lazer não têm alvo; Viajar tem um lote (obrigatório para executar)
  effects     efeitos que o SERVIÇO dono executa (descritivo; o registro não os aplica)
  visibility  UNSPECIFIED: o design não define política de visibilidade de ações

Disponibilidade é CONSULTIVA; a execução é a autoridade (o estado pode mudar entre a consulta e a execução).
Máscara de ações para bots (21 §21) NÃO é deste módulo: é o bloco P1.19, que se apoiará em `available_actions`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import clock as game_clock

from . import rules, services
from .actions import Action
from .balance import Balance
from .models import Player
from .services import ActionResult

UNSPECIFIED = "UNSPECIFIED"   # o design ainda não definiu: explícito, nunca um valor inventado
NO_COOLDOWN = "NONE"          # não existe mecanismo geral de cooldown (nenhum prazo é inferido)

TARGET_NONE = "none"
TARGET_LOT = "lot"
_TARGET_KINDS = (TARGET_NONE, TARGET_LOT)

# Parâmetros de CONTEXTO INTERNO de perform_action: vêm dos sistemas que conhecem a atividade (cargo, curso, atividade de
# lazer), nunca de uma interface ou de um bot. Pedi-los pelo registro é erro, não ignorado em silêncio.
INTERNAL_PARAMS = frozenset({"burnout_risk", "effect", "activity"})

_INT64 = 2 ** 63
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class TargetSpec:
    kind: str = TARGET_NONE
    required: bool = False

    def __post_init__(self):
        if self.kind not in _TARGET_KINDS:
            raise ValueError(f"Tipo de alvo desconhecido: {self.kind!r}")
        if self.required and self.kind == TARGET_NONE:
            raise ValueError("Ação sem alvo não pode exigir alvo.")


@dataclass(frozen=True)
class ActionDescriptor:
    id: str
    name: str
    category: str = UNSPECIFIED
    requirements: Tuple[str, ...] = ()
    cost: Tuple[str, ...] = ()
    cooldown: str = NO_COOLDOWN
    target: TargetSpec = field(default_factory=TargetSpec)
    effects: Tuple[str, ...] = ()
    visibility: str = UNSPECIFIED

    def __post_init__(self):
        if not _ID_RE.match(self.id):
            raise ValueError(f"Identificador de ação inválido: {self.id!r}")

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "category": self.category, "requirements": list(self.requirements),
                "cost": list(self.cost), "cooldown": self.cooldown,
                "target": {"kind": self.target.kind, "required": self.target.required},
                "effects": list(self.effects), "visibility": self.visibility}


# `check`   (player travado e processado, now, bal, alvo|None) -> recusa|None. Só LÊ.
# `execute` (player_id, alvo|None) -> ActionResult. É o serviço dono: transação, trava, catch-up e revalidação próprios.
# `preview` (player travado, now, bal, alvo|None) -> {chave: valor|Explained}. Só LÊ; nada é cobrado nem aplicado.
CheckFn = Callable[[Player, int, Balance, Any], Optional[ActionResult]]
ExecuteFn = Callable[[int, Any], ActionResult]
PreviewFn = Callable[[Player, int, Balance, Any], Dict[str, Any]]


@dataclass(frozen=True)
class RegisteredAction:
    descriptor: ActionDescriptor
    check: CheckFn
    execute: ExecuteFn
    preview: PreviewFn


_actions: Dict[str, RegisteredAction] = {}


def register_action(descriptor: ActionDescriptor, *, check: CheckFn, execute: ExecuteFn, preview: PreviewFn) -> None:
    """Cada app registra as suas ações no `ready()` (como os hooks). Id duplicado é erro, nunca sobrescrita."""
    if descriptor.id in _actions:
        raise ValueError(f"Ação duplicada no registro: {descriptor.id}")
    _actions[descriptor.id] = RegisteredAction(descriptor, check, execute, preview)


def unregister_action(action_id: str) -> None:   # para testes
    _actions.pop(action_id, None)


def get_descriptor(action_id: str) -> Optional[ActionDescriptor]:
    entry = _actions.get(action_id)
    return None if entry is None else entry.descriptor


def list_descriptors() -> List[ActionDescriptor]:
    """Todas as ações registradas, em ordem de id (determinístico)."""
    return [_actions[a].descriptor for a in sorted(_actions)]


# --- consulta -----------------------------------------------------------------

@dataclass(frozen=True)
class ActionAvailability:
    """
    Resultado CONSULTIVO de uma ação para um jogador. `available` diz se a ação pode ser tentada; os motivos reais são os da
    regra (`code`, `blocked_by`), nunca reinterpretados aqui.
      target_validated  True só quando um alvo foi informado e conferido. Sem alvo, uma ação com alvo obrigatório continua
                        disponível em geral (`target_required=True`); executar sem alvo é recusado (TARGET_REQUIRED).
    """
    action_id: str
    name: str
    available: bool
    code: str                       # "OK" ou o código de recusa
    blocked_by: Tuple[str, ...]     # todos os motivos de bloqueio (vazio se disponível ou se a recusa não é de bloqueio)
    target_required: bool
    target_validated: bool
    preview: Dict[str, Any]
    at: int


def _target_problem(descriptor: ActionDescriptor, target: Any, *, executing: bool) -> Optional[ActionResult]:
    """
    Regras do alvo que NÃO dependem do banco: proibição e tipo; e a presença, SÓ na execução. Na consulta, a falta de alvo
    não tira a ação da disponibilidade geral (ela apenas ainda não foi validada contra um alvo).
    """
    spec = descriptor.target
    if target is None:
        if spec.required and executing:
            return ActionResult(False, "TARGET_REQUIRED", {"action": descriptor.id, "target": spec.kind})
        return None
    if spec.kind == TARGET_NONE:
        return ActionResult(False, "TARGET_NOT_ALLOWED", {"action": descriptor.id})
    if spec.kind == TARGET_LOT and (isinstance(target, bool) or not isinstance(target, int)
                                    or not -_INT64 <= target < _INT64):   # fora do int64 nem chega ao banco
        return ActionResult(False, "INVALID_PARAMS", {"action": descriptor.id, "target": repr(target),
                                                      "expected": "lot id (int)"})
    return None


def _availability(entry: RegisteredAction, player: Player, now: int, bal: Balance, target: Any) -> ActionAvailability:
    d = entry.descriptor
    problem = _target_problem(d, target, executing=False)
    refusal = problem if problem is not None else entry.check(player, now, bal, target)
    preview = entry.preview(player, now, bal, target) if problem is None else {}
    if refusal is None:
        code, blocked = "OK", ()
    else:
        code, blocked = refusal.code, tuple(refusal.detail.get("reasons", ()))
    return ActionAvailability(d.id, d.name, refusal is None, code, blocked, d.target.required,
                              target is not None and problem is None, preview, now)


def check_action(player_id: int, action_id: str, target: Any = None) -> ActionAvailability:
    """
    A ação `action_id` pode ser tentada agora? Um acesso sincronizado (trava + catch-up lazy, como get_snapshot).
    Sem `target`, só a disponibilidade geral; com `target`, também as regras do alvo. ValueError não é usado: ação
    desconhecida devolve UNKNOWN_ACTION.
    """
    entry = _actions.get(action_id)
    if entry is None:
        return ActionAvailability(str(action_id), str(action_id), False, "UNKNOWN_ACTION", (), False, False, {},
                                  game_clock.now())
    with services.locked_player(player_id) as (player, now, bal):
        return _availability(entry, player, now, bal, target)


def available_actions(player_id: int) -> List[ActionAvailability]:
    """Disponibilidade GERAL de todas as ações registradas (sem alvos; não enumera lotes), numa única sessão sincronizada."""
    with services.locked_player(player_id) as (player, now, bal):
        return [_availability(_actions[a], player, now, bal, None) for a in sorted(_actions)]


# --- execução -----------------------------------------------------------------

def execute_action(player_id: int, action_id: str, target: Any = None, **params) -> ActionResult:
    """
    Executa uma ação pelo registro. Recusas são CÓDIGOS (como nos serviços): UNKNOWN_ACTION, INVALID_PARAMS,
    TARGET_REQUIRED, TARGET_NOT_ALLOWED e as do próprio serviço. O serviço dono revalida requisitos e alvo dentro da sua
    transação: o resultado é o mesmo de chamá-lo diretamente. Parâmetros de contexto interno (INTERNAL_PARAMS) e
    desconhecidos são recusados com INVALID_PARAMS.
    """
    entry = _actions.get(action_id)
    if entry is None:
        return ActionResult(False, "UNKNOWN_ACTION", {"action": str(action_id)})
    if params:
        return ActionResult(False, "INVALID_PARAMS", {
            "action": action_id, "rejected": sorted(params), "internal": sorted(set(params) & INTERNAL_PARAMS)})
    problem = _target_problem(entry.descriptor, target, executing=True)
    if problem is not None:
        return problem
    return entry.execute(player_id, target)


# --- ações do próprio players (Trabalhar, Estudar, Lazer: 04 §2.2, §7) ---------

_PLAYER_ACTION_NAMES = {Action.WORK: "Trabalhar", Action.STUDY: "Estudar", Action.LEISURE: "Lazer"}
# Códigos que as regras do 04 podem recusar (rules.block_reasons + Energia). O teste de equivalência confere que nenhum
# código real escapa desta lista; provedores de outros sistemas (ex.: TRAVELING) aparecem em `blocked_by`.
_PLAYER_REQUIREMENTS = {
    Action.WORK: ("HOSPITALIZED", "HEALTH_CRITICAL", "BURNOUT_ACTIVE", "INSUFFICIENT_ENERGY"),
    Action.STUDY: ("HOSPITALIZED", "BURNOUT_ACTIVE", "INSUFFICIENT_ENERGY"),
    Action.LEISURE: ("HOSPITALIZED", "INSUFFICIENT_ENERGY"),
}
_PLAYER_EFFECTS = {
    Action.WORK: ("energy_spent", "burnout_gain", "last_work_at", "action_hooks"),
    Action.STUDY: ("energy_spent", "burnout_gain", "action_hooks"),
    Action.LEISURE: ("energy_spent", "burnout_reduction", "action_hooks"),
}


def _player_action_entry(action: Action) -> RegisteredAction:
    def check(player, now, bal, target):
        return services.action_refusal(player, action, now, bal, None)

    def execute(player_id, target):
        return services.perform_action(player_id, action)

    def preview(player, now, bal, target):
        # Mesmas funções da execução, com os mesmos padrões (risco 1, sem atividade): o que se vê é o que se paga.
        return {"energy_cost": rules.energy_cost(action, bal),
                "burnout_change": rules.burnout_change(action, Decimal(1), bal)}

    descriptor = ActionDescriptor(
        id=action.value, name=_PLAYER_ACTION_NAMES[action], requirements=_PLAYER_REQUIREMENTS[action],
        cost=("energy", "burnout"), effects=_PLAYER_EFFECTS[action])
    return RegisteredAction(descriptor, check, execute, preview)


def register_player_actions() -> None:
    for action in Action:
        entry = _player_action_entry(action)
        register_action(entry.descriptor, check=entry.check, execute=entry.execute, preview=entry.preview)


__all__ = ["ActionAvailability", "ActionDescriptor", "ActionResult", "INTERNAL_PARAMS", "NO_COOLDOWN",
           "RegisteredAction", "TARGET_LOT", "TARGET_NONE", "TargetSpec", "UNSPECIFIED", "available_actions",
           "check_action", "execute_action", "get_descriptor", "list_descriptors", "register_action",
           "register_player_actions", "unregister_action"]
