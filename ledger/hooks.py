"""
Ganchos de FIM DE OPERAÇÃO do registro monetário (extensão pequena; não altera nenhuma regra monetária).

Para quem precisa reagir a "o patrimônio de uma conta pode ter mudado" (ex.: Rankings, recorde de patrimônio) sem polling.
  - Uma OPERAÇÃO financeira é uma chamada pública que muda saldo ou obrigações (`post_transaction` e as que a usam,
    `open_obligation`, `settle_obligations`, `cancel_obligation`, `liquidate_remuneration`). Operações aninhadas (a quitação que
    posta transações; a liquidação que quita e abre obrigações) formam UMA operação: o gancho roda UMA vez, quando a operação
    mais externa termina, com o estado FINAL (obrigações já atualizadas), nunca no meio dela.
  - Roda DENTRO da transação do banco da operação, antes do commit: se a operação for desfeita, o efeito do gancho também é;
    se o gancho levantar erro, a operação inteira é desfeita (nunca se perde silenciosamente uma atualização).
  - `fn(account_ids, at)`: contas cujo saldo ou obrigações mudaram (só as que de fato escreveram) e o instante da operação.
Execução idempotente (repetir uma operação com a mesma chave não escreve nada e não dispara o gancho).
"""
from __future__ import annotations

import contextlib
import contextvars
import functools
from typing import Callable, Dict, FrozenSet, Iterable, Iterator, List, Optional

OperationHook = Callable[[FrozenSet[int], int], None]
_hooks: Dict[str, OperationHook] = {}
_state: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar("ledger_operation", default=None)


def register_operation_hook(name: str, fn: OperationHook) -> None:
    if name in _hooks:
        raise ValueError(f"gancho de operação duplicado: {name}")
    _hooks[name] = fn


def unregister_operation_hook(name: str) -> None:
    _hooks.pop(name, None)


def clear_operation_hooks() -> None:         # para testes
    _hooks.clear()


def operation_hook_names() -> List[str]:
    return sorted(_hooks)


def _fire(accounts: Iterable[int], at: int) -> None:
    ids = frozenset(accounts)
    if not ids:
        return
    for name in sorted(_hooks):
        _hooks[name](ids, at)


@contextlib.contextmanager
def operation() -> Iterator[None]:
    """Delimita uma operação. Use DENTRO da transação (`transaction.atomic`) da operação mais externa."""
    st = _state.get()
    if st is not None:                       # aninhada: só participa da operação externa
        st["depth"] += 1
        try:
            yield
        finally:
            st["depth"] -= 1
        return
    st = {"depth": 0, "touched": set(), "at": None}
    token = _state.set(st)
    try:
        yield
    except BaseException:
        _state.reset(token)
        raise
    _state.reset(token)
    _fire(st["touched"], st["at"] if st["at"] is not None else 0)


def touch(account_id: int, at: int) -> None:
    """Marca uma conta como afetada pela operação corrente (chame só depois de escrever)."""
    st = _state.get()
    if st is None:                           # fora de uma operação delimitada: dispara já (nunca perde o aviso)
        _fire([account_id], at)
        return
    st["touched"].add(account_id)
    st["at"] = at if st["at"] is None else max(st["at"], at)


def as_operation(fn):
    """Decorador: a função INTEIRA é uma operação (transação do banco + delimitação do gancho de fim de operação)."""
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        from django.db import transaction
        with transaction.atomic():
            with operation():
                return fn(*args, **kwargs)
    return inner
