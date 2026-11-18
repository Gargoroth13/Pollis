"""
Auditoria do Histórico do Mundo (design/12). Só LÊ. Invariantes:
  1  estrutura: categoria e prioridade válidas, modelo de texto existente, variação dentro do intervalo, ano/mês conferem com o instante
  2  marcos: todo marco (`milestone:*`) é da categoria Marco (a unicidade do marco é restrição única do banco)
  3  falência: só empresas de ≥ `BANKRUPTCY_MIN_STARS`★ têm notícia global (12.5)
  4  eleição: a porcentagem da notícia confere com votos/total guardados (12.6)
"""
from __future__ import annotations

from decimal import Decimal

from ledger.audit import AuditReport

from . import news, params, texts
from .constants import Category, Priority
from .models import NewsItem
from .publish import year_month


def audit_history() -> AuditReport:
    report = AuditReport()
    n = 0
    categories = {c.value for c in Category}
    priorities = {int(p) for p in Priority}
    known = set(texts.keys())
    for item in NewsItem.objects.order_by("pk").iterator():
        n += 1
        if item.category not in categories or item.priority not in priorities:
            report.add(1, "INVALID_CATEGORY_OR_PRIORITY", news=item.pk, category=item.category, priority=item.priority)
        if item.template_key not in known:
            report.add(1, "UNKNOWN_TEMPLATE", news=item.pk, template=item.template_key)
        elif not 0 <= item.variant < texts.variant_count(item.template_key):
            report.add(1, "VARIANT_OUT_OF_RANGE", news=item.pk, variant=item.variant)
        if (item.year, item.month) != year_month(item.at):
            report.add(1, "ARCHIVE_MONTH_MISMATCH", news=item.pk)
        if item.dedupe_key and item.dedupe_key.startswith("milestone:") and item.category != Category.MILESTONE.value:
            report.add(2, "MILESTONE_NOT_IN_MILESTONE_CATEGORY", news=item.pk)
        if item.template_key == "company.bankruptcy" and item.data.get("stars", 0) < params.BANKRUPTCY_MIN_STARS:
            report.add(3, "BANKRUPTCY_BELOW_MIN_STARS", news=item.pk, stars=item.data.get("stars"))
        if item.template_key == "politics.election_winner":
            try:
                expected = news.election_pct(item.data["votes"], item.data["total_votes"])
            except (KeyError, ValueError):
                report.add(4, "ELECTION_DATA_INVALID", news=item.pk)
            else:
                if Decimal(item.data["pct"]) != expected or texts.fmt_pct(expected) not in item.body:
                    report.add(4, "ELECTION_PCT_MISMATCH", news=item.pk, expected=str(expected))
    report.stats.update(news=n)
    return report
