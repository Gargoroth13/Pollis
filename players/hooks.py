"""
Pontos de integração do estado do jogador com outros sistemas (Skills, e no futuro Inventário, Escolas...).

Por que existe: Trabalhar e Estudar já são ações do players (04). Outros sistemas precisam REAGIR a elas
(ex.: Skills ganha progresso) SEM duplicar a lógica de ação e SEM criar um caminho paralelo: jogadores
reais e bots chamam a mesma `services.perform_action` (design/21), e os hooks rodam dentro dela.

Garantias:
  - rodam na MESMA transação: se um hook falha, a ação inteira é desfeita;
  - só rodam depois de a ação ter SUCESSO (recusas por energia, burnout, etc. não disparam hooks);
  - ordem determinística (por nome);
  - `players` não interpreta o conteúdo do ActivityContext: só o repassa.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from .actions import Action
from .balance import Balance
from .models import Player


@dataclass(frozen=True)
class ActivityContext:
    """
    Descritor OPCIONAL do que a atividade oferece além de custo de Energia e Burnout. Quem conhece a
    atividade (o cargo, o curso, a atividade de lazer) o monta e passa a `perform_action`.

    skills             nomes das skills que a atividade desenvolve; None = padrão da ação
                       (Estudar: as 3 skills, 01 §1.4; Trabalhar/Lazer: nenhuma sem esta informação)
    base_gain          ganho base POR SKILL, sobrescrevendo o parâmetro de balanceamento
    school_quality     qualidade da escola (01 §1.3); 1 quando não se aplica
    specialization_key chave de Especialização (02 §13): atividade ou produto trabalhado
    """
    skills: Optional[Tuple[str, ...]] = None
    base_gain: Optional[Mapping[str, Decimal]] = None
    school_quality: Decimal = Decimal(1)
    specialization_key: Optional[str] = None


@dataclass
class ActionHookContext:
    player: Player            # em memória, ainda não salvo: hooks NÃO devem chamar player.save()
    action: Action
    now: int                  # tempo de jogo, lido uma vez pelo serviço
    bal: Balance
    activity: Optional[ActivityContext]


ActionHook = Callable[[ActionHookContext], Optional[Dict[str, Any]]]
PlayerCreatedHook = Callable[[Player, int], None]

_action_hooks: Dict[str, ActionHook] = {}
_created_hooks: Dict[str, PlayerCreatedHook] = {}


def register_action_hook(name: str, fn: ActionHook) -> None:
    if name in _action_hooks:
        raise ValueError(f"Hook de ação duplicado: {name}")
    _action_hooks[name] = fn


def register_player_created_hook(name: str, fn: PlayerCreatedHook) -> None:
    if name in _created_hooks:
        raise ValueError(f"Hook de criação duplicado: {name}")
    _created_hooks[name] = fn


def run_action_hooks(ctx: ActionHookContext) -> Dict[str, Any]:
    """Executa os hooks em ordem de nome; devolve {nome: resultado} dos que retornaram algo."""
    results: Dict[str, Any] = {}
    for name in sorted(_action_hooks):
        out = _action_hooks[name](ctx)
        if out is not None:
            results[name] = out
    return results


def run_player_created_hooks(player: Player, now: int) -> None:
    for name in sorted(_created_hooks):
        _created_hooks[name](player, now)


def unregister_action_hook(name: str) -> None:        # para testes
    _action_hooks.pop(name, None)


def unregister_player_created_hook(name: str) -> None:  # para testes
    _created_hooks.pop(name, None)
