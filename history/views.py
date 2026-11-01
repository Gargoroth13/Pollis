"""
Consultas públicas do Histórico do Mundo (design/12 §12.1, §12.10). Só LEEM a tabela de notícias (já agregada pelos sistemas de origem):
nenhuma consulta aqui toca transações, lançamentos ou qualquer histórico bruto (12.15, "Performance"). A prioridade (12.13) só ordena e
não é exposta ao jogador.

Ordem do feed: mais recentes primeiro; no mesmo instante, a de maior prioridade (menor número) primeiro; depois a mais nova.
Paginação por cursor `(at, priority, id)` estável: notícias novas não deslocam as páginas já lidas.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from django.db.models import Count, Q

from . import params
from .constants import CATEGORY_LABELS, Category, Priority
from .models import NewsItem

Cursor = Tuple[int, int, int]
RefResolver = Callable[[str], Optional[str]]
_ref_resolvers: Dict[str, RefResolver] = {}


def register_ref_resolver(kind: str, resolver: RefResolver) -> None:
    """A referência da notícia leva à página do objeto QUANDO existe página (12.1): quem tem a página registra como montar o caminho."""
    _ref_resolvers[kind] = resolver


def clear_ref_resolvers() -> None:       # para testes
    _ref_resolvers.clear()


def filters() -> List[Dict[str, Optional[str]]]:
    """Filtros iniciais da página (12.1): Todas + as 5 categorias."""
    return [{"key": None, "label": "Todas"}] + [{"key": c.value, "label": CATEGORY_LABELS[c]} for c in Category]


def news_view(item: NewsItem) -> Dict[str, Any]:
    ref = None
    if item.ref_kind:
        resolver = _ref_resolvers.get(item.ref_kind)
        ref = {"kind": item.ref_kind, "id": item.ref_id, "path": resolver(item.ref_id) if resolver else None}
    return {"id": item.pk, "at": item.at, "category": item.category, "category_label": CATEGORY_LABELS[Category(item.category)],
            "headline": item.headline, "body": item.body, "ref": ref}


def _cursor_of(item: NewsItem) -> Cursor:
    return (item.at, item.priority, item.pk)


def feed(category: Optional[str] = None, limit: int = params.FEED_PAGE_SIZE, after: Optional[Cursor] = None) -> Dict[str, Any]:
    """Uma página do feed. `after` é o `next` da página anterior. Categoria inexistente → ValueError (nunca um feed vazio enganoso)."""
    if category is not None and category not in {c.value for c in Category}:
        raise ValueError(f"categoria inexistente: {category!r}")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit inválido")
    limit = min(limit, params.FEED_MAX_PAGE_SIZE)
    qs = NewsItem.objects.all()
    if category is not None:
        qs = qs.filter(category=category)
    if after is not None:
        at, priority, pk = after
        # (at DESC, priority ASC, id DESC): o que vem DEPOIS do cursor
        qs = qs.filter(Q(at__lt=at) | Q(at=at, priority__gt=priority) | Q(at=at, priority=priority, pk__lt=pk))
    rows = list(qs.order_by("-at", "priority", "-id")[:limit + 1])
    page, more = rows[:limit], len(rows) > limit
    return {"items": [news_view(i) for i in page], "next": _cursor_of(page[-1]) if more else None, "category": category}


def archive_index() -> List[Dict[str, int]]:
    """Meses com notícia (12.10), do mais recente ao mais antigo, com a contagem. O ano/mês é do calendário do jogo (lacuna H2 em design/12a)."""
    rows = NewsItem.objects.order_by().values("year", "month").annotate(n=Count("id")).order_by("-year", "-month")
    return [{"year": r["year"], "month": r["month"], "count": r["n"]} for r in rows]


def archive_month(year: int, month: int, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Todas as notícias do mês, em ordem cronológica (arquivo histórico), qualquer que seja a idade."""
    qs = NewsItem.objects.filter(year=year, month=month)
    if category is not None:
        if category not in {c.value for c in Category}:
            raise ValueError(f"categoria inexistente: {category!r}")
        qs = qs.filter(category=category)
    return [news_view(i) for i in qs.order_by("at", "-priority", "id")]


def milestones() -> List[Dict[str, Any]]:
    """Marcos únicos do servidor (12.8), do mais antigo ao mais novo."""
    return [news_view(i) for i in NewsItem.objects.filter(category=Category.MILESTONE.value).order_by("at", "id")]
