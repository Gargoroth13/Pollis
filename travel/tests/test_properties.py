"""
Propriedades sobre sequências ALEATÓRIAS (semente fixa => reproduzíveis) de viagens, ações e passagem de tempo.

  1. INVARIANTES: todo jogador tem um lote válido; no máximo 1 viagem ativa; a viagem ativa parte de onde o jogador está
     e chega no futuro; viagens concluídas formam uma CADEIA (cada uma parte de onde a anterior chegou).
  2. DETERMINISMO: mesma sequência => mesmo resultado (design/21).
  3. EQUIVALÊNCIA LAZY (04 §22): acessos extras nunca mudam o resultado, nem das viagens nem das ações.

Cada configuração EXIGE ter atingido os estados interessantes (cobertura), senão o teste passaria vazio.
"""
import random

from django.test import TestCase, override_settings

from accounts.models import Usuario
from core.clock import ManualClock, use_clock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.models import Lot
from geography.tests.base import SMALL
from players.actions import Action
from players.hooks import ActivityContext
from players.services import consume_food, create_player, perform_action, sync_player
from players.tests.base import T0
from travel import services
from travel.integrity import check_integrity
from travel.models import Journey, PlayerLocation

N_OPS = 60
ADVANCES = [0, 1, 59, 300, 599, 600, 601, 1800, 3600, 5 * 3600, 20 * 3600, 2 * 86400]


def run_sequence(name, seed, *, extra_sync_seed=None, check=True):
    ops = random.Random(seed)
    extra = random.Random(extra_sync_seed) if extra_sync_seed is not None else None
    lot_ids = list(Lot.objects.order_by("id").values_list("id", flat=True))
    clk = ManualClock(T0)
    responses, coverage = [], set()
    with use_clock(clk):
        player = create_player(Usuario.objects.create_user(name))
        for _ in range(N_OPS):
            op = ops.choice(["advance", "advance", "travel", "travel", "work", "work", "study", "leisure", "food"])
            r = None
            if op == "advance":
                clk.advance(seconds=ops.choice(ADVANCES))
            elif op == "travel":
                r = services.start_travel(player.pk, ops.choice(lot_ids))
            elif op == "food":
                r = consume_food(player.pk, ops.randint(20, 100))
            else:
                # Presença é regra FIXA da ação (GD, 2026-10-07): a atividade não declara nada para work/study/leisure.
                r = perform_action(player.pk, Action(op), activity=ActivityContext())
            if r is not None and op in ("work", "study") and r.code == "TRAVELING":
                coverage.add("PRESENCE_BLOCKED")
            if r is not None and op == "leisure" and r.ok and Journey.objects.filter(player=player, completed=False).exists():
                coverage.add("LEISURE_DURING_TRIP")
            responses.append((op, r.code if r else None))
            if r is not None and not r.ok:
                coverage.add(r.code)
            if op == "travel" and r.ok:
                coverage.add("TRIP_STARTED")
            if extra is not None and extra.random() < 0.6:
                sync_player(player.pk)
            if check:
                _assert_invariants(player, clk.now())
        sync_player(player.pk)
        done = Journey.objects.filter(player=player, completed=True).count()
        if done >= 2:
            coverage.add("TWO_OR_MORE_TRIPS_COMPLETED")
        elif done == 1:
            coverage.add("ONE_TRIP_COMPLETED")
        loc = PlayerLocation.objects.get(player=player).lot_id
        journeys = tuple(Journey.objects.filter(player=player).order_by("id").values_list("origin_id", "destination_id", "departed_at", "arrives_at", "completed"))
        state = (loc, journeys, tuple(sync_player(player.pk).__dict__[k] for k in ("energy", "health", "nutrition", "burnout", "processed_until")))
    return responses, state, coverage


def _assert_invariants(player, now):
    sync_player(player.pk)
    assert Lot.objects.filter(pk=PlayerLocation.objects.get(player=player).lot_id).exists(), "localização inválida"
    active = list(Journey.objects.filter(player=player, completed=False))
    assert len(active) <= 1, "mais de uma viagem ativa"
    if active:
        j = active[0]
        assert j.arrives_at > now, f"viagem vencida e não concluída ({j.arrives_at} <= {now})"
        assert j.departed_at <= now
        assert j.origin_id == PlayerLocation.objects.get(player=player).lot_id, "viagem ativa não parte do lote atual"
    done = list(Journey.objects.filter(player=player, completed=True).order_by("arrives_at", "id"))
    for a, b in zip(done, done[1:]):
        assert a.destination_id == b.origin_id, "cadeia de viagens quebrada"
        assert a.arrives_at <= b.departed_at, "viagens sobrepostas"
    report = check_integrity()
    assert report.ok, report.violations


class PropertyTests(TestCase):
    SEEDS = range(1, 21)

    @classmethod
    def setUpTestData(cls):
        generate_world(get_scenario(**SMALL))

    def _equivalence(self, prefix, seeds, noise):
        coverage = set()
        for seed in seeds:
            plain = run_sequence(f"{prefix}p{seed}", seed, check=False)
            noisy = run_sequence(f"{prefix}n{seed}", seed, extra_sync_seed=noise + seed, check=False)
            self.assertEqual(plain[:2], noisy[:2], f"seed={seed}")
            coverage |= plain[2]
        return coverage

    def test_invariants_hold_on_random_sequences(self):
        for seed in self.SEEDS:
            run_sequence(f"inv{seed}", seed)

    def test_same_sequence_gives_the_same_result(self):
        for seed in (2, 8, 14):
            self.assertEqual(run_sequence(f"a{seed}", seed, check=False)[:2], run_sequence(f"b{seed}", seed, check=False)[:2])

    @override_settings(POLIS_GEOGRAPHY={"travel_minutes_per_unit": 2})
    def test_extra_accesses_never_change_the_outcome_with_short_trips(self):
        """Viagens curtas: muitas chegadas, inclusive entre dois ciclos."""
        coverage = self._equivalence("s", self.SEEDS, 1000)
        self.assertTrue({"TRIP_STARTED", "TWO_OR_MORE_TRIPS_COMPLETED", "TRAVELING", "ALREADY_TRAVELING"} <= coverage, coverage)

    def test_extra_accesses_never_change_the_outcome_with_the_default_scale(self):
        coverage = self._equivalence("d", self.SEEDS, 2000)
        self.assertTrue({"TRIP_STARTED", "TRAVELING"} <= coverage, coverage)

    def test_presence_rule_and_invariants(self):
        """Trabalho/Estudo bloqueiam em viagem; Lazer nunca. Em ambos os casos nada fica inconsistente."""
        for seed in range(1, 9):
            run_sequence(f"p{seed}", seed)
        coverage = self._equivalence("q", range(1, 9), 3000)
        self.assertTrue({"TRAVELING", "PRESENCE_BLOCKED", "LEISURE_DURING_TRIP"} <= coverage, coverage)

    @override_settings(POLIS_GEOGRAPHY={"travel_minutes_per_unit": 1})
    def test_no_state_blocks_departure_and_invariants_hold(self):
        """Nenhum estado impede a partida (GD, 2026-10-07): mesmo com viagens frequentes, burnout/hospitalização/saúde crítica."""
        for seed in range(1, 11):
            run_sequence(f"b{seed}", seed)
        coverage = self._equivalence("c", range(1, 11), 4000)
        self.assertTrue({"TRIP_STARTED"} <= coverage, coverage)

    def test_recorded_cost_always_matches_distance_times_cost_per_unit(self):
        """Custo monetário (GD, 2026-10-07): toda viagem registra distância × custo_por_unidade, em centavos, fixado na partida."""
        from decimal import Decimal
        from geography import services as geo
        from travel import rules
        run_sequence("cost", 3, check=False)
        per_unit = get_scenario().travel_cost_per_unit
        journeys = list(Journey.objects.select_related("origin", "destination").all())
        self.assertGreater(len(journeys), 0)
        for j in journeys:
            expected = rules.charge_amount(geo.distance_between(j.origin, j.destination) * per_unit)
            self.assertEqual(j.cost, expected)
            self.assertGreaterEqual(j.cost, Decimal(0))
