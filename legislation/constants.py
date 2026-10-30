"""Enumerações do processo legislativo (design/07)."""
from enum import Enum


class Kind(str, Enum):
    CHANGE = "change"            # cria ou altera a lei: parâmetros X novos (07 §07.4, §07.21)
    REVOKE = "revoke"            # revoga uma lei em vigor (07 §07.22)


class Status(str, Enum):
    DISCUSSION = "discussion"                # 07.5: pública; o autor edita e retira
    VOTING = "voting"                        # 07.8: Câmara vota; congelada
    SANCTION = "sanction"                    # 07.12: aguarda sanção ou veto (3 dias; inação = sanção)
    VETOED = "vetoed"                        # 07.15: veto aguarda a janela semanal para a Câmara tentar derrubá-lo
    OVERRIDE_VOTING = "override_voting"      # 07.15: votação de derrubada (2/3)
    AWAITING_FORCE = "awaiting_force"        # 07.16: "aprovada aguardando vigor" até o próximo weekly tick
    ENACTED = "enacted"                      # entrou em vigor (alteração ou revogação aplicada)
    REJECTED = "rejected"                    # 07.10/07.11
    VETO_SUSTAINED = "veto_sustained"        # 07.15: Câmara não alcançou 2/3
    WITHDRAWN = "withdrawn"                  # 07.5


ACTIVE = frozenset({Status.DISCUSSION, Status.VOTING, Status.SANCTION, Status.VETOED, Status.OVERRIDE_VOTING, Status.AWAITING_FORCE})
TERMINAL = frozenset(set(Status) - ACTIVE)
OPEN_VOTE = frozenset({Status.VOTING, Status.OVERRIDE_VOTING})


class RoundKind(str, Enum):
    MAIN = "main"
    OVERRIDE = "override"


class RoundStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    VOIDED = "voided"            # 07.18/07.19: nova Câmara/novo Presidente; a votação anterior NÃO é aproveitada (fica no histórico)


class Choice(str, Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


class EventKind(str, Enum):
    CREATED = "created"
    EDITED = "edited"
    WITHDRAWN = "withdrawn"
    VOTE_OPENED = "vote_opened"
    VOTE_CLOSED = "vote_closed"
    VOTE_VOIDED = "vote_voided"
    SANCTIONED = "sanctioned"
    AUTO_SANCTIONED = "auto_sanctioned"
    VETOED = "vetoed"
    OVERRIDE_OPENED = "override_opened"
    OVERRIDE_CLOSED = "override_closed"
    RETURNED_TO_VOTE = "returned_to_vote"
    IN_FORCE = "in_force"
    DEADLINES_SHIFTED = "deadlines_shifted"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    ADOPTED = "adopted"
    DISMISSED = "dismissed"


class LawStatus(str, Enum):
    IN_FORCE = "in_force"
    REVOKED = "revoked"
