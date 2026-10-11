"""
Regras puras de viagem (design/04 §6, §20, §21). Não tocam o banco.

Geografia fornece a DISTÂNCIA; este módulo compõe o tempo-base e o custo monetário base e decide o que depende de
presença. Veículos, infraestrutura e transporte público (04 §21) não existem: quando existirem, entram como
modificadores sobre o tempo-base e o custo-base (passos multiplicativos "modifier:<nome>" do detalhamento).
"""
from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal
from typing import Optional, Sequence, Tuple

from core.breakdown import Calc, Explained
from players.actions import Action
from players.hooks import ActivityContext

# Decisão do GD (2026-10-07): Trabalho e Estudo EXIGEM presença; Lazer e Tratamento NÃO. É regra fixa da ação: uma
# atividade não pode contrariá-la. Ação fora desta tabela: cada atividade declara (ActivityContext.requires_presence).
PRESENCE_BY_ACTION = {"work": True, "study": True, "leisure": False, "treatment": False}

Modifier = Tuple[str, Decimal]   # (nome, fator multiplicativo)


def _apply(calc: Calc, modifiers: Sequence[Modifier]) -> Calc:
    for name, factor in modifiers:
        calc = calc.mul(f"modifier:{name}", factor)
    return calc


def travel_time(distance: Decimal, minutes_per_unit: Decimal, at: Optional[int] = None,
                modifiers: Sequence[Modifier] = ()) -> Explained:
    """
    tempo de viagem (minutos de jogo) = distância em grid × minutos_por_unidade [× modificadores]   (04 §21)
    Sem modificadores é o tempo-base. Detalhamento estruturado (doc 20): quem consome vê cada componente.
    """
    return _apply(Calc("distance", distance).mul("minutes_per_unit", minutes_per_unit), modifiers).result(at)


def travel_cost(distance: Decimal, cost_per_unit: Decimal, at: Optional[int] = None,
                modifiers: Sequence[Modifier] = ()) -> Explained:
    """custo monetário da viagem = distância em grid × custo_por_unidade [× modificadores]   (decisão do GD, 2026-10-07)"""
    return _apply(Calc("distance", distance).mul("cost_per_unit", cost_per_unit), modifiers).result(at)


def duration_seconds(minutes: Decimal) -> int:
    """
    Minutos -> segundos de jogo inteiros (o motor de tempo usa segundos inteiros). Arredonda PARA CIMA: a viagem nunca
    chega antes do tempo calculado. Mínimo de 1 s para manter a invariante "chega depois de partir". O design não define o
    arredondamento; é decisão técnica registrada no CHANGELOG_DEV.md.
    """
    return max(1, int((minutes * 60).to_integral_value(rounding=ROUND_CEILING)))


def charge_amount(cost: Decimal) -> Decimal:
    """Valor efetivamente cobrado: centavos (2 casas), arredondamento bancário. O cálculo em si nunca arredonda (doc 20 §8)."""
    return cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


def requires_presence(action: Action, activity: Optional[ActivityContext]) -> bool:
    """
    A ação define (Trabalho/Estudo sim; Lazer/Tratamento não). Para ação fora da tabela, a atividade tem de declarar.
    Contrariar a regra fixa da ação é erro de programação (ValueError), não uma escolha silenciosa.
    """
    declared = None if activity is None else activity.requires_presence
    fixed = PRESENCE_BY_ACTION.get(action.value)
    if fixed is None:
        if declared is None:
            raise ValueError(f"A ação '{action.value}' não tem regra de presença: a atividade deve declarar requires_presence.")
        return declared
    if declared is not None and declared != fixed:
        raise ValueError(f"A ação '{action.value}' {'exige' if fixed else 'não exige'} presença física (regra fixa); "
                         f"a atividade não pode declarar o contrário.")
    return fixed
