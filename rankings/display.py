"""Apresentação de valores (só texto de tela; a regra de negócio devolve sempre o valor exato e o detalhamento estruturado)."""
from __future__ import annotations

from ledger.money import to_reais


def fmt_centavos(value: int) -> str:
    sign = "-" if value < 0 else ""
    reais = to_reais(abs(value))
    whole, frac = f"{reais:.2f}".split(".")
    return f"{sign}R$ {int(whole):,}".replace(",", ".") + f",{frac}"


def fmt_seconds(value: int) -> str:
    days, rest = divmod(value, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    return f"{days} d {hours} h {minutes} min"


def fmt_ppm(value: int) -> str:
    return f"{value / 10_000:.4f}%".replace(".", ",")


def fmt_qol(value) -> str:
    return f"{value:.4f}".replace(".", ",")


def fmt(unit: str, value) -> str:
    if unit == "centavos":
        return fmt_centavos(value)
    if unit == "segundos":
        return fmt_seconds(value)
    if unit == "qol":
        return fmt_qol(value)
    if unit == "percentual":
        return fmt_ppm(value)
    return str(value)
