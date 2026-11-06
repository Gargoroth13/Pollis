"""
Instrumentação leve para PRODUÇÃO (CLAUDE.md §9: medir tempo de banco e queries antes de otimizar).
Não depende de utilitários de teste: usa `connection.execute_wrapper`, o ponto de extensão oficial do Django, que não exige
`DEBUG` nem guarda o texto das queries — só conta e soma o tempo.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

from django.db import connection as default_connection


class QueryCounter:
    """`with QueryCounter() as q: ...` → `q.count` (queries executadas) e `q.db_seconds` (tempo gasto nelas)."""

    def __init__(self, connection=None):
        self._connection = connection or default_connection
        self.count = 0
        self.db_seconds = 0.0
        self._cm = None

    def _wrapper(self, execute, sql, params, many, context):
        started = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.count += 1
            self.db_seconds += time.perf_counter() - started

    def __enter__(self) -> "QueryCounter":
        self._cm = self._connection.execute_wrapper(self._wrapper)
        self._cm.__enter__()
        return self

    def __exit__(self, *exc):
        return self._cm.__exit__(*exc)

    def __len__(self) -> int:
        return self.count


@contextmanager
def stopwatch():
    """`with stopwatch() as t: ...` → `t()` devolve os segundos decorridos até agora (ou o total, depois de sair)."""
    started = time.perf_counter()
    end = []
    yield lambda: (end[0] if end else time.perf_counter()) - started
    end.append(time.perf_counter())
