from bots import population
from bots.models import Bot
from ledger.audit import audit_ledger
from players.tests.base import PlayerTestCase


class BotsBase(PlayerTestCase):
    """Mundo pequeno e relógio manual; Bots são contas de jogador normais."""

    audit_at_end = True

    def setUp(self):
        super().setUp()
        self.run_ = population.start_run("teste", target_population=20, creation_interval_real_seconds=60, global_seed=7)
        self.addCleanup(self._audit)

    def _audit(self):
        if self.audit_at_end:
            report = audit_ledger()
            self.assertTrue(report.ok, report.findings)

    def make_bot(self, **profile):
        return population.create_bot(self.run_, profile or None)

    def fresh(self, bot):
        return Bot.objects.get(pk=bot.pk)

    def go(self, seconds):
        self.clk.set(self.clk.now() + seconds)
