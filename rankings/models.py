from django.db import models
from django.db.models import F, Q

from .constants import ENTITY_TYPES, HISTORICAL


class RankingHistorico(models.Model):
    """
    Recorde atual de UMA categoria histórica (design/14 §14.5): estrutura genérica, sem uma tabela por ranking.
    O recorde anterior é substituído (não há histórico de estados); `metadata` guarda o necessário à auditoria da categoria.
    Substituição só por valor ESTRITAMENTE maior: em empate fica quem chegou primeiro.
    Instantes em tempo de jogo (segundos).
    """

    category = models.CharField(max_length=32, unique=True, choices=[(c.key.value, c.label) for c in HISTORICAL])
    entity_type = models.CharField(max_length=16, choices=[(t, t) for t in ENTITY_TYPES])
    entity_id = models.BigIntegerField()
    value = models.BigIntegerField()                  # unidade da categoria (centavos, segundos, partes por milhão)
    recorded_at = models.BigIntegerField()            # quando o recorde foi ESTABELECIDO (14.4)
    updated_at = models.BigIntegerField()             # quando o registro foi gravado pela última vez (14.9)
    metadata = models.JSONField(default=dict)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(value__gte=0), name="rankinghistorico_value_gte_0"),
            models.CheckConstraint(condition=Q(updated_at__gte=F("recorded_at")), name="rankinghistorico_updated_after_recorded"),
        ]

    def __str__(self):
        return f"RankingHistorico({self.category}: {self.entity_type}#{self.entity_id}={self.value})"


class ActivityEvent(models.Model):
    """
    Outbox durável da atividade (design/14a §3.6). UMA linha por execução BEM-SUCEDIDA do Action Registry (jogadores e bots
    iguais), gravada na MESMA transação da ação: ou ação e evento são confirmados juntos, ou nenhum dos dois.
    `ActivityStreak` é atualizada a partir destes eventos por `rankings.outbox` (em ordem `(at, id)` por jogador, idempotente).
    `id` é o identificador único e o desempate estável da ordem. Não é um barramento de eventos: só carrega atividade.
    """

    player = models.ForeignKey("players.Player", on_delete=models.CASCADE, related_name="activity_events")
    action_id = models.CharField(max_length=64)
    at = models.BigIntegerField()                               # instante (tempo de jogo) em que a ação foi confirmada
    processed_at = models.BigIntegerField(null=True, blank=True)   # NULL = pendente
    attempts = models.PositiveIntegerField(default=0)           # tentativas de processamento que FALHARAM
    last_error = models.CharField(max_length=500, blank=True, default="")
    last_attempt_at = models.BigIntegerField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["player", "at", "id"], name="activityevent_pending_idx", condition=Q(processed_at__isnull=True)),
            models.Index(fields=["at", "id"], name="activityevent_oldest_idx", condition=Q(processed_at__isnull=True)),
        ]

    def __str__(self):
        return f"evento #{self.pk} jogador {self.player_id} {self.action_id}@{self.at}"


class ActivityStreak(models.Model):
    """
    Sequência de atividade de uma conta (design/14 §14.3.11). Uma linha por jogador.
    A atividade é uma AÇÃO VÁLIDA (execução bem-sucedida pelo Action Registry), não login nem navegação.
    O período de uma sequência é `última ação − primeira ação` da sequência; a sequência continua enquanto o intervalo entre
    duas ações consecutivas for INFERIOR a 72 h. Guarda a sequência corrente e a MELHOR já alcançada pela conta.
    """

    player = models.OneToOneField("players.Player", on_delete=models.CASCADE, related_name="activity_streak")
    current_start = models.BigIntegerField()
    last_action_at = models.BigIntegerField()
    best_start = models.BigIntegerField()
    best_end = models.BigIntegerField()
    best_length = models.BigIntegerField()            # segundos: best_end − best_start

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(last_action_at__gte=F("current_start")), name="activitystreak_current_ordered"),
            models.CheckConstraint(condition=Q(best_end__gte=F("best_start")), name="activitystreak_best_ordered"),
            models.CheckConstraint(condition=Q(best_length=F("best_end") - F("best_start")), name="activitystreak_best_length"),
            models.CheckConstraint(condition=Q(best_length__gte=F("last_action_at") - F("current_start")),
                                   name="activitystreak_best_not_below_current"),
        ]
        indexes = [models.Index(fields=["-best_length", "player"], name="activitystreak_rank_idx")]

    def __str__(self):
        return f"ActivityStreak(player={self.player_id}, best={self.best_length}s)"


class NetWorthCandidate(models.Model):
    """
    Candidato a recorde de patrimônio que NÃO pôde ser aplicado no fim da operação do ledger (ex.: falha ao gravar o recorde).
    Gravado na MESMA transação da operação financeira, para que a atualização nunca se perca em silêncio; reaplicado pela
    tarefa horária (`drain_net_worth_candidates`) com o valor e o instante que existiam na operação, e então removido.
    """

    player_id = models.BigIntegerField()
    value = models.BigIntegerField()
    at = models.BigIntegerField()                     # instante da operação financeira
    metadata = models.JSONField(default=dict)
    attempts = models.IntegerField(default=0)
    last_error = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        indexes = [models.Index(fields=["at", "id"], name="nwcandidate_order_idx")]


class QolSnapshot(models.Model):
    """
    Foto comparável da QoL de todos os jogadores elegíveis em UM instante de referência comum (design/14 §14.3.4).
    OPEN: coletando. COMPLETE: todos os elegíveis representados exatamente em `reference_at` (única que a página pública lê).
    INCOMPLETE: finalizada com jogadores que já tinham sido processados além da referência e cujo valor não pôde ser obtido;
    nunca é exibida, e a última COMPLETE é preservada.
    """

    OPEN, COMPLETE, INCOMPLETE = "open", "complete", "incomplete"

    reference_at = models.BigIntegerField(unique=True)
    status = models.CharField(max_length=10, default=OPEN, choices=[(OPEN, OPEN), (COMPLETE, COMPLETE), (INCOMPLETE, INCOMPLETE)])
    opened_at = models.BigIntegerField()
    finalized_at = models.BigIntegerField(null=True, blank=True)
    eligible = models.IntegerField(null=True, blank=True)        # jogadores com created_at_game <= reference_at
    represented = models.IntegerField(null=True, blank=True)
    missing = models.IntegerField(null=True, blank=True)
    metrics = models.JSONField(default=dict, blank=True)         # duração, consultas, jogadores por origem (14.9 / CLAUDE.md §9)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(status="open") | (Q(eligible__isnull=False, represented__isnull=False, missing__isnull=False,
                                                finalized_at__isnull=False)),
                name="qolsnapshot_final_has_counts"),
            models.CheckConstraint(
                condition=~Q(status="complete") | Q(missing=0, represented=models.F("eligible")),
                name="qolsnapshot_complete_means_all_represented"),
        ]
        indexes = [models.Index(fields=["status", "-reference_at"], name="qolsnapshot_status_idx")]


class QolSnapshotEntry(models.Model):
    player = models.ForeignKey("players.Player", on_delete=models.CASCADE, related_name="+")
    snapshot = models.ForeignKey(QolSnapshot, on_delete=models.CASCADE, related_name="entries")
    qol = models.DecimalField(max_digits=30, decimal_places=12)  # o valor EXATO de players.qol.qol_current em reference_at
    explained = models.JSONField(default=dict)                   # o detalhamento do MESMO cálculo (doc 20), não reconstruído
    source = models.CharField(max_length=10)                     # "advance" (captura ao avançar o jogador) ou "sweep"

    class Meta:
        constraints = [models.UniqueConstraint(fields=["snapshot", "player"], name="qolentry_unique_player")]
        indexes = [models.Index(fields=["snapshot", "-qol", "player"], name="qolentry_rank_idx")]
