"""
Publicação de notícias (design/12 §12.2): quem decide que algo é noticiável é o SISTEMA DE ORIGEM; o 12 só transforma o acontecimento
estruturado em notícia (manchete + resumo), com variação de texto, idempotência, marco único e intervalo mínimo por indicador (12.12).
Nada aqui descobre acontecimentos sozinho nem lê histórico bruto.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.db import IntegrityError, transaction

from core import clock as game_clock
from ledger.money import competence_day_of

from . import params, texts
from .constants import Category, Priority, Status
from .models import NewsItem


@dataclass(frozen=True)
class Published:
    status: str
    item: Optional[NewsItem] = None
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.status == Status.PUBLISHED


def jsonable(value: Any) -> Any:
    """Dados estruturados da notícia em JSON: Decimal vira texto exato, nunca float."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def year_month(at: int) -> Tuple[int, int]:
    d = date.fromordinal(competence_day_of(at))
    return d.year, d.month


def publish(template_key: str, data: Dict[str, Any], *, category: Category, priority: Priority, at: Optional[int] = None,
            ref: Optional[Tuple[str, Any]] = None, dedupe_key: Optional[str] = None, indicator: str = "",
            min_interval: Optional[int] = None, structured: Optional[Dict[str, Any]] = None) -> Published:
    """
    Publica uma notícia e devolve o resultado (nunca silencia um erro de dados: campo faltando no modelo levanta `TemplateError`).
      - `dedupe_key` já publicada → DUPLICATE (idempotência e marco único; seguro sob concorrência pela restrição única do banco);
      - `indicator` + `min_interval`: se já há notícia do mesmo indicador a menos de `min_interval` segundos de `at` → SUPPRESSED.
    `data` alimenta o texto; `structured` (padrão: `data`) é guardado para auditoria.
    """
    if not isinstance(category, Category) or not isinstance(priority, Priority):
        raise ValueError("categoria e prioridade devem ser Category/Priority")
    now = game_clock.now()
    at = now if at is None else at
    if dedupe_key is not None and NewsItem.objects.filter(dedupe_key=dedupe_key).exists():
        return Published(Status.DUPLICATE, NewsItem.objects.get(dedupe_key=dedupe_key), "dedupe_key")
    if indicator and min_interval and NewsItem.objects.filter(indicator_key=indicator, at__gt=at - min_interval, at__lt=at + min_interval).exists():
        return Published(Status.SUPPRESSED, None, "min_interval")
    ref_kind, ref_id = ("", "") if ref is None else (ref[0], str(ref[1]))
    seed = dedupe_key or f"{indicator}|{ref_kind}:{ref_id}|{at}"
    variant, headline, body = texts.render(template_key, data, seed)
    year, month = year_month(at)
    item = NewsItem(at=at, published_at=now, year=year, month=month, category=category.value, priority=int(priority), template_key=template_key,
                    variant=variant, headline=headline[:params.HEADLINE_MAX], body=body, data=jsonable(structured if structured is not None else data),
                    ref_kind=ref_kind, ref_id=ref_id, dedupe_key=dedupe_key, indicator_key=indicator)
    try:
        with transaction.atomic():
            item.save()
    except IntegrityError:
        existing = NewsItem.objects.filter(dedupe_key=dedupe_key).first() if dedupe_key is not None else None
        if existing is None:
            raise
        return Published(Status.DUPLICATE, existing, "dedupe_key")
    return Published(Status.PUBLISHED, item)
