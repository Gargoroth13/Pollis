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
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from core.breakdown import Calc, Explained

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
    requires_presence  a atividade depende de PRESENÇA FÍSICA no local? (04 §6, §20). Regra fixa por ação (GD, 2026-10-07):
                       Trabalho e Estudo exigem; Lazer e Tratamento não. Para esses, None = a regra da ação e declarar o
                       contrário é erro (ValueError). Ação sem regra fixa: a atividade declara.
    """
    skills: Optional[Tuple[str, ...]] = None
    base_gain: Optional[Mapping[str, Decimal]] = None
    school_quality: Decimal = Decimal(1)
    specialization_key: Optional[str] = None
    requires_presence: Optional[bool] = None


@dataclass
class ActionHookContext:
    player: Player            # em memória, ainda não salvo: hooks NÃO devem chamar player.save()
    action: Action
    now: int                  # tempo de jogo, lido uma vez pelo serviço
    bal: Balance
    activity: Optional[ActivityContext]


ActionHook = Callable[[ActionHookContext], Optional[Dict[str, Any]]]
PlayerCreatedHook = Callable[[Player, int], None]
# Provedor de bloqueio: devolve um CÓDIGO de motivo (ex.: "TRAVELING") se a ação não pode ser feita agora, ou None.
BlockProvider = Callable[[Player, Action, int, Optional[ActivityContext]], Optional[str]]
# Hook de acesso (On Access, 04 §22): roda ao FIM do catch-up lazy, com o jogador já processado até `now`.
AccessHook = Callable[[Player, int], None]
# Provedor de atividade: quem conhece a atividade (o cargo do jogador, o curso) devolve o `ActivityContext` da ação, ou None.
# Só é consultado quando quem chamou `perform_action` NÃO informou `activity`: jogadores reais e bots, que pedem a ação pelo
# Action Registry, nunca informam o contexto; ele vem do sistema dono (design/02 §6; GD 2026-10-12).
ActivityProvider = Callable[[Player, Action, int], Optional[ActivityContext]]
# Provedor de risco de Burnout (02 §9.2): devolve o multiplicador dos GANHOS de Burnout de Trabalhar/Estudar (1 = 100%) com o
# detalhamento, ou None se o sistema não tem efeito sobre este jogador agora. Só é consultado quando quem chamou `perform_action`
# NÃO informou `burnout_risk`; os provedores se multiplicam e o piso de 1% é aplicado depois (`rules.burnout_change`).
BurnoutRiskProvider = Callable[[Player, Action, int], Optional[Explained]]

_action_hooks: Dict[str, ActionHook] = {}
_created_hooks: Dict[str, PlayerCreatedHook] = {}
_block_providers: Dict[str, BlockProvider] = {}
_access_hooks: Dict[str, AccessHook] = {}
_activity_providers: Dict[str, ActivityProvider] = {}
_burnout_risk_providers: Dict[str, BurnoutRiskProvider] = {}


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


def register_block_provider(name: str, fn: BlockProvider) -> None:
    """Um sistema acrescenta motivos de recusa a uma ação (ex.: viagem). Mesmo caminho para humanos e bots."""
    if name in _block_providers:
        raise ValueError(f"Provedor de bloqueio duplicado: {name}")
    _block_providers[name] = fn


def register_access_hook(name: str, fn: AccessHook) -> None:
    if name in _access_hooks:
        raise ValueError(f"Hook de acesso duplicado: {name}")
    _access_hooks[name] = fn


def register_activity_provider(name: str, fn: ActivityProvider) -> None:
    if name in _activity_providers:
        raise ValueError(f"Provedor de atividade duplicado: {name}")
    _activity_providers[name] = fn


def register_burnout_risk_provider(name: str, fn: BurnoutRiskProvider) -> None:
    if name in _burnout_risk_providers:
        raise ValueError(f"Provedor de risco de Burnout duplicado: {name}")
    _burnout_risk_providers[name] = fn


def resolve_burnout_risk(player: Player, action: Action, now: int) -> Optional[Explained]:
    """Produto dos multiplicadores dos provedores (ordem de nome, determinístico) com o detalhamento; None se nenhum responde."""
    calc, any_effect = Calc("burnout_risk_base", 1), False
    for name in sorted(_burnout_risk_providers):
        effect = _burnout_risk_providers[name](player, action, now)
        if effect is not None:
            calc.mul(name, effect.value, detail=effect)
            any_effect = True
    return calc.result(now) if any_effect else None


def resolve_activity(player: Player, action: Action, now: int) -> Optional[ActivityContext]:
    """Primeiro contexto não vazio, em ordem de nome (determinístico). Sem provedor que responda, a ação segue sem contexto."""
    for name in sorted(_activity_providers):
        activity = _activity_providers[name](player, action, now)
        if activity is not None:
            return activity
    return None


def run_block_providers(player: Player, action: Action, now: int, activity: Optional[ActivityContext]) -> List[str]:
    """Motivos de bloqueio dos provedores, em ordem de nome (determinístico), sem repetição."""
    reasons: List[str] = []
    for name in sorted(_block_providers):
        reason = _block_providers[name](player, action, now, activity)
        if reason is not None and reason not in reasons:
            reasons.append(reason)
    return reasons


def run_access_hooks(player: Player, now: int) -> None:
    for name in sorted(_access_hooks):
        _access_hooks[name](player, now)


def unregister_block_provider(name: str) -> None:      # para testes
    _block_providers.pop(name, None)


def unregister_activity_provider(name: str) -> None:   # para testes
    _activity_providers.pop(name, None)


def unregister_access_hook(name: str) -> None:         # para testes
    _access_hooks.pop(name, None)


def unregister_action_hook(name: str) -> None:        # para testes
    _action_hooks.pop(name, None)


def unregister_player_created_hook(name: str) -> None:  # para testes
    _created_hooks.pop(name, None)


def unregister_burnout_risk_provider(name: str) -> None:  # para testes
    _burnout_risk_providers.pop(name, None)
