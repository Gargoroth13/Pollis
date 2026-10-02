"""
Propriedades sobre sequências ALEATÓRIAS (semente fixa => reproduzíveis) de atividades e passagem de tempo.

  1. INVARIANTES: exatamente 3 skills; nível nunca negativo e NUNCA diminui (não existe decadência de skill
     no 01); a Especialização nunca cai abaixo de 50% do máximo histórico nem passa dele; o ganho registrado
     no detalhamento é exatamente a variação do nível.
  2. DETERMINISMO: mesma sequência => mesmo resultado (design/21).
  3. EQUIVALÊNCIA LAZY (04 §22): acessos extras nunca mudam o resultado, inclusive a decadência diária.

Cada configuração EXIGE ter atingido os estados interessantes, senão o teste passaria vazio.
"""
import random
from decimal import Decimal

from django.test import TestCase, override_settings

from accounts.models import Usuario
from core.clock import ManualClock, use_clock
from players.actions import Action
from players.hooks import ActivityContext
from players.services import consume_food, create_player, perform_action, sync_player
from players.tests.base import T0
from skills import rules, services
from skills.balance import get_skill_balance
from skills.constants import SKILLS
from skills.models import PlayerSkill, Specialization

N_OPS = 50
ADVANCES = [0, 59, 600, 3600, 5 * 3600, 20 * 3600, 86400, 2 * 86400, 5 * 86400]
KEYS = [None, None, "product:a", "product:b", "activity:c"]
SKILL_SETS = [None, ("physical",), ("intelligence",), ("charisma",), ("intelligence", "charisma"),
              ("intelligence", "physical", "charisma")]


def run_sequence(name, seed, *, extra_sync_seed=None, check=True):
    ops = random.Random(seed)
    extra = random.Random(extra_sync_seed) if extra_sync_seed is not None else None
    clk = ManualClock(T0)
    sbal = get_skill_balance()
    coverage, responses = set(), []
    with use_clock(clk):
        player = create_player(Usuario.objects.create_user(name))
        prev_levels = {s: Decimal(0) for s in SKILLS}
        for _ in range(N_OPS):
            op = ops.choice(["advance", "advance", "study", "work", "work", "work", "leisure", "food"])
            r = None
            before = services.get_levels(player.pk)
            if op == "advance":
                clk.advance(seconds=ops.choice(ADVANCES))
            elif op == "study":
                r = perform_action(player.pk, Action.STUDY, activity=ActivityContext(school_quality=Decimal(ops.choice(["1", "0.5", "0"]))))
            elif op == "work":
                r = perform_action(player.pk, Action.WORK, activity=ActivityContext(
                    skills=ops.choice(SKILL_SETS), specialization_key=ops.choice(KEYS)))
            elif op == "leisure":
                r = perform_action(player.pk, Action.LEISURE, activity=ActivityContext(
                    skills=("charisma",), base_gain={"charisma": Decimal(ops.randint(0, 3))}))
            else:
                r = consume_food(player.pk, ops.randint(20, 100))
            responses.append((op, r.code if r else None))
            if r is not None and not r.ok:
                coverage.add(r.code)
            if r is not None and r.ok and "skills" in r.detail.get("hooks", {}):
                out = r.detail["hooks"]["skills"]
                if out["gains"]:
                    coverage.add("SKILL_GAIN")
                    after = services.get_levels(player.pk)
                    for skill, g in out["gains"].items():
                        assert g["level_after"] - g["level_before"] == g["gain"].value, "ganho do detalhamento != variação"
                    for s in SKILLS:
                        assert after[s] - before[s] == (out["gains"][s.value]["gain"].value if s.value in out["gains"] else 0)
                if out["specialization"]:
                    coverage.add("SPEC_GAIN")
                    if out["specialization"]["gain"].step("recovery_multiplier").amount > 1:
                        coverage.add("SPEC_RECOVERY_BOOST")
            if extra is not None and extra.random() < 0.6:
                sync_player(player.pk)
            if check:
                prev_levels = _assert_invariants(player, clk.now(), sbal, prev_levels)
            for spec in Specialization.objects.filter(player=player):
                if spec.value < spec.historic_max:
                    coverage.add("SPEC_DECAYED")
        final = sync_player(player.pk)
        levels = services.get_levels(player.pk)
        specs = tuple((s.key, s.value, s.historic_max, s.last_used_day)
                      for s in Specialization.objects.filter(player=player).order_by("key"))
    state = (tuple(levels[s] for s in SKILLS), specs, final.energy, final.health, final.burnout, final.processed_until)
    return responses, state, coverage


def _assert_invariants(player, now, sbal, prev_levels):
    sync_player(player.pk)
    assert PlayerSkill.objects.filter(player=player).count() == 3, "devem existir exatamente 3 skills"
    levels = services.get_levels(player.pk)
    for s in SKILLS:
        assert levels[s] >= 0, f"{s} negativa"
        assert levels[s] >= prev_levels[s], f"{s} DIMINUIU: {prev_levels[s]} -> {levels[s]}"
    for spec in Specialization.objects.filter(player=player):
        floor = rules.specialization_floor(spec.historic_max, sbal)
        assert floor <= spec.value <= spec.historic_max, f"{spec.key}: {spec.value} fora de [{floor}, {spec.historic_max}]"
    return levels


class PropertyTests(TestCase):
    SEEDS = range(1, 16)

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

    def test_same_sequence_gives_same_result(self):
        for seed in (2, 7, 11):
            self.assertEqual(run_sequence(f"a{seed}", seed, check=False)[:2], run_sequence(f"b{seed}", seed, check=False)[:2])

    @override_settings(POLIS_BALANCE={"nutrition_decay_per_cycle": 0})
    def test_extra_accesses_never_change_the_outcome(self):
        coverage = self._equivalence("e", self.SEEDS, 1000)
        self.assertTrue({"SKILL_GAIN", "SPEC_GAIN", "SPEC_DECAYED", "SPEC_RECOVERY_BOOST"} <= coverage, coverage)

    @override_settings(POLIS_BALANCE={"nutrition_decay_per_cycle": 0},
                       POLIS_SKILLS_BALANCE={"specialization_decay_per_day": 0.4, "specialization_floor_ratio": 0.8,
                                             "specialization_gain_per_work": 3})
    def test_invariants_and_equivalence_with_aggressive_specialization_parameters(self):
        for seed in range(1, 9):
            run_sequence(f"x{seed}", seed)
        coverage = self._equivalence("x", range(1, 9), 3000)
        self.assertTrue({"SPEC_GAIN", "SPEC_DECAYED", "SPEC_RECOVERY_BOOST"} <= coverage, coverage)

    def test_default_balance_with_realistic_nutrition_also_stays_consistent(self):
        """Com a Nutrição do P0.04 ativa: o jogador adoece e as ações são recusadas; nada disso quebra Skills."""
        coverage = self._equivalence("d", range(1, 9), 5000)
        self.assertIn("SKILL_GAIN", coverage)
