"""
Detalhamento estruturado de fórmulas (design/20, FINAL — BOT TEST).

Regra: a PRÓPRIA função que calcula o valor produz também a explicação; nunca
se reconstrói a explicação depois. O resultado é DADO ESTRUTURADO (chaves, números,
tipos de passo), não texto: quem apresenta (UI, bot, histórico) decide como mostrar.

Tipos de passo (20.3):
  BASE      ponto de partida
  ADD       fórmula aditiva (+X / -X)
  MULTIPLY  fórmula multiplicativa (×F)
  FLOOR/CAP fórmula com limite; `binding` diz se o limite RESTRINGIU o resultado
            (20.3: "o detalhamento precisa mostrar qual regra restringiu")
Passos podem carregar `detail`, outro Explained (detalhamento hierárquico, 20.6).

Valores são Decimal exatos e NUNCA arredondados aqui (20.8): arredondar é da UI.
Float é rejeitado de propósito: mantém o cálculo determinístico.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional, Tuple, Union

Number = Union[int, str, Decimal]


def D(x: Number) -> Decimal:
    """Converte para Decimal exato. Float é proibido (não-determinístico)."""
    if isinstance(x, float):
        raise TypeError("float não é permitido em fórmulas do jogo; use int, str ou Decimal.")
    return x if isinstance(x, Decimal) else Decimal(x)


class StepKind(str, Enum):
    BASE = "base"
    ADD = "add"
    MULTIPLY = "multiply"
    FLOOR = "floor"
    CAP = "cap"


@dataclass(frozen=True)
class Step:
    key: str                       # identificador estável (a UI traduz; não é texto de tela)
    kind: StepKind
    amount: Decimal                # parcela somada, fator, ou limite
    result: Decimal                # valor corrente DEPOIS deste passo
    binding: bool = False          # FLOOR/CAP: o limite alterou o valor?
    detail: Optional["Explained"] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "key": self.key, "kind": self.kind.value,
            "amount": str(self.amount), "result": str(self.result),
        }
        if self.kind in (StepKind.FLOOR, StepKind.CAP):
            d["binding"] = self.binding
        if self.detail is not None:
            d["detail"] = self.detail.to_dict()
        return d


@dataclass(frozen=True)
class Explained:
    value: Decimal
    steps: Tuple[Step, ...]
    computed_at: Optional[int] = None  # tempo de jogo do cálculo (20.9)

    def step(self, key: str) -> Step:
        for s in self.steps:
            if s.key == key:
                return s
        raise KeyError(key)

    def has(self, key: str) -> bool:
        return any(s.key == key for s in self.steps)

    @property
    def restricted_by(self) -> Tuple[str, ...]:
        """Chaves dos limites que de fato restringiram o resultado."""
        return tuple(s.key for s in self.steps if s.binding)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": str(self.value),
            "computed_at": self.computed_at,
            "steps": [s.to_dict() for s in self.steps],
        }


class Calc:
    """Construtor de fórmula: cada operação aplica E registra o passo."""

    def __init__(self, key: str, base: Number, *, detail: Optional[Explained] = None):
        self._value = D(base)
        self._steps = [Step(key, StepKind.BASE, self._value, self._value, detail=detail)]

    @property
    def value(self) -> Decimal:
        return self._value

    def add(self, key: str, amount: Number, *, detail: Optional[Explained] = None) -> "Calc":
        amount = D(amount)
        self._value += amount
        self._steps.append(Step(key, StepKind.ADD, amount, self._value, detail=detail))
        return self

    def mul(self, key: str, factor: Number, *, detail: Optional[Explained] = None) -> "Calc":
        factor = D(factor)
        self._value *= factor
        self._steps.append(Step(key, StepKind.MULTIPLY, factor, self._value, detail=detail))
        return self

    def floor(self, key: str, minimum: Number) -> "Calc":
        minimum = D(minimum)
        binding = self._value < minimum
        if binding:
            self._value = minimum
        self._steps.append(Step(key, StepKind.FLOOR, minimum, self._value, binding=binding))
        return self

    def cap(self, key: str, maximum: Number) -> "Calc":
        maximum = D(maximum)
        binding = self._value > maximum
        if binding:
            self._value = maximum
        self._steps.append(Step(key, StepKind.CAP, maximum, self._value, binding=binding))
        return self

    def result(self, computed_at: Optional[int] = None) -> Explained:
        return Explained(self._value, tuple(self._steps), computed_at)
