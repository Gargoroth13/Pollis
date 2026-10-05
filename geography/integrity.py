"""
Integridade territorial. Verifica que o mundo guardado respeita a estrutura do design/08 E o cenário em vigor.

Devolve um relatório ESTRUTURADO (códigos estáveis), não lança exceção: serve a testes, ao comando `check_world`
e ao painel de observabilidade dos Bots (21), que precisam distinguir *qual* regra foi violada.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from django.db.models import Count

from . import resources
from .balance import Scenario, get_scenario
from .constants import RESOURCES, Category
from .generator import neighborhood_types
from .models import City, Lot, Neighborhood, ResourceDeposit, State


@dataclass(frozen=True)
class Violation:
    code: str
    detail: str


@dataclass
class IntegrityReport:
    violations: List[Violation] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def codes(self) -> List[str]:
        return sorted({v.code for v in self.violations})

    def add(self, code: str, detail: str) -> None:
        self.violations.append(Violation(code, detail))


def check_integrity(scenario: Optional[Scenario] = None) -> IntegrityReport:
    sc = scenario or get_scenario()
    r = IntegrityReport()
    states = list(State.objects.all())
    r.stats = {"states": len(states), "cities": City.objects.count(),
               "neighborhoods": Neighborhood.objects.count(), "lots": Lot.objects.count(),
               "deposits": ResourceDeposit.objects.count()}
    if not states:
        r.add("EMPTY_WORLD", "não há nenhum estado")
        return r

    # --- Estado: >= 1 cidade e uma capital dentro do próprio estado (08 §2) --------------------------------------
    city_state = dict(City.objects.values_list("id", "state_id"))
    cities_per_state = Counter(city_state.values())
    for s in states:
        if cities_per_state[s.id] < 1:
            r.add("STATE_WITHOUT_CITY", s.name)
        if s.capital_id is None:
            r.add("STATE_WITHOUT_CAPITAL", s.name)
        elif city_state.get(s.capital_id) != s.id:
            r.add("CAPITAL_NOT_IN_STATE", s.name)

    # --- Cidade: nº de bairros e plano de tipos (08 §3.1) ---------------------------------------------------------
    expected_plan = Counter({t.value: n for t, n in Counter(neighborhood_types(sc)).items()})
    per_city: Dict[int, Counter] = defaultdict(Counter)
    for city_id, zoning in Neighborhood.objects.values_list("city_id", "zoning"):
        per_city[city_id][zoning] += 1
    for city in City.objects.all():
        counter = per_city.get(city.id, Counter())
        if sum(counter.values()) != sc.neighborhoods_per_city:
            r.add("CITY_WRONG_NEIGHBORHOOD_COUNT", f"{city.name}: {sum(counter.values())} != {sc.neighborhoods_per_city}")
        elif counter != expected_plan:
            r.add("CITY_TYPE_PLAN_MISMATCH", f"{city.name}: {dict(counter)} != {dict(expected_plan)}")

    # --- Bairro: composição de lotes (08 §6) e índices contíguos ---------------------------------------------------
    lots_by_hood: Dict[int, List[tuple]] = defaultdict(list)
    for hood_id, idx, cat in Lot.objects.values_list("neighborhood_id", "index", "category"):
        lots_by_hood[hood_id].append((idx, cat))
    for hood in Neighborhood.objects.all():
        entries = lots_by_hood.get(hood.id, [])
        expected = {c.value: n for c, n in sc.expected_composition(Category(hood.zoning)).items()}
        if dict(Counter(cat for _, cat in entries)) != expected:
            r.add("NEIGHBORHOOD_LOT_COMPOSITION_MISMATCH", f"{hood.name}: {dict(Counter(c for _, c in entries))} != {expected}")
        if sorted(i for i, _ in entries) != list(range(len(entries))):
            r.add("LOT_INDEX_GAP", hood.name)

    # --- Coordenadas únicas entre irmãos (nada sobreposto) ---------------------------------------------------------
    for label, qs, parent in (("STATE", State.objects.all(), None), ("CITY", City.objects.all(), "state_id"),
                              ("NEIGHBORHOOD", Neighborhood.objects.all(), "city_id"), ("LOT", Lot.objects.all(), "neighborhood_id")):
        keys = ["x", "y"] + ([parent] if parent else [])
        for row in qs.values(*keys).annotate(n=Count("id")).filter(n__gt=1):
            r.add(f"DUPLICATE_{label}_COORDINATES", str({k: str(row[k]) for k in keys}))

    # --- Recursos: só em lote rural; frequência global = raridade (08 §13-15) ---------------------------------------
    bad = ResourceDeposit.objects.exclude(lot__category=Category.RURAL.value).count()
    if bad:
        r.add("DEPOSIT_ON_NON_RURAL_LOT", f"{bad} depósito(s) fora de lote rural")
    rural_total = Lot.objects.filter(category=Category.RURAL.value).count()
    have = Counter(ResourceDeposit.objects.values_list("resource", flat=True))
    for res in RESOURCES:
        want = resources.target_count(rural_total, sc.resource_rarity.get(res, 0))
        if have.get(res.value, 0) != want:
            r.add("RESOURCE_SHARE_MISMATCH", f"{res.value}: {have.get(res.value, 0)} != {want}")
    return r
