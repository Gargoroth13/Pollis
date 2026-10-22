"""
Escolas (design/03 §2-§6): escola pública de cada bairro, matrícula inicial, troca de escola e capacidade.

PROTOCOLO de travamento: jogador → escolas em ordem crescente de id. A matrícula inicial (dentro da criação do jogador) não trava
escola nenhuma: não aplica limite de vagas (ver abaixo), então não há corrida a serializar.

Capacidade (03 §4): vagas = residências possíveis no bairro × 1,5. As residências vêm do sistema de Imóveis (P1.07, `10` §6.1), que
registra um provedor aqui; sem provedor a capacidade é DESCONHECIDA (`None`, "Sem dados"), nunca 0 nem ilimitada, e a troca de escola não
a aplica. A matrícula INICIAL nunca é recusada por falta de vaga: o design não define lotação para quem acaba de nascer (03 §28, "regras
de lotação") e a moradia inicial do jogador não consome capacidade (GD 2026-10-07; `10` §7). Registrado em `design/03a`.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from django.db import IntegrityError, transaction

from core import clock as game_clock
from core.breakdown import Calc, Explained
from geography.models import Neighborhood
from players.models import Player
from players.services import ActionResult
from travel.models import PlayerLocation

from . import params
from .constants import MAX_NAME, MAX_STARS, MIN_STARS, EnrollmentEnd, SchoolKind
from .models import Enrollment, School

CREATED_HOOK = "travel.schools"            # depois de "travel" (ordem por nome): a localização inicial já existe

ResidenceProvider = Callable[[int], Optional[int]]
_residence_providers: Dict[str, ResidenceProvider] = {}


def _refuse(code: str, **detail) -> ActionResult:
    return ActionResult(False, code, detail)


def _is_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value < 2 ** 63


# --- capacidade ---------------------------------------------------------------------------------------------------------------

def register_residence_provider(name: str, fn: ResidenceProvider) -> None:
    """Imóveis (P1.07) informa `{bairro: número de residências possíveis}`. Mais de um provedor: somam-se (None = não sabe)."""
    if name in _residence_providers:
        raise ValueError(f"Provedor de residências duplicado: {name}")
    _residence_providers[name] = fn


def unregister_residence_provider(name: str) -> None:        # para testes
    _residence_providers.pop(name, None)


def residences_in(neighborhood_id: int) -> Optional[int]:
    known = [fn(neighborhood_id) for _, fn in sorted(_residence_providers.items())]
    known = [k for k in known if k is not None]
    return sum(known) if known else None


def seats_of(school: School) -> Optional[Explained]:
    """Vagas da escola (03 §4) com o detalhamento (20), ou None se as residências do bairro ainda são desconhecidas."""
    residences = residences_in(school.neighborhood_id)
    if residences is None:
        return None
    return Calc("neighborhood_residences", residences).mul("capacity_multiplier", params.CAPACITY_MULTIPLIER).result(game_clock.now())


def seat_count(school: School) -> Optional[int]:
    """Número inteiro de vagas (a parte inteira: não existe meia vaga)."""
    seats = seats_of(school)
    return None if seats is None else int(seats.value)


def enrolled_count(school_id: int) -> int:
    return Enrollment.objects.filter(school_id=school_id, ended_at__isnull=True).count()


def school_status(school_id: int) -> Optional[Dict[str, Any]]:
    school = School.objects.filter(pk=school_id).first()
    if school is None:
        return None
    seats = seats_of(school)
    enrolled = enrolled_count(school_id)
    return {"school": school.pk, "name": school.name, "kind": school.kind, "stars": school.stars, "neighborhood": school.neighborhood_id,
            "enrolled": enrolled, "seats": None if seats is None else int(seats.value), "seats_explained": seats,
            "free_seats": None if seats is None else int(seats.value) - enrolled,
            "over_capacity": None if seats is None else enrolled > int(seats.value)}


# --- criação de escolas -------------------------------------------------------------------------------------------------------

def _name_problem(name: Any) -> Optional[ActionResult]:
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_NAME:
        return _refuse("INVALID_NAME", max=MAX_NAME)
    return None


def create_school(*, neighborhood_id: int, kind: SchoolKind, name: str, owner_id: Optional[int] = None, stars: Optional[int] = None,
                  initial: bool = False, now: Optional[int] = None) -> ActionResult:
    """
    Cria uma escola (uso do sistema: a pública de origem do bairro e, depois, as que o governo/jogadores construírem; a fundação
    de escola particular por jogador não está definida no design — ver `design/03a`). Recusas: INVALID_PARAMS, INVALID_NAME,
    NEIGHBORHOOD_NOT_FOUND, OWNER_NOT_ALLOWED / OWNER_REQUIRED, PLAYER_NOT_FOUND, INVALID_STARS.
    """
    now = game_clock.now() if now is None else now
    stars = params.INITIAL_STARS if stars is None else stars
    if not _is_id(neighborhood_id) or not isinstance(kind, SchoolKind):
        return _refuse("INVALID_PARAMS")
    problem = _name_problem(name)
    if problem is not None:
        return problem
    if not isinstance(stars, int) or isinstance(stars, bool) or not MIN_STARS <= stars <= MAX_STARS:
        return _refuse("INVALID_STARS", stars=repr(stars)[:20], allowed=[MIN_STARS, MAX_STARS])
    if kind is SchoolKind.PUBLIC and owner_id is not None:
        return _refuse("OWNER_NOT_ALLOWED")
    if kind is SchoolKind.PRIVATE and owner_id is None:
        return _refuse("OWNER_REQUIRED")
    if owner_id is not None and not Player.objects.filter(pk=owner_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=owner_id)
    if not Neighborhood.objects.filter(pk=neighborhood_id).exists():
        return _refuse("NEIGHBORHOOD_NOT_FOUND", neighborhood=neighborhood_id)
    from . import quality
    with transaction.atomic():
        school = School.objects.create(neighborhood_id=neighborhood_id, kind=kind.value, name=name.strip(), stars=stars,
                                       owner_id=owner_id, initial=initial, created_at=now)
        quality.open_first_day(school, now)
    return ActionResult(True, "OK", {"school": school.pk, "name": school.name, "kind": school.kind, "stars": school.stars})


def ensure_public_school(neighborhood_id: int, now: Optional[int] = None) -> School:
    """
    A escola pública de origem do bairro ("normalmente haverá uma única escola por bairro", 03 §2). Existe desde o primeiro uso;
    criar a instituição não cria dinheiro nem estoque. Idempotente e seguro com concorrência (índice único parcial).
    """
    existing = School.objects.filter(neighborhood_id=neighborhood_id, initial=True).first()
    if existing is not None:
        return existing
    name = Neighborhood.objects.values_list("name", flat=True).get(pk=neighborhood_id)
    try:
        res = create_school(neighborhood_id=neighborhood_id, kind=SchoolKind.PUBLIC, name=f"Escola Pública {name}"[:MAX_NAME],
                            initial=True, now=now)
    except IntegrityError:                                   # corrida: a outra transação criou primeiro
        return School.objects.get(neighborhood_id=neighborhood_id, initial=True)
    if not res.ok:
        raise RuntimeError(f"escola pública do bairro {neighborhood_id}: {res.code} {res.detail}")
    return School.objects.get(pk=res.detail["school"])


# --- matrícula ----------------------------------------------------------------------------------------------------------------

def current_enrollment(player_id: int) -> Optional[Enrollment]:
    return Enrollment.objects.filter(player_id=player_id, ended_at__isnull=True).select_related("school").first()


def on_player_created(player: Player, now: int) -> None:
    """
    03 §2: todo jogador novo é associado, automaticamente, a uma escola do seu bairro. Só escolas PÚBLICAS são candidatas (a particular
    cobra mensalidade, 03 §6.1: ninguém é matriculado nela sem escolher). Várias públicas no bairro: a primeira (menor id) com vaga
    conhecida sobrando; sem vaga conhecida ou sem dado de capacidade, a de origem. Nunca recusa (ver módulo).
    """
    neighborhood_id = PlayerLocation.objects.filter(player_id=player.pk).values_list("lot__neighborhood_id", flat=True).first()
    if neighborhood_id is None:
        raise RuntimeError("jogador sem localização: a matrícula escolar precisa do bairro (hook 'travel' deve rodar antes)")
    origin = ensure_public_school(neighborhood_id, now)
    chosen = origin
    for school in School.objects.filter(neighborhood_id=neighborhood_id, kind=SchoolKind.PUBLIC.value).order_by("id"):
        seats = seat_count(school)
        if seats is not None and enrolled_count(school.pk) < seats:
            chosen = school
            break
    Enrollment.objects.create(player=player, school=chosen, started_at=now)


def change_refusal(player_id: Any, school_id: Any) -> Optional[ActionResult]:
    """Recusa da troca de escola (03 §2: só para outra escola do MESMO bairro). None = pode."""
    if not _is_id(player_id) or not _is_id(school_id):
        return _refuse("INVALID_PARAMS")
    if not Player.objects.filter(pk=player_id).exists():
        return _refuse("PLAYER_NOT_FOUND", player=player_id)
    target = School.objects.filter(pk=school_id).first()
    if target is None:
        return _refuse("SCHOOL_NOT_FOUND", school=school_id)
    current = current_enrollment(player_id)
    if current is None:
        return _refuse("NOT_ENROLLED")
    if current.school_id == target.pk:
        return _refuse("ALREADY_ENROLLED_HERE", school=target.pk)
    if current.school.neighborhood_id != target.neighborhood_id:
        return _refuse("SCHOOL_IN_OTHER_NEIGHBORHOOD", from_neighborhood=current.school.neighborhood_id,
                       to_neighborhood=target.neighborhood_id)
    seats = seat_count(target)
    if seats is not None and enrolled_count(target.pk) >= seats:
        return _refuse("SCHOOL_FULL", school=target.pk, seats=seats)
    return None


def change_school(player_id: Any, school_id: Any) -> ActionResult:
    """Troca de escola dentro do bairro. Tudo é revalidado sob trava (jogador → escola de destino) e o histórico é contínuo."""
    problem = change_refusal(player_id, school_id)
    if problem is not None:
        return problem
    with transaction.atomic():
        Player.objects.select_for_update().get(pk=player_id)
        target = School.objects.select_for_update().get(pk=school_id)
        problem = change_refusal(player_id, school_id)               # estado pode ter mudado até a trava
        if problem is not None:
            return problem
        now = game_clock.now()
        current = current_enrollment(player_id)
        Enrollment.objects.filter(pk=current.pk).update(ended_at=now, end_reason=EnrollmentEnd.TRANSFER.value)
        Enrollment.objects.create(player_id=player_id, school=target, started_at=now)
    return ActionResult(True, "OK", {"school": target.pk, "from_school": current.school_id, "at": now})


def register() -> None:
    from players import hooks
    hooks.register_player_created_hook(CREATED_HOOK, on_player_created)
