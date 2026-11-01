"""
Catálogo de leis (design/07 §07.2, §07.4, §07.17; `11 — Leis Paramétricas`, REVIEW).

O processo legislativo NÃO conhece leis concretas: cada sistema/`P1.12` REGISTRA uma `LawSpec` (chave, parâmetros X com mínimo/máximo/padrão,
grupo acoplado, validações de coerência). Jogadores não inventam tipos de lei nem efeitos (07 §07.2). Sem lei registrada, nada pode ser proposto.

Valor de parâmetro: inteiro (`kind="int"`) ou decimal exato (`kind="decimal"`, aceito como `int` ou `str`; guardado como `str`). Nunca float.
Pisos constitucionais (07 §07.23) vêm de `register_constitutional_floor`; o design diz que "são definidos pelo sistema inicial" e não dá valores:
nenhum piso vem registrado (lacuna L5 de `design/07a`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Optional, Tuple

Value = Any      # int | str (decimal canônico)
Check = Dict[str, Any]       # {"key": str, "ok": bool, "reason": str, ...}
Validator = Callable[[Dict[str, Value], "LawContext"], List[Check]]


@dataclass(frozen=True)
class ParamSpec:
    name: str
    kind: str                    # "int" | "decimal"
    minimum: Value
    maximum: Value
    default: Value

    def __post_init__(self):
        if self.kind not in ("int", "decimal"):
            raise ValueError(f"kind inválido: {self.kind}")
        lo, hi, df = (to_decimal(v) for v in (self.minimum, self.maximum, self.default))
        if None in (lo, hi, df) or not lo <= df <= hi:
            raise ValueError(f"Parâmetro {self.name}: mínimo ≤ padrão ≤ máximo é obrigatório")


@dataclass(frozen=True)
class LawSpec:
    key: str
    name: str
    params: Tuple[ParamSpec, ...]
    group: Optional[str] = None                       # grupo acoplado (07 §07.17): uma proposta ativa bloqueia o grupo inteiro
    validators: Tuple[Validator, ...] = ()
    source: str = ""

    @property
    def scope(self) -> str:
        """Chave de conflito: o grupo, ou a própria lei (07 §07.17)."""
        return f"group:{self.group}" if self.group else f"law:{self.key}"

    def param(self, name: str) -> Optional[ParamSpec]:
        return next((p for p in self.params if p.name == name), None)

    def defaults(self) -> Dict[str, Value]:
        return {p.name: normalize(p.default, p.kind) for p in self.params}


@dataclass
class LawContext:
    """O que um validador de coerência pode consultar: o valor vigente de qualquer lei (nunca escreve)."""
    value_of: Callable[[str, str], Value]


_catalog: Dict[str, LawSpec] = {}
_floors: Dict[Tuple[str, str], Value] = {}


def register_law(spec: LawSpec) -> None:
    if spec.key in _catalog:
        raise ValueError(f"Lei duplicada no catálogo: {spec.key}")
    if len({p.name for p in spec.params}) != len(spec.params) or not spec.params:
        raise ValueError(f"Lei {spec.key}: parâmetros vazios ou repetidos")
    _catalog[spec.key] = spec


def unregister_law(key: str) -> None:             # para testes
    _catalog.pop(key, None)


def clear_catalog() -> None:                      # para testes
    _catalog.clear()
    _floors.clear()


def get(key: Any) -> Optional[LawSpec]:
    return _catalog.get(key) if isinstance(key, str) else None


def all_laws() -> List[LawSpec]:
    return [_catalog[k] for k in sorted(_catalog)]


def register_constitutional_floor(law_key: str, param: str, floor: Value) -> None:
    """Piso protegido (07 §07.23): lei comum não pode propor o parâmetro abaixo dele."""
    spec = _catalog.get(law_key)
    if spec is None or spec.param(param) is None:
        raise ValueError(f"Piso constitucional para parâmetro desconhecido: {law_key}.{param}")
    _floors[(law_key, param)] = floor


def floor_of(law_key: str, param: str) -> Optional[Value]:
    return _floors.get((law_key, param))


def to_decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, bool) or isinstance(value, float):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            d = Decimal(value.strip())
        except InvalidOperation:
            return None
        return d if d.is_finite() else None
    return None


def normalize(value: Any, kind: str) -> Optional[Value]:
    """Valor canônico: `int` para kind int (recusa decimal fracionário), `str` normalizada para decimal."""
    d = to_decimal(value)
    if d is None:
        return None
    if kind == "int":
        return int(d) if d == d.to_integral_value() and not isinstance(value, str) else None
    text = format(d.normalize(), "f")
    return text
