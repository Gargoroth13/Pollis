"""
Valores monetários: INTEIROS EM CENTAVOS (design/24 §24.4). Float é proibido. Valores calculados arredondam UMA vez
(`ROUND_HALF_EVEN`, a mesma regra de `travel.rules.charge_amount`) e a última perna é o resto.
"""
from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
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
