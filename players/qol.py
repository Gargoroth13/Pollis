"""
QoL (design/04 §3-4), SEMPRE derivada e SEMPRE explicada (doc 20; 04 §25).

  QoL Base           = 0,50 + modificadores estruturais        (§4.1)
  QoL Base efetiva   = QoL Base - penalidade temporária de Burnout Ativo   (§4.2, §7.3)
  QoL Atual          = QoL Base efetiva + efeitos temporários ativos
                       - debuff de Saúde Crítica               (§4.3, §12)

Nada é guardado: o valor é recalculado do estado, então a penalidade do Burnout e os efeitos
temporários terminam sozinhos e a QoL Base estrutural nunca é reescrita (§7.3).

Sem teto nem piso: o 04 não define escala (QoL > 1,00 dá bônus de regeneração, §2.3).

Pontos de extensão: moradia, bens, condições sociais, localização, instituições (§4.1) ainda não
existem; cada sistema registra seu provedor aqui, definindo o PRÓPRIO modificador (§4.1, §29.3:
"o documento 04 não deve inventar parâmetros pertencentes a outros sistemas").
"""
from __future__ import annotations

from decimal import Decimal
from typing import Callable, Dict, Optional

from core.breakdown import Calc, Explained
from .balance import Balance, get_balance
from .models import Player

Provider = Callable[[Player, int], Optional[Decimal]]
_providers: Dict[str, Provider] = {}
_RESERVED = {"baseline", "burnout", "qol_base_effective", "critical_health", "structural"}


def register_qol_base_provider(name: str, fn: Provider) -> None:
    """Um sistema (ex.: moradia) soma uma parcela à QoL Base. `fn(player, at)` -> Decimal ou None."""
    if name in _RESERVED or name.startswith("effect:"):
        raise ValueError(f"Nome de provedor reservado: {name}")
    if name in _providers:
        raise ValueError(f"Provedor de QoL Base duplicado: {name}")
    _providers[name] = fn


def clear_qol_base_providers() -> None:  # para testes
    _providers.clear()


def qol_base(player: Player, at: int, bal: Optional[Balance] = None) -> Explained:
    """QoL Base estrutural."""
    bal = bal or get_balance()
    calc = Calc("baseline", bal.qol_base_baseline)
    for name in sorted(_providers):  # ordem determinística
        amount = _providers[name](player, at)
        if amount:
            calc.add(name, amount)
    return calc.result(at)


def qol_base_effective(player: Player, at: int, bal: Optional[Balance] = None,
                       structural: Optional[Explained] = None) -> Explained:
    """QoL Base com a penalidade de Burnout Ativo. É a que a regeneração de Energia usa (04 §2.3)."""
    bal = bal or get_balance()
    structural = structural or qol_base(player, at, bal)
    calc = Calc("structural", structural.value, detail=structural)  # hierarquia (20.6)
    if player.burnout_active:
        calc.add("burnout", -bal.burnout_qol_penalty)
    return calc.result(at)


def qol_current(player: Player, at: int, bal: Optional[Balance] = None,
                effective: Optional[Explained] = None) -> Explained:
    bal = bal or get_balance()
    effective = effective or qol_base_effective(player, at, bal)
    calc = Calc("qol_base_effective", effective.value, detail=effective)
    for effect in player.qol_effects.filter(starts_at__lte=at, expires_at__gt=at).order_by("category"):
        calc.add(f"effect:{effect.category}", effect.amount)
    if player.health_critical:
        calc.add("critical_health", -bal.critical_health_qol_debuff)
    return calc.result(at)
