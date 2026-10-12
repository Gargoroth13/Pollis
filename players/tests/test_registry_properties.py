"""
Propriedades do Action Registry sobre sequências ALEATÓRIAS (semente fixa => reproduzíveis).

  1. EQUIVALÊNCIA: executar pelo registro == chamar o serviço direto (mesmos códigos, detalhes e estado final).
  2. PREVISÃO: a consulta (`check_action`) concorda com o que a execução, no mesmo instante, de fato devolve, para todo estado
     alcançado; o código de recusa real está sempre declarado nos requisitos (ou vem de um provedor externo).
  3. LAZY: consultar disponibilidade quantas vezes for não altera o resultado de nada (04 §22).
  4. DETERMINISMO: mesma semente => mesmo resultado.

Cada teste EXIGE ter atingido os estados interessantes (cobertura), senão passaria vazio.
"""
import random
from decimal import Decimal

from django.test import TestCase

from accounts.models import Usuario
from core.clock import ManualClock, use_clock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.models import Lot
from geography.tests.base import SMALL
from players import registry
from players.actions import Action
from players.models import Player
from players.services import change_health, consume_food, create_player, perform_action, sync_player
from players.tests.base import T0
from travel import services as travel
from travel.models import Journey, PlayerLocation

N_OPS = 70
ADVANCES = [0, 1, 299, 600, 601, 1800, 3600, 4 * 3600, 20 * 3600, 2 * 86400]
ACTIONS = ("work", "study", "leisure", "travel")
PROVIDER_CODES = {"TRAVELING"}


def _strip(detail):
    return {k: v for k, v in detail.items() if k != "journey_id"}


def run_sequence(name, seed, *, mode, noise_seed=None):
    """mode: 'registry' (pelo registro, conferindo a previsão) | 'direct' (serviços diretos)."""
    ops = random.Random(seed)
    noise = random.Random(noise_seed) if noise_seed is not None else None
    lot_ids = list(Lot.objects.order_by("id").values_list("id", flat=True))
    clk = ManualClock(T0)
    log, coverage = [], set()
    with use_clock(clk):
        player = create_player(Usuario.objects.create_user(name))
        for _ in range(N_OPS):
            op = ops.choice(["advance", "advance", "advance", "work", "work", "study", "leisure", "travel", "travel",
                             "food", "hurt", "burn", "drain"])
            if noise is not None and noise.random() < 0.5:
                registry.available_actions(player.pk)           # consultas extras nunca podem mudar nada
            if op == "advance":
                clk.advance(seconds=ops.choice(ADVANCES))
                log.append((op, None))
                continue
            if op == "food":
                consume_food(player.pk, ops.randint(20, 100))
                log.append((op, None))
                continue
            if op == "hurt":
                change_health(player.pk, -Decimal(ops.choice([30, 60, 100])), "prop")
                log.append((op, None))
                continue
            if op in ("burn", "drain"):
                sync_player(player.pk)      # estado direto SÓ depois de processar o lazy, senão o próprio teste quebra a equivalência
                fields = (dict(burnout=Decimal(100), burnout_active=True) if op == "burn"
                          else dict(energy=Decimal(ops.choice([0, 5, 15]))))
                Player.objects.filter(pk=player.pk).update(**fields)
                log.append((op, None))
                continue
            target = None
            if op == "travel":
                target = ops.choice(lot_ids + [PlayerLocation.objects.get(player=player).lot_id, 10 ** 9])
            if mode == "registry":
                predicted = registry.check_action(player.pk, op, target)
                r = registry.execute_action(player.pk, op, target)
                _assert_prediction(predicted, r, op)
                coverage.add(("predicted", predicted.available))
            elif op == "travel":
                r = travel.start_travel(player.pk, target)
            else:
                r = perform_action(player.pk, Action(op))
            log.append((op, r.ok, r.code, _strip(r.detail)))
            coverage.add(r.code)
            if op in ("work", "study") and r.code == "TRAVELING":
                coverage.add("PRESENCE_BLOCKED")
            if not r.ok and mode == "registry" and op != "travel":
                for code in {r.code, *r.detail.get("reasons", ())} - PROVIDER_CODES:
                    assert code in registry.get_descriptor(op).requirements, f"{op}: {code} não declarado"
        s = sync_player(player.pk)
        final = (tuple(getattr(s, k) for k in ("energy", "health", "nutrition", "burnout", "processed_until", "last_work_at")),
                 PlayerLocation.objects.get(player=player).lot_id,
                 tuple(Journey.objects.filter(player=player).order_by("id")
                       .values_list("origin_id", "destination_id", "departed_at", "arrives_at", "completed", "cost")))
    return log, final, coverage


def _assert_prediction(predicted, result, op):
    """Consulta e execução no mesmo instante: concordam. Exceção: Viajar sem pagamento nunca recusa por fundos."""
    if predicted.code in ("TARGET_NOT_ALLOWED", "INVALID_PARAMS"):
        assert not result.ok and result.code == predicted.code, (op, predicted.code, result.code)
        return
    assert predicted.available == result.ok, f"{op}: previsto {predicted.code}, executado {result.code}"
    assert predicted.code == result.code, f"{op}: previsto {predicted.code}, executado {result.code}"
    if not result.ok and "reasons" in result.detail:
        assert list(predicted.blocked_by) == result.detail["reasons"], op


class RegistryPropertyTests(TestCase):
    SEEDS = range(1, 13)

    @classmethod
    def setUpTestData(cls):
        generate_world(get_scenario(**SMALL))

    def test_registry_and_direct_services_are_equivalent_and_predictions_hold(self):
        coverage = set()
        for seed in self.SEEDS:
            via = run_sequence(f"rv{seed}", seed, mode="registry")
            direct = run_sequence(f"dr{seed}", seed, mode="direct")
            self.assertEqual(via[0], direct[0], f"seed={seed}: resultados")
            self.assertEqual(via[1], direct[1], f"seed={seed}: estado final")
            coverage |= via[2]
        needed = {"OK", "INSUFFICIENT_ENERGY", "BURNOUT_ACTIVE", "HEALTH_CRITICAL", "HOSPITALIZED", "TRAVELING",
                  "PRESENCE_BLOCKED", "ALREADY_TRAVELING", "SAME_LOCATION", "INVALID_DESTINATION",
                  ("predicted", True), ("predicted", False)}
        self.assertLessEqual(needed, coverage, needed - coverage)

    def test_extra_availability_queries_never_change_the_outcome(self):
        for seed in self.SEEDS:
            plain = run_sequence(f"qp{seed}", seed, mode="registry")
            noisy = run_sequence(f"qn{seed}", seed, mode="registry", noise_seed=900 + seed)
            self.assertEqual(plain[:2], noisy[:2], f"seed={seed}")

    def test_same_sequence_gives_the_same_result(self):
        for seed in (3, 7, 11):
            self.assertEqual(run_sequence(f"a{seed}", seed, mode="registry")[:2], run_sequence(f"b{seed}", seed, mode="registry")[:2])
