"""
Auto-consumo de alimentos (design/04 §16). A regra, inteira, vem do design:

  - o jogador habilita o Auto-consumo no Inventário e escolhe (opcional) um alimento preferido;
  - quando `Nutrição < 10`, durante o processamento lazy do estado do jogador, o sistema tenta consumir;
  - prioridade: 1) o alimento preferido, se existir no Inventário; 2) senão, o alimento disponível com o MENOR ganho de Nutrição;
  - repete enquanto a Nutrição seguir abaixo de 10 e existir alimento elegível; ao atingir ou passar de 10, para; sem
    alimento elegível, não faz nada;
  - usa EXATAMENTE as regras do consumo manual (`services.consume_locked`), sem ganho especial;
  - nenhuma verificação contínua por jogador: roda só quando o estado do jogador é processado (hook de acesso).

Integração com o processamento lazy (sem recursão). `players.services._catch_up` termina rodando os hooks de acesso, e o
consumo público (`services.consume`) chama `locked_player` → `_catch_up`. Por isso o hook NÃO chama o serviço público: opera
sobre o jogador que o catch-up já travou e processou (em memória), pelo núcleo `consume_locked`, que não trava, não faz
catch-up e não salva (o dono do catch-up salva). Um guarda de reentrada garante que, mesmo que alguém religue os caminhos, o
hook nunca rode dentro de si mesmo.

Escolhas técnicas (não alteram o design; registradas no CHANGELOG_DEV):
  - "elegível" = alimento do catálogo com valores especificados (NULL é recusado pelo consumo manual) e ganho de Nutrição > 0
    (um alimento sem ganho nunca encerraria o laço), com ao menos 1 unidade no inventário do jogador;
  - empate no menor ganho: desempate determinístico pela chave do produto (ordem alfabética);
  - o limiar 10 é do design (`constants.AUTO_CONSUME_BELOW`), não `[PROV]`.
"""
from __future__ import annotations

import contextvars
from typing import Any, Dict, Optional, Tuple

from django.db import transaction

from catalog import services as catalog
from core import clock as game_clock
from players.models import Player
from players.services import ActionResult

from . import services
from .constants import AUTO_CONSUME_BELOW
from .models import AutoConsumption, InventoryItem

_running: contextvars.ContextVar[bool] = contextvars.ContextVar("inventory_auto_consumption_running", default=False)


# --- configuração -------------------------------------------------------------------------------------------------------

def configuration_refusal(enabled: Any, preferred: Any) -> Optional[ActionResult]:
    """Recusas que só LEEM: tipos, e o preferido (se houver) precisa ser um alimento consumível do catálogo."""
    if not isinstance(enabled, bool) or not (preferred is None or isinstance(preferred, str)):
        return services._refuse("INVALID_PARAMS", why="enabled deve ser booleano e preferred, texto ou nulo")
    if preferred is None:
        return None
    return services.consumption_refusal(preferred)


def settings_of(player_id: int) -> Dict[str, Any]:
    cfg = AutoConsumption.objects.filter(player_id=player_id).select_related("preferred_product").first()
    if cfg is None:
        return {"enabled": False, "preferred": None}
    return {"enabled": cfg.enabled, "preferred": cfg.preferred_product.key if cfg.preferred_product else None}


def configure(player_id: int, enabled: Any, preferred: Any = None) -> ActionResult:
    """
    Habilita/desabilita o Auto-consumo e define (ou limpa, com `None`) o alimento preferido. Não custa Energia nem dinheiro
    (o design não define custo). Desabilitar mantém a preferência. Recusas: INVALID_PARAMS, PLAYER_NOT_FOUND, UNKNOWN_PRODUCT,
    NO_CONSUMPTION_EFFECT, UNSPECIFIED_DESIGN_VALUE.
    """
    refusal = configuration_refusal(enabled, preferred)
    if refusal is not None:
        return refusal
    if not Player.objects.filter(pk=player_id).exists():
        return services._refuse("PLAYER_NOT_FOUND", player=player_id)
    product = catalog.get_product(preferred) if preferred is not None else None
    with transaction.atomic():
        Player.objects.select_for_update().get(pk=player_id)          # protocolo: a linha do jogador serializa a configuração
        AutoConsumption.objects.update_or_create(
            player_id=player_id,
            defaults={"enabled": enabled, "preferred_product": product, "updated_at": game_clock.now()})
    return ActionResult(True, "OK", {"enabled": enabled, "preferred": preferred})


# --- escolha do alimento ------------------------------------------------------------------------------------------------

def choose_food(player_id: int, preferred: Optional[str]) -> Optional[Tuple[str, str, Dict[str, str]]]:
    """
    `(produto, regra, candidatos)` ou None se não há alimento elegível. `regra` = "preferred" ou "lowest_gain"; `candidatos` =
    {produto: ganho} dos elegíveis no inventário (vai para o detalhamento do movimento, 20).
    """
    held = list(InventoryItem.objects.filter(player_id=player_id, quantity__gt=0).values_list("product__key", flat=True))
    gains = catalog.food_gains(held)
    if not gains:
        return None
    candidates = {k: str(v) for k, v in sorted(gains.items())}
    if preferred is not None and preferred in gains:
        return preferred, "preferred", candidates
    lowest = min(gains, key=lambda k: (gains[k], k))
    return lowest, "lowest_gain", candidates


# --- hook de acesso -----------------------------------------------------------------------------------------------------

def on_access(player: Player, now: int) -> None:
    """
    Hook de acesso (`players.hooks`, On Access): roda no FIM do catch-up com o jogador já processado até `now`, em memória e
    travado pelo dono do catch-up. Barato no caso comum: com Nutrição ≥ 10 não consulta nada.
    """
    if player.nutrition >= AUTO_CONSUME_BELOW or _running.get():
        return
    cfg = AutoConsumption.objects.filter(player_id=player.pk, enabled=True).select_related("preferred_product").first()
    if cfg is None:
        return
    preferred = cfg.preferred_product.key if cfg.preferred_product else None
    token = _running.set(True)
    try:
        while player.nutrition < AUTO_CONSUME_BELOW:
            choice = choose_food(player.pk, preferred)
            if choice is None:
                break                                                 # sem alimento elegível: nenhuma ação
            key, rule, candidates = choice
            res = services.consume_locked(player, key, now, automatic=True,
                                          extra={"selection": {"rule": rule, "preferred": preferred, "chosen": key,
                                                               "candidates": candidates}})
            if not res.ok:                                            # não deveria ocorrer: o elegível foi lido sob o bloqueio
                raise RuntimeError(f"auto-consumo recusado depois da escolha: {res.code}")
    finally:
        _running.reset(token)
