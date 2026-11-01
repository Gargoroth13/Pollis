"""
Ações legislativas no Action Registry (players.registry; design/07, design/21 §20). Nenhuma regra vive aqui: a disponibilidade vem das MESMAS
funções de recusa que a execução usa. Bots e jogadores usam o mesmo caminho (CLAUDE.md §5.4).

  propose_law          Formalizar proposta (Presidente/Deputado)  alvo = {"law", "params" | "revoke": true, ["description"]}
  edit_proposal        Alterar os parâmetros X na discussão (autor)  alvo = {"proposal", ["params"], ["description"]}
  withdraw_proposal    Retirar na discussão (autor)                alvo = {"proposal"}
  cast_vote            Votar sim/não/abstenção (Deputado)           alvo = {"proposal", "choice"}   (vale para a votação principal e a de derrubada)
  sanction_proposal    Sancionar (Presidente)                       alvo = {"proposal"}
  veto_proposal        Vetar (Presidente)                           alvo = {"proposal", ["justification"]}
  suggest_law          Sugerir ao Presidente (Governador/Prefeito)  alvo = como propose_law
  adopt_suggestion     Formalizar a sugestão (Presidente)           alvo = {"suggestion"}
  dismiss_suggestion   Descartar a sugestão (Presidente)            alvo = {"suggestion"}
"""
from __future__ import annotations

from typing import Any, Dict

from players.registry import TARGET_PARAMS, ActionDescriptor, TargetSpec, register_action

from . import preview, proposals, suggestions, voting
from .common import is_int

COMMON = ("INVALID_PARAMS", "PLAYER_NOT_FOUND")


def _spec(id_, name, requirements, effects):
    return ActionDescriptor(id=id_, name=name, requirements=COMMON + requirements, cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=effects)


def _propose_preview(player, now, bal, target) -> Dict[str, Any]:
    if not isinstance(target, dict) or "law" not in target:
        return {}
    values = target.get("params")
    from . import catalog
    spec = catalog.get(target["law"])
    if spec is None:
        return {}
    revoke = target.get("revoke") is True
    if not revoke:
        values = proposals.normalize_params(spec, values)
        if not isinstance(values, dict):
            return {}
    view = preview.preview(spec.key, values, revoke=revoke)
    return {} if view is None else {"preview": view}


def _no_preview(player, now, bal, target) -> Dict[str, Any]:
    return {}


def register() -> None:
    register_action(_spec("propose_law", "Formalizar proposta de lei",
                          ("NOT_A_PROPOSER", "OFFICE_CONFLICT", "UNKNOWN_LAW", "INVALID_DESCRIPTION", "INVALID_PARAM_VALUE", "PARAM_OUT_OF_RANGE", "NO_CHANGE",
                           "VALIDATION_FAILED", "BELOW_CONSTITUTIONAL_FLOOR", "LAW_NOT_IN_FORCE", "LAW_BLOCKED", "COOLDOWN_ACTIVE"),
                          ("proposal_created",)),
                    check=lambda player, now, bal, target: None if target is None else proposals.new_proposal_refusal(player.pk, target),
                    execute=proposals.create_proposal, preview=_propose_preview)
    register_action(_spec("edit_proposal", "Alterar proposta na discussão",
                          ("PROPOSAL_NOT_FOUND", "NOT_AUTHOR", "NOT_IN_DISCUSSION", "VOTING_STARTED", "NO_CHANGE", "NOTHING_CHANGED", "PARAM_OUT_OF_RANGE",
                           "VALIDATION_FAILED", "BELOW_CONSTITUTIONAL_FLOOR"), ("proposal_edited",)),
                    check=lambda player, now, bal, target: None if target is None else proposals.edit_refusal(player.pk, target),
                    execute=proposals.edit_proposal, preview=_no_preview)
    register_action(_spec("withdraw_proposal", "Retirar proposta na discussão", ("PROPOSAL_NOT_FOUND", "NOT_AUTHOR", "NOT_IN_DISCUSSION", "VOTING_STARTED"),
                          ("proposal_withdrawn",)),
                    check=lambda player, now, bal, target: None if target is None else proposals.withdraw_refusal(player.pk, target),
                    execute=proposals.withdraw_proposal, preview=_no_preview)
    register_action(_spec("cast_vote", "Votar na Câmara", ("INVALID_CHOICE", "PROPOSAL_NOT_FOUND", "NOT_VOTING", "VOTE_CLOSED", "NOT_A_VOTER", "NOT_A_DEPUTY",
                                                          "OFFICE_CONFLICT"), ("vote_recorded",)),
                    check=lambda player, now, bal, target: None if target is None else voting.cast_refusal(player.pk, target),
                    execute=voting.cast_vote, preview=_no_preview)
    register_action(_spec("sanction_proposal", "Sancionar proposta aprovada",
                          ("PROPOSAL_NOT_FOUND", "NOT_AWAITING_SANCTION", "NOT_PRESIDENT", "OFFICE_CONFLICT", "SANCTION_DEADLINE_PASSED"), ("proposal_sanctioned",)),
                    check=lambda player, now, bal, target: None if target is None else voting.sanction_refusal(player.pk, target),
                    execute=voting.sanction, preview=_no_preview)
    register_action(_spec("veto_proposal", "Vetar proposta aprovada",
                          ("INVALID_JUSTIFICATION", "PROPOSAL_NOT_FOUND", "NOT_AWAITING_SANCTION", "NOT_PRESIDENT", "OFFICE_CONFLICT", "SANCTION_DEADLINE_PASSED"),
                          ("proposal_vetoed",)),
                    check=lambda player, now, bal, target: None if target is None else voting.veto_refusal(player.pk, target),
                    execute=voting.veto, preview=_no_preview)
    register_action(_spec("suggest_law", "Sugerir lei ao Presidente",
                          ("NOT_A_SUGGESTER", "UNKNOWN_LAW", "INVALID_DESCRIPTION", "INVALID_PARAM_VALUE", "PARAM_OUT_OF_RANGE", "VALIDATION_FAILED"),
                          ("suggestion_created",)),
                    check=lambda player, now, bal, target: None if target is None else suggestions.suggest_refusal(player.pk, target),
                    execute=suggestions.suggest_law, preview=_no_preview)
    register_action(_spec("adopt_suggestion", "Formalizar sugestão como proposta",
                          ("NOT_PRESIDENT", "OFFICE_CONFLICT", "SUGGESTION_NOT_FOUND", "SUGGESTION_DECIDED", "LAW_BLOCKED", "COOLDOWN_ACTIVE", "NO_CHANGE",
                           "VALIDATION_FAILED"), ("proposal_created", "suggestion_adopted")),
                    check=lambda player, now, bal, target: None if target is None else suggestions.adopt_refusal(player.pk, target),
                    execute=suggestions.adopt_suggestion, preview=_no_preview)
    register_action(_spec("dismiss_suggestion", "Descartar sugestão", ("NOT_PRESIDENT", "OFFICE_CONFLICT", "SUGGESTION_NOT_FOUND", "SUGGESTION_DECIDED"),
                          ("suggestion_dismissed",)),
                    check=lambda player, now, bal, target: None if target is None else suggestions.dismiss_refusal(player.pk, target),
                    execute=suggestions.dismiss_suggestion, preview=_no_preview)
