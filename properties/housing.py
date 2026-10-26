"""
Moradia (design/10 §6.1, §14-15; 05 §8): unidades, quem tem direito de morar nelas, residência ativa e o QoL do imóvel.

Direito de morar numa unidade: ser o PROPRIETÁRIO (jogador) do imóvel com a unidade sem contrato de aluguel em vigor, ou ser o INQUILINO de um
contrato `rent` em vigor que já começou (`starts_on` alcançado: 10 §9 "pagamento do aluguel → ocupação"). Empresa não mora. A moradia
INICIAL (04 §24, 10 §14) é o estado SEM linha em `ActiveResidence`: garantida, básica, neutra em QoL, fora da capacidade.

PROTOCOLO de trava: jogador → lote → (contrato). A residência, a venda e a ativação do aluguel travam o MESMO lote antes de decidir.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from django.db import transaction

from contracts.constants import RUNNING_STATUSES, ContractType
from contracts.models import Contract
from core import clock as game_clock
from geography.models import Lot
from ledger.money import competence_day_of
from players.models import Player
from players.services import ActionResult

from .common import positive, refuse
from .constants import OwnerKind
from .models import ActiveResidence, Building, Tenancy, Unit
from .titles import owner_of_lot

PROVIDER_NAME = "residence_building"


def create_units(building: Building) -> None:
    Unit.objects.bulk_create([Unit(building=building, index=i) for i in range(1, building.units + 1)])


def running_lease(unit_id: int) -> Optional[Contract]:
    """O contrato de aluguel em vigor da unidade (no máximo um: a ativação trava o lote)."""
    ids = list(Tenancy.objects.filter(unit_id=unit_id).values_list("contract_id", flat=True))
    if not ids:
        return None
    return Contract.objects.filter(pk__in=ids, type=ContractType.RENT.value, status__in=[s.value for s in RUNNING_STATUSES]).order_by("id").first()


def entitlement(player_id: int, unit: Unit, today: Optional[int] = None) -> Optional[str]:
    """`owner`, `tenant` ou None. Só LÊ; quem decide algo com isso trava o lote antes."""
    today = competence_day_of(game_clock.now()) if today is None else today
    lease = running_lease(unit.pk)
    if lease is not None:
        tenancy = Tenancy.objects.get(contract_id=lease.pk)
        mine = (tenancy.tenant_kind, tenancy.tenant_id) == (OwnerKind.PLAYER.value, player_id)
        return "tenant" if mine and (lease.starts_on is None or lease.starts_on <= today) else None
    kind, owner = owner_of_lot(unit.building.lot_id)
    return "owner" if (kind is OwnerKind.PLAYER and owner == player_id) else None


def residence_refusal(player_id: Any, unit_id: Any) -> Optional[ActionResult]:
    """`unit_id` None = voltar à moradia inicial (sempre permitido)."""
    if not positive(player_id) or not Player.objects.filter(pk=player_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(player_id)[:40])
    if unit_id is None:
        return None
    if not positive(unit_id):
        return refuse("INVALID_PARAMS", unit=repr(unit_id)[:30])
    unit = Unit.objects.select_related("building").filter(pk=unit_id).first()
    if unit is None:
        return refuse("UNIT_NOT_FOUND", unit=unit_id)
    current = ActiveResidence.objects.filter(player_id=player_id).first()
    if current is not None and current.unit_id == unit.pk:
        return refuse("ALREADY_RESIDENT", unit=unit.pk)
    other = ActiveResidence.objects.filter(unit=unit).exclude(player_id=player_id).first()
    if other is not None:
        return refuse("UNIT_OCCUPIED", unit=unit.pk)
    if entitlement(player_id, unit) is None:
        return refuse("NOT_ENTITLED_TO_UNIT", unit=unit.pk)
    return None


def set_residence(player_id: Any, unit_id: Any) -> ActionResult:
    """
    Define a residência ativa (05 §8): uma unidade que o jogador possui sem aluguel em vigor, ou alugou e já começou; `unit` nulo = volta à
    moradia inicial. Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS, UNIT_NOT_FOUND, ALREADY_RESIDENT, UNIT_OCCUPIED, NOT_ENTITLED_TO_UNIT.
    """
    if not positive(player_id) or not Player.objects.filter(pk=player_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(player_id)[:40])
    with transaction.atomic():
        list(Player.objects.select_for_update().filter(pk=player_id))
        if positive(unit_id):
            lot_id = Unit.objects.filter(pk=unit_id).values_list("building__lot_id", flat=True).first()
            if lot_id is not None:
                list(Lot.objects.select_for_update().filter(pk=lot_id))
        refusal = residence_refusal(player_id, unit_id)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        ActiveResidence.objects.filter(player_id=player_id).delete()
        if unit_id is None:
            return ActionResult(True, "OK", {"unit": None, "housing": "initial"})
        ActiveResidence.objects.create(player_id=player_id, unit_id=unit_id, since=now)
        return ActionResult(True, "OK", {"unit": unit_id, "housing": "unit"})


def drop_unentitled_residents(lot_id: int) -> int:
    """Depois de a propriedade ou os aluguéis do lote mudarem: quem já não tem direito à unidade volta à moradia inicial. O lote deve estar travado."""
    dropped = 0
    today = competence_day_of(game_clock.now())
    for row in ActiveResidence.objects.select_related("unit__building").filter(unit__building__lot_id=lot_id):
        if entitlement(row.player_id, row.unit, today) is None:
            row.delete()
            dropped += 1
    return dropped


def qol_bonus(player: Player, at: int) -> Optional[Decimal]:
    """QoL Base: o bônus do imóvel da residência ativa (10 §7); moradia inicial = neutra (sem parcela)."""
    row = ActiveResidence.objects.select_related("unit__building").filter(player_id=player.pk).first()
    return None if row is None else row.unit.building.qol_bonus


def unit_view(unit_id: int) -> Optional[Dict[str, Any]]:
    unit = Unit.objects.select_related("building").filter(pk=unit_id).first()
    if unit is None:
        return None
    kind, owner = owner_of_lot(unit.building.lot_id)
    lease = running_lease(unit.pk)
    resident = ActiveResidence.objects.filter(unit=unit).values_list("player_id", flat=True).first()
    from .models import RentListing
    listing = RentListing.objects.filter(unit=unit, status="open").first()
    return {"unit": unit.pk, "index": unit.index, "building": unit.building_id, "lot": unit.building.lot_id, "kind": unit.building.kind,
            "qol_bonus": str(unit.building.qol_bonus), "owner": [kind.value, owner], "resident": resident,
            "lease": None if lease is None else {"contract": lease.pk, "amount_cents": lease.terms["amount_cents"],
                                                 "frequency": lease.frequency, "starts_on": lease.starts_on, "ends_on": lease.ends_on},
            "rent_listing": None if listing is None else {"id": listing.pk, "amount_cents": listing.amount_cents,
                                                         "frequency": listing.frequency}}


def residence_view(player_id: int) -> Dict[str, Any]:
    row = ActiveResidence.objects.select_related("unit__building").filter(player_id=player_id).first()
    if row is None:
        return {"housing": "initial", "unit": None, "qol_bonus": "0"}          # 04 §24: garantida, básica, neutra
    return {"housing": "unit", "unit": row.unit_id, "lot": row.unit.building.lot_id, "kind": row.unit.building.kind,
            "qol_bonus": str(row.unit.building.qol_bonus), "since": row.since}
