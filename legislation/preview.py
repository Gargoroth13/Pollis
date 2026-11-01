"""
Preview de impacto de uma proposta (design/07 §07.24): efeitos DIRETOS conhecidos, ESTIMATIVAS (identificadas como tal) e validações de coerência.

Estimadores são registrados pelos sistemas afetados (`register_estimator`); sem estimador a lista de estimativas fica vazia, nunca inventada.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from . import catalog, laws, proposals
from .models import Proposal

Estimator = Callable[[catalog.LawSpec, Dict[str, Any], Dict[str, Any]], List[Dict[str, Any]]]     # (lei, atuais, propostos) -> [{"key","value",...}]
_estimators: Dict[str, Estimator] = {}


def register_estimator(law_key: str, fn: Estimator) -> None:
    _estimators[law_key] = fn


def clear_estimators() -> None:       # para testes
    _estimators.clear()


def preview(law_key: str, values: Optional[Dict[str, Any]], revoke: bool = False) -> Optional[Dict[str, Any]]:
    spec = catalog.get(law_key)
    if spec is None:
        return None
    current = laws.current_values(law_key)
    proposed = spec.defaults() if revoke else values
    direct = [{"param": p.name, "from": current[p.name], "to": proposed[p.name], "changed": current[p.name] != proposed[p.name]} for p in spec.params]
    estimates: List[Dict[str, Any]] = []
    if law_key in _estimators:
        estimates = [{**e, "is_estimate": True} for e in _estimators[law_key](spec, current, proposed)]
    checks = [] if revoke else proposals.coherence_checks(spec, proposed)
    return {"law": law_key, "revoke": revoke, "direct_effects": direct, "estimated_effects": estimates, "validations": checks,
            "valid": all(c["ok"] for c in checks), "estimates_note": "estimates_are_not_guarantees" if estimates else ""}


def proposal_preview(proposal: Proposal) -> Optional[Dict[str, Any]]:
    from .constants import Kind
    return preview(proposal.law_key, proposal.params, revoke=proposal.kind == Kind.REVOKE.value)
