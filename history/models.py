"""
Notícia do Histórico do Mundo (design/12). Cada notícia é PERMANENTE (12.10): não se edita nem se apaga (nem em lote). Guarda o texto
final (manchete + resumo), os dados estruturados que o originaram (12.11: o jogador não vê o bruto, mas Dev/Admin sim) e a referência.
"""
from __future__ import annotations

from django.db import models
from django.db.models import Q

from .constants import CATEGORY_LABELS, Category, Priority


class NewsImmutableError(Exception):
    pass


class NewsQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise NewsImmutableError("notícias são permanentes (12.10)")

    def delete(self):
        raise NewsImmutableError("notícias são permanentes (12.10)")


def _choices(enum):
    return [(m.value, m.value) for m in enum]


class NewsItem(models.Model):
    at = models.BigIntegerField()                                    # quando o acontecimento ocorreu (instante lógico do jogo)
    published_at = models.BigIntegerField()                          # quando a notícia foi escrita (relógio do jogo)
    year = models.SmallIntegerField()                                # ano/mês do calendário local do jogo, para o arquivo (12.10)
    month = models.SmallIntegerField()
    category = models.CharField(max_length=12, choices=[(c.value, CATEGORY_LABELS[c]) for c in Category])
    priority = models.SmallIntegerField()                            # 12.13; só desempata; não é mostrada ao jogador
    template_key = models.CharField(max_length=60)
    variant = models.SmallIntegerField()                             # qual variação do modelo de texto foi usada (12.3)
    headline = models.CharField(max_length=200)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)                # dados estruturados do acontecimento (auditoria, 12.11)
    ref_kind = models.CharField(max_length=24, blank=True, default="")
    ref_id = models.CharField(max_length=80, blank=True, default="")
    dedupe_key = models.CharField(max_length=160, null=True, blank=True)       # idempotência e marco único (12.8)
    indicator_key = models.CharField(max_length=100, blank=True, default="")   # intervalo mínimo entre notícias do mesmo indicador (12.12)

    objects = NewsQuerySet.as_manager()

    class Meta:
        ordering = ["-at", "priority", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["dedupe_key"], condition=Q(dedupe_key__isnull=False), name="news_unique_dedupe_key"),
            models.CheckConstraint(condition=Q(priority__gte=min(Priority)) & Q(priority__lte=max(Priority)), name="news_priority_in_range"),
            models.CheckConstraint(condition=~Q(headline=""), name="news_headline_not_empty"),
            models.CheckConstraint(condition=Q(month__gte=1) & Q(month__lte=12), name="news_month_in_range"),
        ]
        indexes = [
            models.Index(fields=["-at", "priority", "-id"], name="news_feed"),
            models.Index(fields=["category", "-at", "priority", "-id"], name="news_feed_category"),
            models.Index(fields=["indicator_key", "at"], name="news_indicator_at"),
            models.Index(fields=["year", "month"], name="news_archive"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise NewsImmutableError("notícias são permanentes (12.10)")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise NewsImmutableError("notícias são permanentes (12.10)")

    def __str__(self):
        return f"News({self.pk}:{self.headline[:40]})"
