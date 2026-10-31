"""
Action Masking (21 §21.21) sobre o Action Registry COMPARTILHADO (21 §21.20, CLAUDE.md §5.4): a máscara é a disponibilidade GERAL que o próprio registro
informa ao jogador; o Bot não tem catálogo de ações próprio. A máscara não remove regras: a execução revalida tudo.
"""
from __future__ import annotations

from typing import Dict

from players import registry


def action_mask(player_id: int) -> Dict[str, Dict[str, object]]:
    """{ação: {"available": 0|1, "target_required": bool, "code": str}} em ordem estável de id."""
    return {a.action_id: {"available": int(a.available), "target_required": a.target_required, "code": a.code}
            for a in registry.available_actions(player_id)}
