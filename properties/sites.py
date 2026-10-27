"""
Localização de empresas (design/10 §16-17, §29; 02 §2.1, §5.2; 08 §8, §9, §12).

O QUE O DESIGN DEFINE e esta etapa implementa:
  - a empresa opera num lote, e o uso do lote tem de ser o do seu tipo (Matriz rural, Industrial industrial, Varejo/Serviços comercial),
    segundo o ZONEAMENTO (10 §22: consulta `geography.zoning`, não duplica a regra);
  - a categoria da Matriz é a do TERRENO onde ela está (02 §2.1). O terreno rural é decidido por `terrain_of`, ÚNICO ponto de troca: o 08 não define o
    tipo de um lote rural SEM depósito, então vale a REGRA A PROVISÓRIA do GD (2026-10-27, design/10a G12): produtos comuns (Agropecuária e Extrativismo
    não-petróleo) em qualquer lote rural; produtos de depósito (petróleo e os 9 minerais; `Product.resource`) só onde há o depósito. A opção B (tipo
    de terreno gerado por lote) troca só `terrain_of`;

O QUE ESTA ETAPA NÃO FAZ (depende de G5/G6 ou de regra não definida; ver design/10a §9): tipos de imóvel comercial/industrial e estrela → nível
(G5), mudança de uso (G6), exigir localização para operar (Varejo/Industrial/Serviços) e aluguel comercial.

PROTOCOLO de trava: jogador → empresa → lote (o mesmo da venda, que trava o lote antes de decidir).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Optional

from django.db import transaction

from catalog import services as catalog
from catalog.constants import Sector
from catalog.models import Product
from companies import production
from companies.constants import CompanyType
from companies.models import Company
from core import clock as game_clock
from geography import zoning
from geography.constants import Occupation, Resource
from geography.models import Lot, ResourceDeposit
from players.models import Player
from players.services import ActionResult

from . import params
from .common import authority, is_int, lock, positive, refuse
from .constants import ListingStatus, OwnerKind, SiteStatus
from .models import Building, CompanyLocation, ConstructionSite, Listing
from .titles import owner_of_lot

PROVIDER_NAME = "properties_site"
KEYS = frozenset({"company", "lot"})


# --- terreno da Matriz -------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Terrain:
    """O que o terreno rural sustenta (02 §2.1). `products` = chaves permitidas; as categorias saem dos produtos. `why` é o detalhamento (20)."""
    products: FrozenSet[str]
    common: FrozenSet[str]
    deposits: FrozenSet[str]
    rule: str
    why: Dict[str, Any]

    @property
    def categories(self) -> FrozenSet:
        return frozenset(catalog.producer_sector_of(key) for key in self.products)


def deposit_products(lot_id: int) -> FrozenSet[str]:
    """Produtos de depósito do lote: um por depósito (a chave do recurso é a do produto)."""
    return frozenset(ResourceDeposit.objects.filter(lot_id=lot_id).values_list("resource", flat=True))


def common_products() -> FrozenSet[str]:
    """Matérias-primas de Agropecuária/Extrativismo SEM recurso espacial (as de depósito são o petróleo e os 9 minerais)."""
    return frozenset(Product.objects.filter(sector__in=[Sector.AGRO.value, Sector.EXTRACTIVE.value], resource__isnull=True)
                     .values_list("key", flat=True))


def terrain_of(lot_id: int) -> Terrain:
    """
    PONTO ÚNICO DE TROCA do terreno rural. Regra A provisória (G12; `params.TERRAIN_RULE`): lote sem depósito sustenta os produtos comuns; lote com
    depósito sustenta o(s) recurso(s) do depósito e, se `DEPOSIT_LOTS_ALSO_COMMON`, também os comuns. A opção B (tipo de terreno gerado por lote)
    substitui só esta função; os provedores abaixo e `companies.production` não mudam.
    """
    deposits = deposit_products(lot_id)
    common = common_products()
    with_common = not deposits or params.DEPOSIT_LOTS_ALSO_COMMON
    products = deposits | (common if with_common else frozenset())
    return Terrain(products=products, common=common if with_common else frozenset(), deposits=deposits, rule=params.TERRAIN_RULE,
                   why={"rule": params.TERRAIN_RULE, "provisional": True, "deposits": sorted(deposits), "common_allowed": with_common,
                        "deposit_lots_also_common": params.DEPOSIT_LOTS_ALSO_COMMON})


def _located_lot(company_id: int) -> Optional[int]:
    return CompanyLocation.objects.filter(company_id=company_id).values_list("lot_id", flat=True).first()


def _matrix_terrain(company_id: int) -> Optional[Terrain]:
    company = Company.objects.filter(pk=company_id).first()
    if company is None or CompanyType(company.type) is not CompanyType.MATRIX:
        return None
    lot_id = _located_lot(company_id)
    return None if lot_id is None else terrain_of(lot_id)


def terrain_categories(company_id: int) -> Optional[FrozenSet]:
    """Provedor de terreno da Matriz (`production.register_site_provider`). None = a empresa não está localizada num lote."""
    terrain = _matrix_terrain(company_id)
    return None if terrain is None else terrain.categories


def terrain_products(company_id: int) -> Optional[FrozenSet[str]]:
    terrain = _matrix_terrain(company_id)
    return None if terrain is None else terrain.products


# --- localizar a empresa -------------------------------------------------------------------------------------------------------

def required_use(company_type: str):
    try:
        return params.COMPANY_SITE_USE.get(CompanyType(company_type))
    except ValueError:
        return None


def location_refusal(actor_id: Any, target: Any) -> Optional[ActionResult]:
    """Recusas que só LEEM. `lot` nulo = a empresa deixa o lote (sem recusas além das de autoridade)."""
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    if not isinstance(target, dict) or set(target) != KEYS:
        return refuse("INVALID_PARAMS", expected=sorted(KEYS))
    company_id, lot_id = target["company"], target["lot"]
    if not positive(company_id) or (lot_id is not None and not positive(lot_id)):
        return refuse("INVALID_PARAMS", company=repr(company_id)[:30], lot=repr(lot_id)[:30])
    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return refuse("COMPANY_NOT_FOUND", company=company_id)
    refusal = authority(actor_id, OwnerKind.COMPANY, company_id)
    if refusal is not None:
        return refusal
    if lot_id is None:
        return None if CompanyLocation.objects.filter(company=company).exists() else refuse("NOT_LOCATED", company=company_id)
    use = required_use(company.type)
    if use is None:
        return refuse("COMPANY_TYPE_NOT_LOCATED", company_type=company.type,
                      locatable=sorted(t.value for t in params.COMPANY_SITE_USE))
    lot = Lot.objects.filter(pk=lot_id).first()
    if lot is None:
        return refuse("LOT_NOT_FOUND", lot=lot_id)
    if owner_of_lot(lot.pk) != (OwnerKind.COMPANY, company_id):
        return refuse("LOT_NOT_OWNED_BY_COMPANY", lot=lot_id, company=company_id)       # J1: a empresa só ocupa lote que possui
    here = CompanyLocation.objects.filter(lot=lot).first()
    if here is not None:
        return refuse("ALREADY_LOCATED_HERE" if here.company_id == company_id else "LOT_HAS_COMPANY", lot=lot_id)    # J3: uma empresa por lote
    if Building.objects.filter(lot=lot).exists():
        return refuse("LOT_HAS_BUILDING", lot=lot_id)              # imóvel residencial não é imóvel comercial/industrial (G5 define os que são)
    if (ConstructionSite.objects.filter(lot=lot, status=SiteStatus.ACTIVE.value).exists()
            or Listing.objects.filter(lot=lot, status=ListingStatus.OPEN.value).exists()):
        return refuse("LOT_RESERVED", lot=lot_id)
    if not zoning.is_use_allowed(lot, use):
        return refuse("LOT_USE_NOT_ALLOWED", lot=lot_id, category=lot.category, use=use.value)
    return None


def _set_occupation(lot_id: int, occupied: bool) -> None:
    if occupied:
        Lot.objects.filter(pk=lot_id).update(occupation=Occupation.OCCUPIED.value)
    elif not Building.objects.filter(lot_id=lot_id).exists() and not CompanyLocation.objects.filter(lot_id=lot_id).exists():
        Lot.objects.filter(pk=lot_id).update(occupation=Occupation.EMPTY.value)


def set_company_location(actor_id: Any, target: Any) -> ActionResult:
    """
    O Dono localiza a empresa num lote que ela possui, ou a tira do lote (`lot` nulo). Mudar de lote é imediato e sem custo (J5). Recusas:
    PLAYER_NOT_FOUND, INVALID_PARAMS, COMPANY_NOT_FOUND, NOT_OWNER, NOT_LOCATED, COMPANY_TYPE_NOT_LOCATED, LOT_NOT_FOUND,
    LOT_NOT_OWNED_BY_COMPANY, ALREADY_LOCATED_HERE, LOT_HAS_COMPANY, LOT_HAS_BUILDING, LOT_RESERVED, LOT_USE_NOT_ALLOWED.
    """
    if not positive(actor_id) or not Player.objects.filter(pk=actor_id).exists():
        return refuse("PLAYER_NOT_FOUND", player=repr(actor_id)[:40])
    company_id = target.get("company") if isinstance(target, dict) else None
    lot_id = target.get("lot") if isinstance(target, dict) else None
    with transaction.atomic():
        lock(actor_id, [(OwnerKind.COMPANY, company_id)] if positive(company_id) else [])
        old = _located_lot(company_id) if positive(company_id) else None
        for lid in sorted({x for x in (old, lot_id) if positive(x)}):
            list(Lot.objects.select_for_update().filter(pk=lid))                                  # lotes em ordem crescente
        refusal = location_refusal(actor_id, target)
        if refusal is not None:
            return refusal
        CompanyLocation.objects.filter(company_id=company_id).delete()
        if old is not None:
            _set_occupation(old, False)
        if lot_id is None:
            return ActionResult(True, "OK", {"company": company_id, "lot": None, "left": old})
        CompanyLocation.objects.create(company_id=company_id, lot_id=lot_id, since=game_clock.now())
        _set_occupation(lot_id, True)
        return ActionResult(True, "OK", {"company": company_id, "lot": lot_id, "left": old})


def drop_location_of_lot(lot_id: int) -> Optional[int]:
    """A propriedade do lote mudou: a empresa que o ocupava (por ser dona) deixa de operar nele. O lote deve estar travado."""
    row = CompanyLocation.objects.filter(lot_id=lot_id).first()
    if row is None:
        return None
    company_id = row.company_id
    row.delete()
    _set_occupation(lot_id, False)
    return company_id


def location_view(company_id: int) -> Optional[Dict[str, Any]]:
    row = CompanyLocation.objects.filter(company_id=company_id).select_related("lot").first()
    if row is None:
        return None
    terrain = terrain_of(row.lot_id)
    return {"company": company_id, "lot": row.lot_id, "category": row.lot.category, "since": row.since,
            "deposit_products": sorted(terrain.deposits), "terrain_products": sorted(terrain.products),
            "terrain_defined": bool(terrain.products), "terrain": terrain.why}


def register() -> None:
    production.register_site_provider(PROVIDER_NAME, terrain_categories)
    production.register_site_product_provider(PROVIDER_NAME, terrain_products)
