from django.db import models
from django.db.models import Q

from .constants import Archetype, BotStatus, Goal, Personality, RunStatus, Specialization, WakeReason


def _choices(enum_cls):
    return [(m.value, m.value) for m in enum_cls]


class BotRun(models.Model):
    """Uma execução do Bot Test (21 §21.54): identificador, versões, configuração, população-alvo, velocidade, seed global e contadores."""

    name = models.CharField(max_length=80)
    status = models.CharField(max_length=10, choices=_choices(RunStatus), default=RunStatus.RUNNING.value)
    started_game_at = models.BigIntegerField()
    started_real_at = models.DateTimeField()
    ended_game_at = models.BigIntegerField(null=True, blank=True)
    ended_real_at = models.DateTimeField(null=True, blank=True)
    game_version = models.CharField(max_length=60)
    model_version = models.CharField(max_length=60)
    global_seed = models.BigIntegerField()
    target_population = models.PositiveIntegerField()
    creation_interval_real_seconds = models.PositiveIntegerField()
    max_creation_burst = models.PositiveIntegerField()
    clock_real_seconds_per_game_day = models.PositiveIntegerField(null=True, blank=True)       # velocidade do relógio ao iniciar (21 §21.3)
    last_creation_real_at = models.FloatField(null=True, blank=True)                           # segundos reais (Unix) da última criação planejada
    config = models.JSONField(default=dict)
    bots_created = models.PositiveIntegerField(default=0)
    bots_removed = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(condition=Q(creation_interval_real_seconds__gt=0), name="botrun_interval_positive")]


class Bot(models.Model):
    """
    Entidade Bot (21 §21.5, §21.60). A CONTA é um jogador normal (`Player`); o Bot só acrescenta a identidade administrativa e o agendamento.
    Personalidade, objetivo e especialização são dimensões independentes; `archetype` apenas registra de qual combinação inicial veio.
    """

    run = models.ForeignKey(BotRun, on_delete=models.PROTECT, related_name="bots")
    player = models.OneToOneField("players.Player", on_delete=models.PROTECT, related_name="bot")
    index = models.PositiveIntegerField()                              # ordem de criação dentro da execução
    seed = models.BigIntegerField()
    archetype = models.CharField(max_length=16, choices=_choices(Archetype))
    personality = models.CharField(max_length=14, choices=_choices(Personality))
    goal = models.CharField(max_length=14, choices=_choices(Goal))
    specialization = models.CharField(max_length=14, choices=_choices(Specialization), default=Specialization.NONE.value)
    status = models.CharField(max_length=8, choices=_choices(BotStatus), default=BotStatus.ACTIVE.value)
    created_game_at = models.BigIntegerField()
    next_eval_at = models.BigIntegerField()
    wake_reason = models.CharField(max_length=20, choices=_choices(WakeReason), default=WakeReason.CREATED.value)
    last_eval_at = models.BigIntegerField(null=True, blank=True)
    eval_count = models.PositiveIntegerField(default=0)
    last_observation = models.JSONField(null=True, blank=True)         # última observação do Bot (a mesma que a política recebeu)
    retired_game_at = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["status", "next_eval_at", "id"])]
        constraints = [models.UniqueConstraint(fields=["run", "index"], name="bot_unique_index_per_run")]


class BotDecisionLog(models.Model):
    """Log de decisões (21 §21.56): estado observado, ações disponíveis, ação escolhida, score, exploração, modelo, objetivo, reward posterior, resultado."""

    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="decisions")
    at = models.BigIntegerField()
    eval_no = models.PositiveIntegerField()
    decision_seed = models.BigIntegerField()
    game_version = models.CharField(max_length=60)
    model_version = models.CharField(max_length=60)
    goal = models.CharField(max_length=14)
    observation = models.JSONField()
    available_actions = models.JSONField()          # máscara: {ação: 0|1} (21 §21.21)
    chosen_action = models.CharField(max_length=40, null=True, blank=True)       # None = nenhuma ação (nada disponível ou a política se absteve)
    chosen_target = models.JSONField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    exploration = models.JSONField(default=dict)
    result_code = models.CharField(max_length=60, blank=True, default="")
    reward = models.FloatField(null=True, blank=True)       # preenchido pelo módulo de reward (P1.19); nunca antes da ação (21 §21.17)
    next_observation = models.JSONField(null=True, blank=True)       # preenchido na avaliação seguinte (armazenamento de experiência, 21 §21.26)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["bot", "eval_no"])]
        constraints = [models.UniqueConstraint(fields=["bot", "eval_no"], name="botdecision_unique_eval")]


class BotActionLog(models.Model):
    """Log de ações (21 §21.55): o suficiente para reconstruir a consequência da ação."""

    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name="actions")
    decision = models.OneToOneField(BotDecisionLog, on_delete=models.CASCADE, related_name="action")
    at = models.BigIntegerField()
    action = models.CharField(max_length=40)
    target = models.JSONField(null=True, blank=True)
    success = models.BooleanField()
    code = models.CharField(max_length=60)
    detail = models.JSONField(default=dict)
    energy_before = models.CharField(max_length=20, blank=True, default="")
    energy_after = models.CharField(max_length=20, blank=True, default="")
    money_before = models.BigIntegerField(null=True, blank=True)
    money_after = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["bot", "id"]), models.Index(fields=["action", "success"])]


class BotTickMetric(models.Model):
    """Desempenho do ambiente (21 §21.52, CLAUDE.md §9): tempo de cada passada, decisões e fila de Bots atrasados."""

    run = models.ForeignKey(BotRun, on_delete=models.CASCADE, related_name="metrics")
    game_at = models.BigIntegerField()
    real_seconds = models.FloatField()
    created = models.PositiveIntegerField(default=0)
    evaluated = models.PositiveIntegerField(default=0)
    acted = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    backlog_after = models.PositiveIntegerField(default=0)       # Bots ainda vencidos depois da passada (fila do scheduler)
    db_queries = models.PositiveIntegerField(default=0)
    db_seconds = models.FloatField(default=0)               # tempo gasto em consultas (CLAUDE.md §9: tempo de banco)
    cpu_seconds = models.FloatField(default=0)              # CPU do processo na passada (tempo de simulação)
    rss_mb = models.FloatField(default=0)                   # pico de memória do processo (RAM); GPU/VRAM entram com o modelo (P1.19)

    class Meta:
        ordering = ["id"]


class PopulationSnapshot(models.Model):
    """Foto da população por dia de jogo (population_daily.csv de 21 §21.53)."""

    run = models.ForeignKey(BotRun, on_delete=models.CASCADE, related_name="snapshots")
    game_day = models.IntegerField()
    taken_at = models.BigIntegerField()
    total_active = models.PositiveIntegerField()
    data = models.JSONField()        # contagens por status, arquétipo, personalidade, objetivo e especialização

    class Meta:
        ordering = ["run_id", "game_day"]
        constraints = [models.UniqueConstraint(fields=["run", "game_day"], name="populationsnapshot_one_per_day")]
