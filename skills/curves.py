"""
Curvas parametrizáveis do sistema de Skills: os pontos em que o 01 diz "fórmula ainda não fechada".

  progress curve    diminishing returns do GANHO de skill      (01 §1.5: "fórmula exata ainda não está fechada")
  production curve  relação nível da skill -> produção          (01 §1.6: "deve permanecer parametrizada")

Cada curva recebe o NÍVEL (Decimal) e devolve um `Explained` cujo `value` é o fator (doc 20: tudo que é
derivado carrega os componentes). A única curva embutida é "none" (fator 1 = sem efeito): NENHUMA fórmula
foi escolhida. Quando o design fechar a curva, registra-se uma nova e troca-se o parâmetro no balanceamento.

Nada aqui é regra de gameplay.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Callable, Dict, List

from core.breakdown import Calc, Explained

Curve = Callable[[Decimal], Explained]

_progress: Dict[str, Curve] = {}
_production: Dict[str, Curve] = {}


def _none(level: Decimal) -> Explained:
    return Calc("no_curve", 1).result()


def register_progress_curve(name: str, fn: Curve) -> None:
    if name in _progress:
        raise ValueError(f"Curva de progressão duplicada: {name}")
    _progress[name] = fn


def register_production_curve(name: str, fn: Curve) -> None:
    if name in _production:
        raise ValueError(f"Curva de produção duplicada: {name}")
    _production[name] = fn


def unregister_progress_curve(name: str) -> None:   # para testes
    _progress.pop(name, None)


def unregister_production_curve(name: str) -> None:  # para testes
    _production.pop(name, None)


def progress_curve(name: str) -> Curve:
    return _progress[name]


def production_curve(name: str) -> Curve:
    return _production[name]


def progress_curve_names() -> List[str]:
    return sorted(_progress)


def production_curve_names() -> List[str]:
    return sorted(_production)


register_progress_curve("none", _none)
register_production_curve("none", _none)
