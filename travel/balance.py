"""
Parâmetros de Localização e Viagem (design/04 §6, §20, §21, §24).

Categorias (mesmo padrão dos outros balance.py):
  [04]     regra DEFINIDA no documento.
  [ABERTO] DECISÃO DE DESIGN não fechada: configuração, nunca regra definitiva. Listadas em CHANGELOG_DEV.md.

`travel_minutes_per_unit` NÃO está aqui: é parâmetro de CENÁRIO da Geografia (geography.balance.Scenario, valor
inicial de calibração 15, 04 §21). Sobrescrever: settings.POLIS_TRAVEL_BALANCE = {...}.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from typing import Dict, Tuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PLAYER_STATES = ("hospitalized", "health_critical", "burnout_active")
ACTIONS = ("work", "study", "leisure")


@dataclass(frozen=True)
class TravelBalance:
    # [ABERTO 04 §6, §20] Quais ações dependem de presença física? O 04 só diz: o Trabalho, "quando exigir presença
    # física no local", e "ações que dependam de presença física". Isto é o padrão QUANDO a atividade não informa
    # (ActivityContext.requires_presence): Trabalho sim; Estudo e Lazer não, porque o design não os cita.
    presence_dependent_by_default: Dict[str, bool] = field(
        default_factory=lambda: {"work": True, "study": False, "leisure": False})

    # [ABERTO] Estados do jogador que IMPEDEM iniciar uma viagem. O 04 não define nenhum: vazio = nada impede.
    # Valores aceitos: hospitalized, health_critical, burnout_active.
    travel_blocking_states: Tuple[str, ...] = ()

    def validate(self) -> "TravelBalance":
        e = []
        if set(self.presence_dependent_by_default) != set(ACTIONS):
            e.append(f"presence_dependent_by_default deve definir exatamente {ACTIONS}")
        if not set(self.travel_blocking_states) <= set(PLAYER_STATES):
            e.append(f"travel_blocking_states só aceita {PLAYER_STATES}")
        if e:
            raise ImproperlyConfigured("POLIS_TRAVEL_BALANCE inválido: " + "; ".join(e))
        return self


_FIELDS = {f.name for f in fields(TravelBalance)}


def get_travel_balance() -> TravelBalance:
    overrides = getattr(settings, "POLIS_TRAVEL_BALANCE", None) or {}
    unknown = set(overrides) - _FIELDS
    if unknown:
        raise ImproperlyConfigured(f"POLIS_TRAVEL_BALANCE tem chaves desconhecidas: {sorted(unknown)}")
    base = TravelBalance()
    changes = {}
    for key, value in overrides.items():
        changes[key] = ({**base.presence_dependent_by_default, **value} if key == "presence_dependent_by_default"
                        else tuple(value))
    return replace(base, **changes).validate()
