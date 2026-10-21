"""
Ações das Empresas no Action Registry (players.registry; design/21 §20). Nenhuma regra vive aqui: a disponibilidade vem das MESMAS
funções de recusa que a execução usa, o efeito é o do serviço dono e o feedback vem dos `Explained` (20). Bots e jogadores
reais usam o mesmo caminho (CLAUDE.md §5.4).

  found_company  Fundar empresa   alvo = {"type": tipo, "name": texto, "owner_salary_cents": n}
  fund_company   Aportar capital  alvo = {"company": id, "amount_cents": n}

Cargos e mural (P1.04b; `jobs`): só o Dono abre/fecha vaga, aprova, rejeita e demite (GD 2026-10-19).
  open_position         Abrir vaga        alvo = {"company": id, "kind": cargo, "salary_cents": n, "requirements": {skill: nível}}
  close_position        Fechar vaga       alvo = {"position": id}
  apply_position        Candidatar-se     alvo = {"position": id}
  withdraw_application  Retirar candidatura  alvo = {"application": id}
  approve_application   Aprovar candidato    alvo = {"application": id}
  reject_application    Rejeitar candidato   alvo = {"application": id}
  dismiss_employee      Demitir funcionário  alvo = {"position": id}
  resign                Pedir demissão       sem alvo

Produção (P1.04c; `production`): só o Dono escolhe/troca o produto.
  set_production        Definir produção     alvo = {"company": id, "product": chave do catálogo}

Obra da Construtora (P1.04e; `construction`): só o Dono escolhe e inicia a obra.
  start_construction    Iniciar obra         alvo = {"company": id, "project": chave do projeto}
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from players.registry import TARGET_PARAMS, ActionDescriptor, TargetSpec, register_action
from players.services import ActionResult

from . import construction, jobs, production, services

FOUND_ID = "found_company"
FUND_ID = "fund_company"
FOUND_KEYS = frozenset({"type", "name", "owner_salary_cents"})
FUND_KEYS = frozenset({"company", "amount_cents"})


def _invalid(action: str, keys, target) -> ActionResult:
    return ActionResult(False, "INVALID_PARAMS", {"action": action, "expected": sorted(keys), "target": repr(target)[:80]})


def _params(target, keys) -> Optional[dict]:
    return target if isinstance(target, dict) and set(target) == keys else None


def _found_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    p = _params(target, FOUND_KEYS)
    return _invalid(FOUND_ID, FOUND_KEYS, target) if p is None else services.founding_refusal(
        player.pk, p["type"], p["name"], p["owner_salary_cents"])


def _found_execute(player_id: int, target: Any) -> ActionResult:
    p = _params(target, FOUND_KEYS)
    return _invalid(FOUND_ID, FOUND_KEYS, target) if p is None else services.found_company(
        player_id, p["type"], p["name"], p["owner_salary_cents"])


def _found_preview(player, now, bal, target) -> Dict[str, Any]:
    p = _params(target, FOUND_KEYS) if target is not None else None
    if p is None or not isinstance(p["type"], str):
        return {}
    cost = services.founding_cost(p["type"])
    return {} if cost is None else {"cost": cost, "cost_cents": int(cost.value)}


def _fund_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    p = _params(target, FUND_KEYS)
    return _invalid(FUND_ID, FUND_KEYS, target) if p is None else services.contribution_refusal(
        player.pk, p["company"], p["amount_cents"])


def _fund_execute(player_id: int, target: Any) -> ActionResult:
    p = _params(target, FUND_KEYS)
    return _invalid(FUND_ID, FUND_KEYS, target) if p is None else services.fund_company(
        player_id, p["company"], p["amount_cents"])


def _fund_preview(player, now, bal, target) -> Dict[str, Any]:
    return {}


OPEN_ID, CLOSE_ID, APPLY_ID = "open_position", "close_position", "apply_position"
WITHDRAW_ID, APPROVE_ID, REJECT_ID = "withdraw_application", "approve_application", "reject_application"
DISMISS_ID, RESIGN_ID = "dismiss_employee", "resign"
OPEN_KEYS = frozenset({"company", "kind", "salary_cents", "requirements"})
POSITION_KEYS = frozenset({"position"})
APPLICATION_KEYS = frozenset({"application"})


def _open_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    p = _params(target, OPEN_KEYS)
    return _invalid(OPEN_ID, OPEN_KEYS, target) if p is None else jobs.open_position_refusal(
        player.pk, p["company"], p["kind"], p["salary_cents"], p["requirements"])


def _open_execute(player_id: int, target: Any) -> ActionResult:
    p = _params(target, OPEN_KEYS)
    return _invalid(OPEN_ID, OPEN_KEYS, target) if p is None else jobs.open_position(
        player_id, p["company"], p["kind"], p["salary_cents"], p["requirements"])


def _single(action_id: str, keys, field: str, refusal_fn, execute_fn):
    """Ação de um só parâmetro (`position` ou `application`): disponibilidade e execução usam as mesmas funções do `jobs`."""
    def check(player, now, bal, target) -> Optional[ActionResult]:
        if target is None:
            return None
        p = _params(target, keys)
        return _invalid(action_id, keys, target) if p is None else refusal_fn(player.pk, p[field])

    def execute(player_id: int, target: Any) -> ActionResult:
        p = _params(target, keys)
        return _invalid(action_id, keys, target) if p is None else execute_fn(player_id, p[field])

    return check, execute


def _no_preview(player, now, bal, target) -> Dict[str, Any]:
    return {}


def _resign_check(player, now, bal, target) -> Optional[ActionResult]:
    return jobs.resign_refusal(player.pk)


def _resign_execute(player_id: int, target: Any) -> ActionResult:
    return jobs.resign(player_id)


def _register_jobs() -> None:
    register_action(
        ActionDescriptor(
            id=OPEN_ID, name="Abrir vaga no mural",
            requirements=("INVALID_PARAMS", "COMPANY_NOT_FOUND", "NOT_OWNER", "INVALID_POSITION_KIND",
                          "POSITION_KIND_NOT_ALLOWED", "INVALID_SALARY", "SUPPORT_LIMIT_REACHED", "INVALID_REQUIREMENTS"),
            cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("position_opened",)),
        check=_open_check, execute=_open_execute, preview=_no_preview)
    for action_id, name, keys, field, refusal_fn, execute_fn, reqs, effects in (
            (CLOSE_ID, "Fechar vaga", POSITION_KEYS, "position", jobs.close_position_refusal, jobs.close_position,
             ("INVALID_PARAMS", "POSITION_NOT_FOUND", "NOT_OWNER", "POSITION_NOT_OPEN"), ("position_closed",)),
            (APPLY_ID, "Candidatar-se a uma vaga", POSITION_KEYS, "position", jobs.apply_refusal, jobs.apply_to_position,
             ("INVALID_PARAMS", "POSITION_NOT_FOUND", "POSITION_NOT_OPEN", "ALREADY_APPLIED", "REQUIREMENTS_NOT_MET"),
             ("application_created",)),
            (WITHDRAW_ID, "Retirar candidatura", APPLICATION_KEYS, "application", jobs.withdraw_refusal,
             jobs.withdraw_application, ("INVALID_PARAMS", "APPLICATION_NOT_FOUND", "NOT_APPLICANT", "APPLICATION_NOT_PENDING"),
             ("application_withdrawn",)),
            (APPROVE_ID, "Aprovar candidato", APPLICATION_KEYS, "application", jobs.approve_refusal, jobs.approve_application,
             ("INVALID_PARAMS", "APPLICATION_NOT_FOUND", "NOT_OWNER", "APPLICATION_NOT_PENDING", "POSITION_NOT_OPEN",
              "ALREADY_EMPLOYED", "REQUIREMENTS_NOT_MET"), ("employee_hired",)),
            (REJECT_ID, "Rejeitar candidato", APPLICATION_KEYS, "application", jobs.reject_refusal, jobs.reject_application,
             ("INVALID_PARAMS", "APPLICATION_NOT_FOUND", "NOT_OWNER", "APPLICATION_NOT_PENDING"), ("application_rejected",)),
            (DISMISS_ID, "Demitir funcionário", POSITION_KEYS, "position", jobs.dismiss_refusal, jobs.dismiss,
             ("INVALID_PARAMS", "POSITION_NOT_FOUND", "NOT_OWNER", "CANNOT_DISMISS_OWNER", "POSITION_NOT_FILLED"),
             ("employee_dismissed",))):
        check, execute = _single(action_id, keys, field, refusal_fn, execute_fn)
        register_action(
            ActionDescriptor(id=action_id, name=name, requirements=reqs, cost=(), target=TargetSpec(TARGET_PARAMS, required=True),
                             effects=effects),
            check=check, execute=execute, preview=_no_preview)
    register_action(
        ActionDescriptor(id=RESIGN_ID, name="Pedir demissão", requirements=("NOT_EMPLOYED",), cost=(), target=TargetSpec(),
                         effects=("employee_resigned",)),
        check=_resign_check, execute=_resign_execute, preview=_no_preview)


SET_PRODUCTION_ID = "set_production"
SET_PRODUCTION_KEYS = frozenset({"company", "product"})


def _set_production_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    p = _params(target, SET_PRODUCTION_KEYS)
    return _invalid(SET_PRODUCTION_ID, SET_PRODUCTION_KEYS, target) if p is None else production.selection_refusal(
        player.pk, p["company"], p["product"], now)


def _set_production_execute(player_id: int, target: Any) -> ActionResult:
    p = _params(target, SET_PRODUCTION_KEYS)
    return _invalid(SET_PRODUCTION_ID, SET_PRODUCTION_KEYS, target) if p is None else production.set_production(
        player_id, p["company"], p["product"])


def _register_production() -> None:
    register_action(
        ActionDescriptor(
            id=SET_PRODUCTION_ID, name="Definir produção da empresa",
            requirements=("INVALID_PARAMS", "COMPANY_NOT_FOUND", "NOT_OWNER", "COMPANY_TYPE_CANNOT_PRODUCE", "UNKNOWN_PRODUCT",
                          "PRODUCT_NOT_FOR_COMPANY_TYPE", "MATRIX_SITE_UNDEFINED", "PRODUCT_OUTSIDE_TERRAIN_CATEGORY",
                          "PRODUCTION_NOT_READY", "STARS_TOO_LOW", "ALREADY_PRODUCING", "COOLDOWN_ACTIVE",
                          "PRODUCTION_CHANGE_COST_UNDEFINED"),
            cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("production_selected", "setup_started")),
        check=_set_production_check, execute=_set_production_execute, preview=_no_preview)


START_CONSTRUCTION_ID = "start_construction"
START_CONSTRUCTION_KEYS = frozenset({"company", "project"})


def _start_construction_check(player, now, bal, target) -> Optional[ActionResult]:
    if target is None:
        return None
    p = _params(target, START_CONSTRUCTION_KEYS)
    return _invalid(START_CONSTRUCTION_ID, START_CONSTRUCTION_KEYS, target) if p is None else construction.start_refusal(
        player.pk, p["company"], p["project"])


def _start_construction_execute(player_id: int, target: Any) -> ActionResult:
    p = _params(target, START_CONSTRUCTION_KEYS)
    return _invalid(START_CONSTRUCTION_ID, START_CONSTRUCTION_KEYS, target) if p is None else construction.start_construction(
        player_id, p["company"], p["project"])


def _register_construction() -> None:
    register_action(
        ActionDescriptor(
            id=START_CONSTRUCTION_ID, name="Iniciar obra da Construtora",
            requirements=("INVALID_PARAMS", "COMPANY_NOT_FOUND", "NOT_OWNER", "COMPANY_TYPE_CANNOT_BUILD", "UNKNOWN_PROJECT",
                          "STARS_TOO_LOW", "CONSTRUCTION_ACTIVE"),
            cost=(), target=TargetSpec(TARGET_PARAMS, required=True), effects=("construction_started",)),
        check=_start_construction_check, execute=_start_construction_execute, preview=_no_preview)


def register() -> None:
    _register_jobs()
    _register_production()
    _register_construction()
    register_action(
        ActionDescriptor(
            id=FOUND_ID, name="Fundar empresa",
            requirements=("INVALID_PARAMS", "INVALID_COMPANY_TYPE", "INVALID_NAME", "INVALID_SALARY", "INSUFFICIENT_FUNDS"),
            cost=("money",), target=TargetSpec(TARGET_PARAMS, required=True),
            effects=("company_founded", "owner_position_created", "founding_fee_charged")),
        check=_found_check, execute=_found_execute, preview=_found_preview)
    register_action(
        ActionDescriptor(
            id=FUND_ID, name="Aportar capital na empresa",
            requirements=("INVALID_PARAMS", "INVALID_AMOUNT", "COMPANY_NOT_FOUND", "NOT_OWNER", "INSUFFICIENT_FUNDS"),
            cost=("money",), target=TargetSpec(TARGET_PARAMS, required=True), effects=("capital_contributed",)),
        check=_fund_check, execute=_fund_execute, preview=_fund_preview)
