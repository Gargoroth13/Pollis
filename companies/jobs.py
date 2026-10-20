"""
Cargos, mural de vagas, candidaturas e vínculo (design/02 §15-16; decisões do GD em `02` §25).

Fluxo do §15: vaga aberta → mural público → jogador se candidata → o Dono aprova → cargo ocupado. Só o **Dono** abre/fecha vagas,
aprova, rejeita e demite (GD 2026-10-19: sem delegação nesta fase). Um jogador tem no máximo UM emprego contratado; o cargo Dono
não conta (02 §16; restrição de banco `position_one_job_per_player`).

PROTOCOLO DE TRAVAMENTO (o mesmo de `services`, estendido): 1) jogadores envolvidos em ordem crescente de id; 2) a empresa;
3) a vaga; 4) a candidatura; depois o registro monetário. Toda operação que MUDA o ocupante de uma vaga trava antes a linha do
jogador que entra/sai, então o salário do Trabalho (que roda com o funcionário já travado) enxerga um vínculo estável.
A limpeza de candidaturas de OUTRAS empresas na contratação só ATUALIZA linhas (sem eventos): inserir um evento lá tomaria
`FOR KEY SHARE` numa empresa/vaga que outra operação pode estar travando (ciclo).

Nada aqui move dinheiro. Salário: `payroll.py`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from django.db import transaction

from core import clock as game_clock
from players.models import Player
from players.services import ActionResult
from skills import rules as skill_rules
from skills.constants import Skill
from skills.services import get_levels

from . import params
from .constants import (MAX_REQUIREMENT_LEVEL, MAX_SALARY_CENTS, MURAL_PAGE_LIMIT, SUPPORT_POSITION_KINDS, ApplicationStatus, CompanyType, EventKind,
                        PositionKind, PositionStatus)
from .models import Application, Company, Position, PositionEvent
from .services import owner_of

_INT64 = 2 ** 63


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _id_ok(value: Any) -> bool:
    return _is_int(value) and -_INT64 <= value < _INT64


def relevant_skill(kind) -> Skill:
    """Skill relevante do cargo (01 §1.7-1.8; `[PROV]` em `params.RELEVANT_SKILL`)."""
    return params.RELEVANT_SKILL[PositionKind(kind)]


def current_job(player_id: int) -> Optional[Position]:
    """O emprego contratado do jogador (qualquer cargo que não seja Dono), ou None."""
    return (Position.objects.filter(holder_id=player_id, status=PositionStatus.FILLED.value)
            .exclude(kind=PositionKind.OWNER.value).select_related("company").first())


def _lock(player_ids: Sequence[int], company_id: Optional[int] = None, position_id: Optional[int] = None) -> None:
    for pid in sorted(set(player_ids)):
        Player.objects.select_for_update().filter(pk=pid).first()
    if company_id is not None:
        Company.objects.select_for_update().filter(pk=company_id).first()
    if position_id is not None:
        Position.objects.select_for_update().filter(pk=position_id).first()


def _event(position: Position, event_kind: EventKind, now: int, *, player_id: Optional[int] = None, actor_id: Optional[int] = None,
           **explained) -> None:
    PositionEvent.objects.create(company_id=position.company_id, position=position, kind=event_kind.value, subject=player_id,
                                 actor=actor_id, at=now, explained=explained)


def _requirements_problem(requirements: Any) -> Optional[ActionResult]:
    if not isinstance(requirements, dict):
        return _refuse("INVALID_REQUIREMENTS", why="requirements deve ser um mapeamento skill -> nível mínimo")
    allowed = {s.value for s in Skill}
    for key, level in requirements.items():
        if key not in allowed:
            return _refuse("INVALID_REQUIREMENTS", skill=repr(key)[:40], allowed=sorted(allowed))
        if not _is_int(level) or not 0 <= level <= MAX_REQUIREMENT_LEVEL:
            return _refuse("INVALID_REQUIREMENTS", skill=key, level=repr(level)[:40], max=MAX_REQUIREMENT_LEVEL)
    return None


def _check_requirements(player_id: int, requirements: Dict[str, int]):
    if not requirements:
        return skill_rules.RequirementCheck(True, ())
    return skill_rules.check_requirements(get_levels(player_id), skill_rules.SkillRequirement.of(requirements))


# --- abrir e fechar vaga ------------------------------------------------------------------------------------------------

def open_position_refusal(player_id: int, company_id: Any, kind: Any, salary: Any, requirements: Any) -> Optional[ActionResult]:
    """Recusas que só LEEM (a execução usa as mesmas)."""
    if not _id_ok(company_id):
        return _refuse("INVALID_PARAMS", company=repr(company_id)[:40])
    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return _refuse("COMPANY_NOT_FOUND", company=company_id)
    if owner_of(company_id) != player_id:
        return _refuse("NOT_OWNER", company=company_id)
    try:
        position_kind = PositionKind(kind)
    except ValueError:
        position_kind = None
    allowed = params.HIRABLE_KINDS[CompanyType(company.type)]
    if position_kind is None or position_kind is PositionKind.OWNER:
        return _refuse("INVALID_POSITION_KIND", kind=repr(kind)[:40], allowed=sorted(k.value for k in allowed))
    if position_kind not in allowed:
        return _refuse("POSITION_KIND_NOT_ALLOWED", kind=position_kind.value, company_type=company.type,
                       allowed=sorted(k.value for k in allowed))
    if not _is_int(salary) or not 0 < salary <= MAX_SALARY_CENTS:
        return _refuse("INVALID_SALARY", salary=repr(salary)[:40], max=MAX_SALARY_CENTS)
    if position_kind.value in SUPPORT_POSITION_KINDS:
        limit = params.SUPPORT_LIMIT_PER_STAR[company.stars]
        have = Position.objects.filter(company_id=company_id, kind=position_kind.value).exclude(status=PositionStatus.CLOSED.value).count()
        if have >= limit:
            return _refuse("SUPPORT_LIMIT_REACHED", kind=position_kind.value, stars=company.stars, limit=limit, have=have)
    return _requirements_problem(requirements)


def open_position(player_id: int, company_id: Any, kind: Any, salary: Any, requirements: Any = None) -> ActionResult:
    """
    O Dono abre uma vaga no mural público (02 §15). `salary` (centavos) é o valor devido por ação de Trabalhar do ocupante; o teto
    real é S/T no pagamento. `requirements` = {skill: nível mínimo} (01 §1.9; vazio = sem requisito).
    Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS, COMPANY_NOT_FOUND, NOT_OWNER, INVALID_POSITION_KIND, POSITION_KIND_NOT_ALLOWED,
    INVALID_SALARY, SUPPORT_LIMIT_REACHED (Engenheiros/Advogados abertos ou ocupados já no limite da estrela, 02 §9), INVALID_REQUIREMENTS.
    """
    requirements = {} if requirements is None else requirements
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    with transaction.atomic():
        _lock([player_id], company_id if _id_ok(company_id) else None)
        refusal = open_position_refusal(player_id, company_id, kind, salary, requirements)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        position = Position.objects.create(company_id=company_id, kind=PositionKind(kind).value, salary=salary,
                                           status=PositionStatus.OPEN.value, requirements=dict(requirements), created_at=now)
        _event(position, EventKind.POSITION_OPENED, now, actor_id=player_id, kind=position.kind, salary=salary,
               requirements=dict(requirements))
        return ActionResult(True, "OK", {"position": position.pk, "company": company_id, "kind": position.kind,
                                         "salary": salary, "requirements": dict(requirements),
                                         "relevant_skill": relevant_skill(position.kind).value})


def _position_for_owner(player_id: int, position_id: Any) -> Any:
    if not _id_ok(position_id):
        return None, _refuse("INVALID_PARAMS", position=repr(position_id)[:40])
    position = Position.objects.filter(pk=position_id).first()
    if position is None:
        return None, _refuse("POSITION_NOT_FOUND", position=position_id)
    if owner_of(position.company_id) != player_id:
        return None, _refuse("NOT_OWNER", company=position.company_id)
    return position, None


def close_position_refusal(player_id: int, position_id: Any) -> Optional[ActionResult]:
    position, refusal = _position_for_owner(player_id, position_id)
    if refusal is not None:
        return refusal
    if position.status != PositionStatus.OPEN.value:
        return _refuse("POSITION_NOT_OPEN", position=position.pk, status=position.status)
    return None


def close_position(player_id: int, position_id: Any) -> ActionResult:
    """O Dono fecha uma vaga ABERTA: sai do mural e as candidaturas pendentes são canceladas (nada some sem registro)."""
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    company_id = Position.objects.filter(pk=position_id).values_list("company_id", flat=True).first() if _id_ok(position_id) else None
    with transaction.atomic():
        _lock([player_id], company_id, position_id if company_id is not None else None)
        refusal = close_position_refusal(player_id, position_id)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        position = Position.objects.get(pk=position_id)
        pending = list(Application.objects.select_for_update().filter(
            position=position, status=ApplicationStatus.PENDING.value).order_by("id"))
        for application in pending:
            _cancel(application, "position_closed", now, position, with_event=True)
        position.status = PositionStatus.CLOSED.value
        position.closed_at = now
        position.save(update_fields=["status", "closed_at"])
        _event(position, EventKind.POSITION_CLOSED, now, actor_id=player_id, cancelled_applications=len(pending))
        return ActionResult(True, "OK", {"position": position.pk, "cancelled_applications": len(pending)})


def _cancel(application: Application, reason: str, now: int, position: Position, *, with_event: bool) -> None:
    application.status = ApplicationStatus.CANCELLED.value
    application.reason = reason
    application.decided_at = now
    application.save(update_fields=["status", "reason", "decided_at"])
    if with_event:
        _event(position, EventKind.CANCELLED, now, player_id=application.applicant_id, reason=reason,
               application=application.pk)


# --- candidatura --------------------------------------------------------------------------------------------------------

def apply_refusal(player_id: int, position_id: Any) -> Optional[ActionResult]:
    """Recusas que só LEEM: vaga existe e está aberta, requisitos de skill (01 §1.9) e candidatura repetida."""
    if not _id_ok(position_id):
        return _refuse("INVALID_PARAMS", position=repr(position_id)[:40])
    position = Position.objects.filter(pk=position_id).first()
    if position is None:
        return _refuse("POSITION_NOT_FOUND", position=position_id)
    if position.status != PositionStatus.OPEN.value:
        return _refuse("POSITION_NOT_OPEN", position=position.pk, status=position.status)
    if Application.objects.filter(position=position, applicant_id=player_id,
                                  status=ApplicationStatus.PENDING.value).exists():
        return _refuse("ALREADY_APPLIED", position=position.pk)
    check = _check_requirements(player_id, position.requirements)
    if not check.met:
        return _refuse("REQUIREMENTS_NOT_MET", position=position.pk, requirements=check.to_dict())
    return None


def apply_to_position(player_id: int, position_id: Any) -> ActionResult:
    """
    Candidatura a uma vaga do mural (02 §15). Quem já tem emprego PODE se candidatar (para trocar); a regra de um emprego é
    aplicada na aprovação. Recusas: PLAYER_NOT_FOUND, INVALID_PARAMS, POSITION_NOT_FOUND, POSITION_NOT_OPEN, ALREADY_APPLIED,
    REQUIREMENTS_NOT_MET (com o detalhamento do que falta).
    """
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    company_id = Position.objects.filter(pk=position_id).values_list("company_id", flat=True).first() if _id_ok(position_id) else None
    with transaction.atomic():
        _lock([player_id], company_id, position_id if company_id is not None else None)
        refusal = apply_refusal(player_id, position_id)
        if refusal is not None:
            return refusal
        now = game_clock.now()
        position = Position.objects.get(pk=position_id)
        check = _check_requirements(player_id, position.requirements)
        application = Application.objects.create(
            position=position, applicant_id=player_id, created_at=now,
            explained={"requirements": check.to_dict(), "kind": position.kind, "salary": position.salary})
        _event(position, EventKind.APPLIED, now, player_id=player_id, actor_id=player_id, application=application.pk)
        return ActionResult(True, "OK", {"application": application.pk, "position": position.pk,
                                         "requirements": check.to_dict()})


def _application_for(player_id: int, application_id: Any, *, as_owner: bool) -> Any:
    if not _id_ok(application_id):
        return None, _refuse("INVALID_PARAMS", application=repr(application_id)[:40])
    application = Application.objects.select_related("position").filter(pk=application_id).first()
    if application is None:
        return None, _refuse("APPLICATION_NOT_FOUND", application=application_id)
    if as_owner:
        if owner_of(application.position.company_id) != player_id:
            return None, _refuse("NOT_OWNER", company=application.position.company_id)
    elif application.applicant_id != player_id:
        return None, _refuse("NOT_APPLICANT", application=application_id)
    if application.status != ApplicationStatus.PENDING.value:
        return None, _refuse("APPLICATION_NOT_PENDING", application=application_id, status=application.status)
    return application, None


def withdraw_refusal(player_id: int, application_id: Any) -> Optional[ActionResult]:
    return _application_for(player_id, application_id, as_owner=False)[1]


def reject_refusal(player_id: int, application_id: Any) -> Optional[ActionResult]:
    return _application_for(player_id, application_id, as_owner=True)[1]


def approve_refusal(player_id: int, application_id: Any) -> Optional[ActionResult]:
    """Só o Dono aprova (GD 2026-10-19). Reavalia o que pode ter mudado desde a candidatura: vaga aberta, emprego e requisitos."""
    application, refusal = _application_for(player_id, application_id, as_owner=True)
    if refusal is not None:
        return refusal
    position = application.position
    if position.status != PositionStatus.OPEN.value:
        return _refuse("POSITION_NOT_OPEN", position=position.pk, status=position.status)
    job = current_job(application.applicant_id)
    if job is not None:
        return _refuse("ALREADY_EMPLOYED", applicant=application.applicant_id, position=job.pk, company=job.company_id)
    check = _check_requirements(application.applicant_id, position.requirements)
    if not check.met:
        return _refuse("REQUIREMENTS_NOT_MET", position=position.pk, requirements=check.to_dict())
    return None


def _decide(player_id: int, application_id: Any, refusal_fn, apply_fn) -> ActionResult:
    """Núcleo comum de retirar/rejeitar/aprovar: trava na ordem do protocolo e revalida depois dos travamentos."""
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    probe = Application.objects.select_related("position").filter(pk=application_id).first() if _id_ok(application_id) else None
    players = [player_id] + ([probe.applicant_id] if probe is not None else [])
    with transaction.atomic():
        _lock(players, probe.position.company_id if probe else None, probe.position_id if probe else None)
        if probe is not None:
            Application.objects.select_for_update().filter(pk=probe.pk).first()
        refusal = refusal_fn(player_id, application_id)
        if refusal is not None:
            return refusal
        application = Application.objects.select_related("position").get(pk=application_id)
        return apply_fn(player_id, application, game_clock.now())


def withdraw_application(player_id: int, application_id: Any) -> ActionResult:
    """O candidato desiste de uma candidatura pendente."""
    def go(pid, application, now):
        application.status = ApplicationStatus.WITHDRAWN.value
        application.decided_at = now
        application.decided_by_id = pid
        application.save(update_fields=["status", "decided_at", "decided_by"])
        _event(application.position, EventKind.WITHDRAWN, now, player_id=pid, actor_id=pid, application=application.pk)
        return ActionResult(True, "OK", {"application": application.pk, "status": application.status})
    return _decide(player_id, application_id, withdraw_refusal, go)


def reject_application(player_id: int, application_id: Any) -> ActionResult:
    """O Dono rejeita uma candidatura pendente."""
    def go(pid, application, now):
        application.status = ApplicationStatus.REJECTED.value
        application.decided_at = now
        application.decided_by_id = pid
        application.save(update_fields=["status", "decided_at", "decided_by"])
        _event(application.position, EventKind.REJECTED, now, player_id=application.applicant_id, actor_id=pid,
               application=application.pk)
        return ActionResult(True, "OK", {"application": application.pk, "status": application.status})
    return _decide(player_id, application_id, reject_refusal, go)


def approve_application(player_id: int, application_id: Any) -> ActionResult:
    """
    O Dono aprova: o candidato passa a ocupar o cargo (02 §15). As demais candidaturas à vaga e as outras candidaturas pendentes
    do contratado são canceladas (a vaga foi preenchida / o jogador já tem emprego). Recusas: ver `approve_refusal`.
    """
    def go(pid, application, now):
        position = application.position
        position.holder_id = application.applicant_id
        position.status = PositionStatus.FILLED.value
        position.hired_at = now
        position.save(update_fields=["holder", "status", "hired_at"])
        application.status = ApplicationStatus.APPROVED.value
        application.decided_at = now
        application.decided_by_id = pid
        application.save(update_fields=["status", "decided_at", "decided_by"])
        for other in Application.objects.select_for_update().filter(
                position=position, status=ApplicationStatus.PENDING.value).order_by("id"):
            _cancel(other, "position_filled", now, position, with_event=True)
        Application.objects.filter(applicant_id=application.applicant_id, status=ApplicationStatus.PENDING.value).update(
            status=ApplicationStatus.CANCELLED.value, reason="hired_elsewhere", decided_at=now)
        _event(position, EventKind.HIRED, now, player_id=application.applicant_id, actor_id=pid, application=application.pk,
               salary=position.salary)
        return ActionResult(True, "OK", {"application": application.pk, "position": position.pk,
                                         "company": position.company_id, "kind": position.kind, "salary": position.salary,
                                         "employee": application.applicant_id})
    return _decide(player_id, application_id, approve_refusal, go)


# --- sair do emprego ----------------------------------------------------------------------------------------------------

def resign_refusal(player_id: int) -> Optional[ActionResult]:
    return None if current_job(player_id) is not None else _refuse("NOT_EMPLOYED")


def _leave(position: Position, kind: EventKind, now: int, actor_id: int, employee_id: int) -> None:
    position.holder_id = None
    position.status = PositionStatus.CLOSED.value
    position.closed_at = now
    position.save(update_fields=["holder", "status", "closed_at"])
    _event(position, kind, now, player_id=employee_id, actor_id=actor_id, salary=position.salary)


def resign(player_id: int) -> ActionResult:
    """
    O funcionário pede demissão do seu emprego. A vaga é ENCERRADA (o Dono abre outra se quiser); salários já devidos continuam
    obrigações da empresa até serem pagos (24 §24.9) e não são apagados.
    """
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    probe = current_job(player_id)
    with transaction.atomic():
        _lock([player_id], probe.company_id if probe else None, probe.pk if probe else None)
        refusal = resign_refusal(player_id)
        if refusal is not None:
            return refusal
        position = current_job(player_id)
        _leave(position, EventKind.RESIGNED, game_clock.now(), player_id, player_id)
        return ActionResult(True, "OK", {"position": position.pk, "company": position.company_id})


def dismiss_refusal(player_id: int, position_id: Any) -> Optional[ActionResult]:
    position, refusal = _position_for_owner(player_id, position_id)
    if refusal is not None:
        return refusal
    if position.kind == PositionKind.OWNER.value:
        return _refuse("CANNOT_DISMISS_OWNER", position=position.pk)
    if position.status != PositionStatus.FILLED.value:
        return _refuse("POSITION_NOT_FILLED", position=position.pk, status=position.status)
    return None


def dismiss(player_id: int, position_id: Any) -> ActionResult:
    """O Dono demite o ocupante de um cargo (nunca o próprio cargo Dono). A vaga é encerrada; salários devidos permanecem."""
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    probe = Position.objects.filter(pk=position_id).first() if _id_ok(position_id) else None
    with transaction.atomic():
        _lock([player_id] + ([probe.holder_id] if probe is not None and probe.holder_id else []),
              probe.company_id if probe else None, probe.pk if probe else None)
        refusal = dismiss_refusal(player_id, position_id)
        if refusal is not None:
            return refusal
        position = Position.objects.get(pk=position_id)
        employee = position.holder_id
        if probe is not None and probe.holder_id != employee:         # o ocupante mudou entre a leitura e o travamento
            return _refuse("POSITION_CHANGED", position=position.pk)
        _leave(position, EventKind.DISMISSED, game_clock.now(), player_id, employee)
        return ActionResult(True, "OK", {"position": position.pk, "employee": employee, "company": position.company_id})


# --- leituras públicas --------------------------------------------------------------------------------------------------

def mural(viewer_id: Optional[int] = None, *, company_id: Optional[int] = None, kind: Optional[str] = None,
          after: int = 0, limit: int = MURAL_PAGE_LIMIT) -> List[Dict[str, Any]]:
    """
    Mural PÚBLICO de vagas abertas (02 §15), em ordem de abertura, paginado por `after` (id da última vaga vista). Com `viewer_id`,
    cada vaga traz `requirements_met` e o detalhamento do que falta (20); sem observador esses campos são None (desconhecido, não
    "não atende"). Só mostra o que um jogador comum veria.
    """
    limit = max(1, min(int(limit), MURAL_PAGE_LIMIT))
    qs = Position.objects.filter(status=PositionStatus.OPEN.value, id__gt=after).select_related("company").order_by("id")
    if company_id is not None:
        qs = qs.filter(company_id=company_id)
    if kind is not None:
        qs = qs.filter(kind=kind)
    levels = get_levels(viewer_id) if viewer_id is not None else None
    applied = (set(Application.objects.filter(applicant_id=viewer_id, status=ApplicationStatus.PENDING.value)
                   .values_list("position_id", flat=True)) if viewer_id is not None else None)
    rows: List[Dict[str, Any]] = []
    for p in qs[:limit]:
        met = details = None
        if levels is not None:
            check = (skill_rules.check_requirements(levels, skill_rules.SkillRequirement.of(p.requirements))
                     if p.requirements else skill_rules.RequirementCheck(True, ()))
            met, details = check.met, check.to_dict()
        rows.append({"position": p.pk, "company": p.company_id, "company_name": p.company.name, "company_type": p.company.type,
                     "stars": p.company.stars, "kind": p.kind, "salary": p.salary, "relevant_skill": relevant_skill(p.kind).value,
                     "requirements": dict(p.requirements), "requirements_met": met, "requirements_detail": details,
                     "applied": None if applied is None else p.pk in applied, "opened_at": p.created_at})
    return rows


def pending_applications(player_id: int, company_id: int) -> List[Dict[str, Any]]:
    """Candidaturas pendentes de uma empresa, só para o Dono (quem decide as vê)."""
    if owner_of(company_id) != player_id:
        return []
    qs = Application.objects.filter(position__company_id=company_id, status=ApplicationStatus.PENDING.value) \
        .select_related("position").order_by("id")
    return [{"application": a.pk, "position": a.position_id, "kind": a.position.kind, "applicant": a.applicant_id,
             "created_at": a.created_at, "requirements": a.explained.get("requirements")} for a in qs]
