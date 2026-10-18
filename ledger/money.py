"""
Valores monetários: INTEIROS EM CENTAVOS (design/24 §24.4). Float é proibido. Valores calculados arredondam UMA vez
(`ROUND_HALF_EVEN`, a mesma regra de `travel.rules.charge_amount`) e a última perna é o resto.
"""
from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Optional

from core.timeline import local_dt

from .constants import CENTAVOS_PER_REAL, MAX_AMOUNT


def is_centavos(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def amount_problem(value) -> Optional[str]:
    """Código de recusa para um valor de lançamento inválido, ou None se for válido."""
    if not is_centavos(value):
        return "AMOUNT_NOT_IN_CENTAVOS"
    if value <= 0:
        return "AMOUNT_NOT_POSITIVE"
    if value > MAX_AMOUNT:
        return "AMOUNT_TOO_LARGE"
    return None


def from_reais(value) -> int:
    """Reais (`Decimal`, `int` ou `str`) → centavos. ValueError se não estiver EXATAMENTE em centavos (nada de arredondar calado)."""
    if isinstance(value, float):
        raise ValueError("float não é permitido em valores monetários")
    d = value if isinstance(value, Decimal) else Decimal(value)
    cents = d * CENTAVOS_PER_REAL
    if cents != cents.to_integral_value():
        raise ValueError(f"{value!r} não está em centavos exatos")
    return int(cents)


def to_reais(centavos: int) -> Decimal:
    return Decimal(centavos) / CENTAVOS_PER_REAL


def percent_of(amount: int, rate: Decimal) -> int:
    """`amount × rate` arredondado UMA vez a centavos (HALF_EVEN). `rate` é fração (0,05 = 5%)."""
    if isinstance(rate, float):
        raise ValueError("float não é permitido em alíquotas")
    return int((Decimal(amount) * Decimal(rate)).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def competence_day_of(at: int) -> int:
    """Dia de jogo (calendário local do jogo) de um instante: ordinal da data. Só inteiros, ordenável."""
    return local_dt(at).date().toordinal()


_RATE_QUANTUM = Decimal("0.000001")           # as alíquotas guardadas têm 6 casas (DecimalField(9, 6))


def tax_rate_problem(rate) -> Optional[str]:
    """`TAX_RATE_INVALID` se a alíquota não for número exato em [0, 1] com no máximo 6 casas (nada é arredondado calado)."""
    if isinstance(rate, (float, bool)) or not isinstance(rate, (Decimal, int, str)):
        return "TAX_RATE_INVALID"
    try:
        d = Decimal(rate)
    except (InvalidOperation, ValueError):
        return "TAX_RATE_INVALID"
    if not d.is_finite() or not Decimal(0) <= d <= Decimal(1) or d != d.quantize(_RATE_QUANTUM):
        return "TAX_RATE_INVALID"
    return None


def canonical_rate(rate) -> Decimal:
    """Alíquota válida (ver `tax_rate_problem`) na forma guardada: 6 casas. `0.1`, `"0.10"` e `Decimal("0.100000")` são a mesma."""
    return Decimal(rate).quantize(_RATE_QUANTUM)


def tax_territory_problem(text) -> Optional[str]:
    """`TAX_TERRITORY_INVALID` se o território opaco não for vazio nem `tipo:id` (`city:3`)."""
    if text == "":
        return None
    if not isinstance(text, str):
        return "TAX_TERRITORY_INVALID"
    kind, sep, ident = text.partition(":")
    if not sep or not kind.isalnum() or not ident.isdigit():
        return "TAX_TERRITORY_INVALID"
    return None
