from django.test import TestCase

from accounts.models import Usuario
from core.clock import ManualClock, use_clock
from core.timeline import game_ts
from ledger import services as ledger
from ledger.tests.base import LedgerHelpers
from players.models import Player
from players.services import create_player
from players.tests.base import T0, PlayerTestCase  # noqa: F401
from rankings import live

HOUR = 3600
DAY = 86400


class RankingsTestCase(LedgerHelpers, PlayerTestCase):
    """PlayerTestCase (mundo pequeno, relógio manual em T0) + ledger auditado ao fim de cada teste."""

    def setUp(self):
        super().setUp()
        self.ledger_setup()
        self.addCleanup(live.clear_entity_namers)

    def acct(self, player=None):
        return ledger.player_account((player or self.player).pk)

    def make_player(self, name, created_at=None):
        p = self.new_player(name)
        if created_at is not None:
            Player.objects.filter(pk=p.pk).update(created_at_game=created_at)
            p.refresh_from_db()
        return p
