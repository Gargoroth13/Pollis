"""
Cenário do mundo (design/08). Mesmas categorias de players/balance.py e skills/balance.py:

  [08]     valor ou regra DEFINIDO no documento.
  [PROV]   parâmetro de CENÁRIO provisório. O 08 §19 diz que o mapa do Bot Test é um cenário de teste e que
           "não deve ser tratado como regra permanente do mundo final". O sistema precisa de um número para
           gerar um mundo; NÃO é decisão de design. Listado em CHANGELOG_DEV.md.
  [ABERTO] DECISÃO DE DESIGN não fechada. Configuração com a interpretação mais literal como padrão, nunca como
           regra definitiva. (Nenhuma aberta no momento: as três do P0.06 foram fechadas em 2026-10-03.)

Sobrescrever sem mexer em código: settings.POLIS_GEOGRAPHY = {"states": 3, "seed": 7, "lot_capacity": {"rural": 10}, ...}
Unidade de distância: "unidade de grid". Tempo-base de viagem = distância × travel_minutes_per_unit (04 §21; 15 é o valor inicial de calibração).
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from decimal import Decimal
from typing import Dict, Mapping, Optional, Tuple

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.breakdown import D
from .constants import (CAPACITY_BASE, CATEGORY_NAMES, CATEGORIES, DISTANCE_METRICS, NEIGHBORHOODS_PER_CITY,
                        RARITY_BASE, RESOURCE_NAMES, Category, Resource)


def _default_rarity() -> Dict[Resource, Decimal]:
    r = dict(RARITY_BASE)
    r[Resource.OIL] = Decimal("0.03")  # [PROV] o 08 §14 só diz "raro"; o valor pertence a Produtos (22)
    return r


def _default_type_counts() -> Dict[Category, int]:
    # [PROV] o 08 §3.1 só pede que a cidade REPRESENTE centro, intermediário, periferia, expansão, rural/especial;
    # não define quantos bairros de cada tipo. Soma = 25.
    return {Category.INSTITUTIONAL: 3, Category.COMMERCIAL: 5, Category.RESIDENTIAL: 10,
            Category.SPECIAL: 1, Category.INDUSTRIAL: 3, Category.RURAL: 3}


@dataclass(frozen=True)
class Scenario:
    name: str = "bot_test_default"
    seed: int = 1                                       # reprodutibilidade (design/21 §21.49)

    # --- Estrutura [08] ----------------------------------------------------
    neighborhoods_per_city: int = NEIGHBORHOODS_PER_CITY  # [08 §3.1] "inicialmente 25"; cenários de teste podem mudar (§19)
    lot_capacity: Dict[Category, int] = field(default_factory=lambda: dict(CAPACITY_BASE))  # [08 §6] "parâmetros do sistema"
    resource_rarity: Dict[Resource, Decimal] = field(default_factory=_default_rarity)       # [08 §15]; petróleo [PROV]

    # --- Cenário [PROV] ----------------------------------------------------
    states: int = 2
    cities_per_state: int = 2
    neighborhood_type_counts: Dict[Category, int] = field(default_factory=_default_type_counts)
    # Ordem dos tipos do centro para a periferia (os bairros são gerados em ordem crescente de distância ao centro).
    type_order_from_center: Tuple[Category, ...] = (Category.INSTITUTIONAL, Category.COMMERCIAL, Category.RESIDENTIAL,
                                                    Category.SPECIAL, Category.INDUSTRIAL, Category.RURAL)
    rural_lots_per_neighborhood: int = 40               # 08 §6: rural "definida pela estrutura territorial"
    state_spacing: Decimal = D(20)                      # unidades de grid entre estados
    city_spacing: Decimal = D(6)                        # entre cidades do mesmo estado
    city_radius: Decimal = D("1.5")                     # raio da cidade (distância do centro ao bairro mais externo)
    lot_spacing: Decimal = D("0.01")                    # entre lotes dentro de um bairro
    hotspots_per_resource: int = 3                      # concentrações regionais por recurso (08 §13)
    hotspot_sigma: Decimal = D(2)                       # alcance de cada concentração, em unidades de grid

    # Capital de cada estado (08 §2 exige UMA capital, sem dizer qual): índice, dentro do estado, da cidade que é a capital.
    # 0 = a primeira. É configuração do CENÁRIO, não regra universal do jogo.
    capital_city_index: int = 0
    # Tempo-base de viagem = distância × minutos_por_unidade (04 §21). 15 é só o valor INICIAL de calibração do Bot Test,
    # não balanceamento definitivo. Veículos e demais modificadores NÃO existem aqui: pertencem ao sistema de viagem.
    travel_minutes_per_unit: Decimal = D(15)

    # --- Decididas pelo Game Director (2026-10-03) ---------------------------
    # Composição de lotes: leitura A. Cada bairro tem um tipo predominante e a quantidade de lotes da capacidade desse
    # tipo (lot_capacity; rural: rural_lots_per_neighborhood). NÃO há opção de composição: a leitura B (todas as
    # categorias em todos os bairros) foi descartada. QUANTOS bairros de cada tipo existem nas 25 posições de uma
    # cidade segue sendo cenário provisório (neighborhood_type_counts), não regra do jogo.
    # Métrica de distância: euclidiana por padrão (a configuração existe para calibração do Bot Test).
    distance_metric: str = "euclidean"
    # Usos "relativamente separados" (08 §16): a mistura é permitida CONFORME O ZONEAMENTO. Não há regra de distância
    # entre tipos de uso; restrições assim virão de leis/zoneamento quando esse sistema existir. None = cada categoria
    # admite o próprio uso e as misturas entram por esta matriz ou por overrides de lei.
    zoning_permissions: Optional[Dict[Category, Tuple[Category, ...]]] = None

    # ------------------------------------------------------------------
    def expected_composition(self, neighborhood_type: Category) -> Dict[Category, int]:
        """
        Quantos lotes de cada categoria um bairro deste tipo tem (leitura A): só lotes do próprio tipo, na
        quantidade da capacidade daquele tipo.
        """
        n = self.rural_lots_per_neighborhood if neighborhood_type is Category.RURAL else self.lot_capacity[neighborhood_type]
        return {neighborhood_type: n} if n > 0 else {}

    def validate(self) -> "Scenario":
        e = []
        if self.seed != int(self.seed):
            e.append("seed deve ser inteiro")
        for name in ("states", "cities_per_state", "neighborhoods_per_city"):
            if getattr(self, name) < 1:
                e.append(f"{name} deve ser >= 1")
        if set(self.lot_capacity) - {c for c in CATEGORIES if c is not Category.RURAL}:
            e.append("lot_capacity só aceita residential, commercial, industrial, institutional, special (rural: rural_lots_per_neighborhood)")
        if any(v < 0 or v != int(v) for v in self.lot_capacity.values()) or self.rural_lots_per_neighborhood < 0:
            e.append("capacidades devem ser inteiros >= 0")
        counts = self.neighborhood_type_counts
        if any(v < 0 for v in counts.values()):
            e.append("neighborhood_type_counts não pode ter valor negativo")
        if sum(counts.values()) != self.neighborhoods_per_city:
            e.append(f"neighborhood_type_counts deve somar neighborhoods_per_city ({self.neighborhoods_per_city}); soma = {sum(counts.values())}")
        used = {c for c, n in counts.items() if n > 0}
        if not used <= set(self.type_order_from_center):
            e.append("type_order_from_center deve conter todos os tipos com bairros")
        if len(set(self.type_order_from_center)) != len(self.type_order_from_center):
            e.append("type_order_from_center não pode repetir tipos")
        if any(not 0 <= r <= 1 for r in self.resource_rarity.values()):
            e.append("resource_rarity deve estar em [0, 1]")
        if set(self.resource_rarity) - set(Resource):
            e.append("resource_rarity tem recurso desconhecido")
        if self.distance_metric not in DISTANCE_METRICS:
            e.append(f"distance_metric deve ser um de {DISTANCE_METRICS}")
        for name in ("state_spacing", "city_spacing", "city_radius", "lot_spacing", "hotspot_sigma"):
            if getattr(self, name) <= 0:
                e.append(f"{name} deve ser > 0")
        if not 0 <= self.capital_city_index < self.cities_per_state:
            e.append(f"capital_city_index deve estar em [0, cities_per_state) = [0, {self.cities_per_state})")
        if self.travel_minutes_per_unit <= 0:
            e.append("travel_minutes_per_unit deve ser > 0")
        if self.hotspots_per_resource < 1:
            e.append("hotspots_per_resource deve ser >= 1")
        if self.zoning_permissions is not None and any(not set(v) <= set(Category) for v in self.zoning_permissions.values()):
            e.append("zoning_permissions tem categoria desconhecida")
        if e:
            raise ImproperlyConfigured("POLIS_GEOGRAPHY inválido: " + "; ".join(e))
        return self


_FIELDS = {f.name for f in fields(Scenario)}
_CAT_MAP_FIELDS = {"lot_capacity", "neighborhood_type_counts"}


def _cat(k) -> Category:
    return k if isinstance(k, Category) else Category(k)


def get_scenario(**overrides) -> Scenario:
    """Padrão + settings.POLIS_GEOGRAPHY + overrides explícitos, validado. Mapas são mesclados por chave."""
    merged = dict(getattr(settings, "POLIS_GEOGRAPHY", None) or {})
    merged.update(overrides)
    unknown = set(merged) - _FIELDS
    if unknown:
        raise ImproperlyConfigured(f"POLIS_GEOGRAPHY tem chaves desconhecidas: {sorted(unknown)}")
    base = Scenario()
    changes = {}
    for key, value in merged.items():
        if key == "lot_capacity":
            changes[key] = {**base.lot_capacity, **{_cat(k): int(v) for k, v in value.items()}}
        elif key == "neighborhood_type_counts":
            changes[key] = {_cat(k): int(v) for k, v in value.items()}                      # substitui (a soma importa)
        elif key == "resource_rarity":
            changes[key] = {**base.resource_rarity, **{(k if isinstance(k, Resource) else Resource(k)): D(str(v) if isinstance(v, float) else v) for k, v in value.items()}}
        elif key == "type_order_from_center":
            changes[key] = tuple(_cat(c) for c in value)
        elif key == "zoning_permissions":
            changes[key] = None if value is None else {_cat(c): tuple(_cat(x) for x in uses) for c, uses in value.items()}
        elif key in ("state_spacing", "city_spacing", "city_radius", "lot_spacing", "hotspot_sigma", "travel_minutes_per_unit"):
            changes[key] = D(str(value) if isinstance(value, float) else value)
        elif key in ("seed", "states", "cities_per_state", "neighborhoods_per_city", "rural_lots_per_neighborhood", "hotspots_per_resource", "capital_city_index"):
            changes[key] = int(value)
        else:
            changes[key] = value
    return replace(base, **changes).validate()
