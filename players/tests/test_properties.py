"""
Testes de propriedade: sequências ALEATÓRIAS (semente fixa => reproduzíveis) de ações e passagem de
tempo. Em vez de confiar só nos exemplos que escolhi, verificam:

  1. INVARIANTES: nenhum valor sai da faixa; histereses e hospitalização coerentes com o estado.
  2. DETERMINISMO: mesma sequência => mesmo estado e mesmas respostas (design/21).
  3. EQUIVALÊNCIA LAZY (04 §22): acessar o jogo a mais, em momentos arbitrários, NUNCA muda o
     resultado final nem o resultado de nenhuma ação.

Cada configuração EXIGE ter de fato atingido os estados interessantes (cobertura), senão o teste
passaria vazio.
"""
import random
from decimal import Decimal

from django.test import TestCase, override_settings

from accounts.models import Usuario
from core.clock import ManualClock, use_clock
from players.balance import get_balance
from players.models import Player
from players.rules import Action
from players.services import (EffectSpec, apply_temporary_effect, change_health, consume_food, create_player,
                              get_snapshot, perform_action, sync_player)

from .base import T0

N_OPS = 60
ADVANCES = [0, 1, 59, 599, 600, 601, 1800, 3599, 3600, 3601, 2 * 3600, 5 * 3600, 25 * 3600]


def run_sequence(name, seed, *, extra_sync_seed=None, check_invariants=True):
    """
    Executa a sequência de operações derivada só de `seed` e devolve (respostas, estado final, cobertura).
    Acessos EXTRAS (só sincronizam) vêm de outro gerador, então não alteram a sequência de operações.
    """
    ops = random.Random(seed)
    extra = random.Random(extra_sync_seed) if extra_sync_seed is not None else None
    clk = ManualClock(T0)
    bal = get_balance()
    responses, coverage = [], set()
    with use_clock(clk):
        player = create_player(Usuario.objects.create_user(name))
        for _ in range(N_OPS):
            op = ops.choice(["advance", "advance", "work", "work", "study", "leisure", "food", "food",
                             "damage", "heal", "effect"])
            r = None
            if op == "advance":
                clk.advance(seconds=ops.choice(ADVANCES))
            elif op in ("work", "study", "leisure"):
                effect = EffectSpec("leisure:x", Decimal(ops.randint(1, 20)) / 100, ops.randint(1, 6) * 3600) \
                    if op == "leisure" and ops.random() < 0.5 else None
                r = perform_action(player.pk, Action(op), burnout_risk=ops.choice([1, 1, "0.5", 0]), effect=effect)
            elif op == "food":
                effect = EffectSpec("food:x", Decimal(ops.randint(-5, 20)) / 100, ops.randint(1, 6) * 3600) \
                    if ops.random() < 0.5 else None
                r = consume_food(player.pk, ops.randint(0, 60), effect=effect)
            elif op == "damage":
                r = change_health(player.pk, -ops.randint(0, 80), "test")
            elif op == "heal":
                r = change_health(player.pk, ops.randint(0, 80), "test")
            else:
                r = apply_temporary_effect(player.pk, ops.choice(["food", "leisure", "services"]), "t",
                                           Decimal(ops.randint(-30, 30)) / 100, ops.randint(1, 20) * 3600)
            responses.append((op, r.code if r else None))
            if r is not None and not r.ok:
                coverage.add(r.code)
            stored = Player.objects.get(pk=player.pk)  # leitura barata, sem sync (só mede cobertura)
            for flag, label in ((stored.burnout_active, "BURNOUT_ACTIVE_STATE"), (stored.health_critical, "CRITICAL_STATE"),
                                (stored.is_hospitalized(clk.now()), "HOSPITALIZED_STATE")):
                if flag:
                    coverage.add(label)
            if extra is not None and extra.random() < 0.6:
                sync_player(player.pk)
            if check_invariants:
                _assert_invariants(clk.now(), player.pk, bal)
        final = sync_player(player.pk)
        snap = get_snapshot(player.pk)
    state = (final.energy, final.health, final.nutrition, final.burnout, final.burnout_active,
             final.health_critical, final.hospitalized_until, final.last_work_at, final.processed_until,
             snap.qol_base_effective.value, snap.qol_current.value)
    return responses, state, coverage


def _assert_invariants(now, pk, bal):
    p = sync_player(pk)
    assert 0 <= p.energy <= bal.energy_max, f"energia fora da faixa: {p.energy}"
    assert 0 <= p.health <= bal.health_max, f"saúde fora da faixa: {p.health}"
    assert 0 <= p.nutrition <= bal.nutrition_max, f"nutrição fora da faixa: {p.nutrition}"
    assert 0 <= p.burnout <= bal.burnout_max, f"burnout fora da faixa: {p.burnout}"
    if p.health <= bal.health_critical_enter:
        assert p.health_critical, f"saúde {p.health} <= {bal.health_critical_enter} mas não está crítica"
    if p.health > bal.health_critical_exit:
        assert not p.health_critical, f"saúde {p.health} > {bal.health_critical_exit} mas continua crítica"
    if p.burnout >= bal.burnout_active_enter:
        assert p.burnout_active, f"burnout {p.burnout} >= {bal.burnout_active_enter} mas não está ativo"
    if p.burnout <= bal.burnout_active_exit:
        assert not p.burnout_active, f"burnout {p.burnout} <= {bal.burnout_active_exit} mas continua ativo"
    if p.health == 0:
        assert p.hospitalized_until is not None, "saúde 0 sem hospitalização"
    assert p.processed_until == now, "ciclos pendentes após sync"
    s = get_snapshot(pk)
    assert s.energy_regen_per_cycle.value >= 0, "regeneração negativa"
    qols = (s.qol_base.value, s.qol_base_effective.value, s.qol_current.value)
    assert all(v.is_finite() for v in qols)


class PropertyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from geography.balance import get_scenario
        from geography.generator import generate_world
        from geography.tests.base import SMALL
        generate_world(get_scenario(**SMALL))  # todo jogador precisa de localização válida (04 §24)

    SEEDS = range(1, 21)

    def _equivalence(self, prefix, seeds, noise_base):
        coverage = set()
        for seed in seeds:
            plain = run_sequence(f"{prefix}p{seed}", seed, check_invariants=False)
            noisy = run_sequence(f"{prefix}n{seed}", seed, extra_sync_seed=noise_base + seed, check_invariants=False)
            self.assertEqual(plain[:2], noisy[:2], f"seed={seed}")
            coverage |= plain[2]
        return coverage

    def test_invariants_hold_on_random_sequences(self):
        for seed in self.SEEDS:
            run_sequence(f"inv{seed}", seed)

    def test_same_sequence_gives_same_result(self):
        for seed in (3, 11, 19):
            self.assertEqual(run_sequence(f"a{seed}", seed, check_invariants=False)[:2],
                             run_sequence(f"b{seed}", seed, check_invariants=False)[:2], f"seed={seed}")

    def test_extra_accesses_never_change_the_outcome_default_balance(self):
        """O ponto central do 04 §22: ler/acessar de graça não pode alterar o jogo."""
        coverage = self._equivalence("d", self.SEEDS, 1000)
        self.assertTrue({"INSUFFICIENT_ENERGY", "CRITICAL_STATE"} <= coverage, coverage)

    @override_settings(POLIS_BALANCE={"burnout_gain_work": 25, "burnout_gain_study": 20, "health_burnout_penalty": 2})
    def test_equivalence_when_burnout_active_is_actually_reached(self):
        coverage = self._equivalence("b", self.SEEDS, 2000)
        self.assertTrue({"BURNOUT_ACTIVE_STATE", "BURNOUT_ACTIVE"} <= coverage, coverage)

    @override_settings(POLIS_BALANCE={"nutrition_decay_per_cycle": 4, "health_nutrition_penalty_max": 14,
                                      "hospitalization_duration_seconds": 5400})
    def test_equivalence_through_critical_health_and_hospitalization(self):
        coverage = self._equivalence("h", self.SEEDS, 3000)
        self.assertTrue({"CRITICAL_STATE", "HOSPITALIZED_STATE", "HOSPITALIZED"} <= coverage, coverage)

    @override_settings(POLIS_BALANCE={"burnout_gain_work": 50, "burnout_gain_study": 40, "nutrition_decay_per_cycle": 4,
                                      "health_nutrition_penalty_max": 14, "health_critical_enter": 40,
                                      "health_critical_exit": 45, "burnout_active_exit": 70})
    def test_invariants_and_equivalence_under_extreme_balance(self):
        """Histereses estreitas e ganhos enormes: os três estados com histerese se cruzam."""
        for seed in range(1, 11):
            run_sequence(f"x{seed}", seed)
        coverage = self._equivalence("x", range(1, 11), 4000)
        # Os três estados com histerese E as recusas que cada um produz (INSUFFICIENT_ENERGY é exigido
        # no teste de balanceamento padrão; aqui a hospitalização recusa antes de a energia faltar).
        self.assertTrue({"BURNOUT_ACTIVE_STATE", "CRITICAL_STATE", "HOSPITALIZED_STATE",
                         "BURNOUT_ACTIVE", "HEALTH_CRITICAL", "HOSPITALIZED"} <= coverage, coverage)
