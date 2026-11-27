"""Página pública de Rankings (design/14 §14.8): ao vivo e histórico visualmente separados. Só leitura."""
from __future__ import annotations

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import live, params
from .constants import Group, spec


def _limit(request):
    raw = request.GET.get("limit")
    if raw is None:
        return params.PAGE_SIZE
    try:
        value = int(raw)
    except ValueError:
        raise Http404("limit inválido") from None
    if value < 1:
        raise Http404("limit inválido")
    return min(value, params.MAX_PAGE_SIZE)


@require_GET
def index(request):
    return render(request, "rankings/index.html", live.page_data(limit=_limit(request)))


@require_GET
def data(request):
    """O mesmo conteúdo da página, estruturado (exportável; bots e Dashboard Dev usam a mesma fonte)."""
    return JsonResponse(live.page_data(limit=_limit(request)), json_dumps_params={"ensure_ascii": False})


@require_GET
def category(request, key):
    try:
        s = spec(key)
    except ValueError:
        raise Http404("categoria inexistente") from None
    body = live.live_ranking(s.key, limit=_limit(request)) if s.group == Group.LIVE else live.historical_ranking(s.key)
    return JsonResponse(body, json_dumps_params={"ensure_ascii": False})
