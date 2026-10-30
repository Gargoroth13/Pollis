"""
Portas de operação da empresa (G5): um sistema externo (Imóveis) pode exigir que a empresa esteja localizada no prédio certo para OPERAR (Varejo vender, Industrial
produzir). Companies não conhece Imóveis: ele consulta as portas registradas (`fn(company)` → recusa ou None; só LÊ). Sem porta registrada, nada é exigido.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from players.services import ActionResult

from .models import Company

OperationGate = Callable[[Company], Optional[ActionResult]]
_gates: Dict[str, OperationGate] = {}


def register_operation_gate(name: str, fn: OperationGate) -> None:
    if name in _gates:
        raise ValueError(f"Porta de operação duplicada: {name}")
    _gates[name] = fn


def unregister_operation_gate(name: str) -> None:        # para testes
    _gates.pop(name, None)


def operation_refusal(company: Company) -> Optional[ActionResult]:
    for name in sorted(_gates):
        refusal = _gates[name](company)
        if refusal is not None:
            return refusal
    return None
