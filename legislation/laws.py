"""
Leitura das leis em vigor (design/07 §07.16, §07.21). Os sistemas consumidores leem AQUI o valor vigente de um parâmetro; sem lei em vigor vale o
padrão do catálogo (`11`). A aplicação nunca é retroativa: o valor muda só quando a proposta entra em vigor no `weekly tick`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from . import catalog
from .constants import LawStatus
from .models import Law


def current_values(key: str) -> Optional[Dict[str, Any]]:
    """Parâmetros vigentes da lei (em vigor ou, sem lei, o padrão do catálogo). None se a lei não está no catálogo."""
    spec = catalog.get(key)
    if spec is None:
        return None
    law = Law.objects.filter(key=key, status=LawStatus.IN_FORCE.value).first()
    return dict(law.params) if law is not None else spec.defaults()


def value(key: str, param: str) -> Any:
    values = current_values(key)
    if values is None or param not in values:
        raise KeyError(f"{key}.{param}")
    return values[param]


def in_force(key: str) -> bool:
    return Law.objects.filter(key=key, status=LawStatus.IN_FORCE.value).exists()


def context() -> catalog.LawContext:
    return catalog.LawContext(value_of=value)
