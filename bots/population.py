"""
Population Controller (21 §21.2): cria Bots a uma taxa configurável (padrão 1 por minuto REAL) até a população-alvo e escolhe PERFIS que cobrem as lacunas
de cobertura, em vez de manter uma proporção fixa. Cada Bot é uma conta real e normal (`create_player`): nada de NPC, de dinheiro criado ou de caminho
privilegiado. A dotação monetária inicial pertence ao cenário/ledger (24, P0.07), não a este módulo.
"""
from __future__ import annotations

import time
from collections import Counter
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from accounts.models import Usuario
from core import clock as game_clock
from core.models import WorldClock
from players.services import create_player

from . import params, scheduler
from .constants import ARCHETYPE_DEFAULTS, Archetype, BotStatus, Goal, Personality, RunStatus, Specialization
from .models import Bot, BotRun, PopulationSnapshot
from .runner import game_version
from .seeds import derive_seed, rng_for


def start_run(name: str, *, target_population: int = params.DEFAULT_TARGET_POPULATION,
              creation_interval_real_seconds: int = params.DEFAULT_CREATION_INTERVAL_REAL_SECONDS, global_seed: int = 0,
              max_creation_burst: int = params.DEFAULT_MAX_CREATION_BURST, model_version: str = params.BASELINE_MODEL_VERSION,
              coverage_specializations: Optional[List[str]] = None, config: Optional[Dict[str, Any]] = None) -> BotRun:
    if target_population < 0 or creation_interval_real_seconds < 1 or max_creation_burst < 1:
        raise ValueError("população-alvo ≥ 0, intervalo ≥ 1 s e rajada ≥ 1")
    specs = coverage_specializations or [s.value for s in Specialization if s is not Specialization.NONE]
    unknown = [s for s in specs if s not in {x.value for x in Specialization}]
    if unknown:
        raise ValueError(f"especializações desconhecidas: {unknown}")
    wc = WorldClock.load()
    return BotRun.objects.create(
        name=name, started_game_at=game_clock.now(), started_real_at=timezone.now(), game_version=game_version(), model_version=model_version,
        global_seed=global_seed, target_population=target_population, creation_interval_real_seconds=creation_interval_real_seconds,
        max_creation_burst=max_creation_burst, clock_real_seconds_per_game_day=wc.real_seconds_per_game_day,
        config={**(config or {}), "coverage_specializations": specs})


def active_count(run: BotRun) -> int:
    return Bot.objects.filter(run=run, status=BotStatus.ACTIVE.value).count()


def coverage(run: BotRun) -> Dict[str, Dict[str, int]]:
    """Contagem de Bots ATIVOS por dimensão (inclui zeros das especializações acompanhadas): é a base das lacunas de cobertura (21 §21.2)."""
    rows = Bot.objects.filter(run=run, status=BotStatus.ACTIVE.value).values_list("archetype", "personality", "goal", "specialization")
    out: Dict[str, Counter] = {k: Counter() for k in ("archetype", "personality", "goal", "specialization")}
    for arch, pers, goal, spec in rows:
        out["archetype"][arch] += 1
        out["personality"][pers] += 1
        out["goal"][goal] += 1
        out["specialization"][spec] += 1
    for spec in run.config.get("coverage_specializations", []):
        out["specialization"].setdefault(spec, 0)
    for a in Archetype:
        if a is not Archetype.CUSTOM:
            out["archetype"].setdefault(a.value, 0)
    return {k: dict(sorted(v.items())) for k, v in out.items()}


def gaps(run: BotRun) -> List[Dict[str, Any]]:
    """Dimensões com cobertura abaixo da média da sua dimensão, da mais carente para a menos (sem proporção fixa: o objetivo é cobrir lacunas)."""
    out = []
    for dim, counts in coverage(run).items():
        if not counts:
            continue
        mean = sum(counts.values()) / len(counts)
        for value, n in counts.items():
            if n < mean:
                out.append({"dimension": dim, "value": value, "count": n, "mean": round(mean, 2)})
    return sorted(out, key=lambda g: (g["count"] - g["mean"], g["dimension"], g["value"]))


def choose_profile(run: BotRun, index: int) -> Dict[str, str]:
    """Perfil do próximo Bot: o arquétipo e a especialização MENOS cobertos (desempate reproduzível pela seed), combinados livremente (21 §21.5)."""
    cov = coverage(run)
    rng = rng_for(derive_seed(run.global_seed, "profile", index))

    def least(counts: Dict[str, int]) -> str:
        low = min(counts.values())
        return rng.choice(sorted(k for k, v in counts.items() if v == low))

    archetype = Archetype(least(cov["archetype"]))
    personality, goal = ARCHETYPE_DEFAULTS[archetype]
    spec = Specialization(least(cov["specialization"])) if cov["specialization"] else Specialization.NONE
    return {"archetype": archetype.value, "personality": personality.value, "goal": goal.value, "specialization": spec.value}


def create_bot(run: BotRun, profile: Optional[Dict[str, str]] = None) -> Bot:
    """Cria a conta (usuário sem senha utilizável + jogador normal) e o Bot. O perfil pode combinar personalidade, objetivo e especialização livremente."""
    with transaction.atomic():
        run = BotRun.objects.select_for_update().get(pk=run.pk)
        index = run.bots_created + 1
        profile = profile or choose_profile(run, index)
        archetype = Archetype(profile.get("archetype", Archetype.CUSTOM.value))
        default_p, default_g = ARCHETYPE_DEFAULTS.get(archetype, (Personality.CASUAL, Goal.WEALTH))
        personality = Personality(profile.get("personality", default_p.value))
        goal = Goal(profile.get("goal", default_g.value))
        specialization = Specialization(profile.get("specialization", Specialization.NONE.value))
        user = Usuario(username=f"bot-{run.pk}-{index}", is_active=True)
        user.set_unusable_password()
        user.save()
        now = game_clock.now()
        player = create_player(user, now=now)
        seed = derive_seed(run.global_seed, "bot", index)
        bot = Bot.objects.create(run=run, player=player, index=index, seed=seed, archetype=archetype.value, personality=personality.value, goal=goal.value,
                                 specialization=specialization.value, created_game_at=now,
                                 next_eval_at=scheduler.first_eval_at(rng_for(derive_seed(seed, "first")), now))
        run.bots_created = index
        run.save(update_fields=["bots_created"])
        return bot


def due_creations(run: BotRun, now_real: float) -> int:
    """Quantos Bots criar agora: 1 por intervalo REAL decorrido, limitado à rajada máxima e ao que falta para a meta. Avança o relógio de criação."""
    with transaction.atomic():
        run = BotRun.objects.select_for_update().get(pk=run.pk)
        if run.status != RunStatus.RUNNING.value:
            return 0
        if run.last_creation_real_at is None:
            run.last_creation_real_at = now_real - run.creation_interval_real_seconds         # o primeiro Bot nasce na primeira passada
        slots = int((now_real - run.last_creation_real_at) // run.creation_interval_real_seconds)
        missing = max(0, run.target_population - active_count(run))
        n = max(0, min(slots, run.max_creation_burst, missing))
        if n:
            run.last_creation_real_at += n * run.creation_interval_real_seconds
        elif missing == 0:
            run.last_creation_real_at = now_real            # meta atingida: não acumula criações atrasadas
        run.save(update_fields=["last_creation_real_at"])
        return n


def step(run: BotRun, now_real: Optional[float] = None) -> List[Bot]:
    """Uma passada do controlador: cria os Bots devidos (perfil por cobertura). Devolve os criados."""
    now_real = time.time() if now_real is None else now_real
    return [create_bot(run) for _ in range(due_creations(run, now_real))]


def snapshot_population(run: BotRun) -> PopulationSnapshot:
    """Foto diária (population_daily.csv, 21 §21.53). Uma por dia de jogo; repetir no mesmo dia atualiza a foto."""
    from ledger.money import competence_day_of
    now = game_clock.now()
    day = competence_day_of(now)
    status = dict(Counter(Bot.objects.filter(run=run).values_list("status", flat=True)))
    data = {"status": status, **coverage(run)}
    snap, _ = PopulationSnapshot.objects.update_or_create(run=run, game_day=day, defaults={"taken_at": now, "total_active": status.get(BotStatus.ACTIVE.value, 0), "data": data})
    return snap
