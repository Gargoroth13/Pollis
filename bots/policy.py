"""
Política de decisão: contrato e política de INFRAESTRUTURA. O modelo híbrido de RL é a P1.19; aqui existe só o contrato (`Policy`) e uma política-base
uniforme sobre a máscara, para exercitar o ciclo observar → mascarar → decidir → agir → registrar → agendar. Ela NÃO é estratégia de jogo.
A política recebe SOMENTE a observação, a máscara e o gerador aleatório do Bot (21 §21.17, §21.60): nunca o `Bot`, o `Player` ou dados de Admin.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol

from . import params


@dataclass(frozen=True)
class Decision:
    action_id: str
    target: Any = None
    score: Optional[float] = None
    exploration: Dict[str, Any] = field(default_factory=dict)


class Policy(Protocol):
    model_version: str

    def decide(self, observation: Dict[str, Any], mask: Dict[str, Dict[str, Any]], rng: random.Random) -> Optional[Decision]:
        ...


class UniformMaskedPolicy:
    """Escolhe uniformemente entre as ações disponíveis que NÃO exigem alvo (as demais precisam de enumeração de alvos, que é do modelo da P1.19)."""

    model_version = params.BASELINE_MODEL_VERSION

    def decide(self, observation, mask, rng):
        options = sorted(a for a, m in mask.items() if m["available"] and not m["target_required"])
        if not options:
            return None
        chosen = rng.choice(options)
        return Decision(action_id=chosen, target=None, score=1.0 / len(options),
                        exploration={"kind": "uniform_over_mask", "options": len(options)})
