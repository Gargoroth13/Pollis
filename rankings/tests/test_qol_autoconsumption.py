"""
Integração Rankings (snapshots de QoL) × Auto-consumo (design/04 §16): a existência do ranking não pode mudar o jogo
(design/14 §14.11). Os checkpoints do catch-up e a varredura da snapshot dividem só os CICLOS; o hook de acesso do
auto-consumo roda uma única vez, no acesso real. Dois jogadores idênticos, um levado com checkpoint e varredura, outro sem.
"""
from decimal import Decimal

from inventory.models import InventoryMovement
from players import hooks as player_hooks
from players.models import Player
from players.services import sync_player
from rankings import qol_snapshots as snaps

from inventory.tests.test_auto_consumption import AutoTestCase

D = Decimal
HOUR = 3600


class QolSnapshotsDoNotChangeAutoConsumptionTests(AutoTestCase):
    def _state(self, pl):
        pl = Player.objects.get(pk=pl.pk)
        return {"nutrition": pl.nutrition, "health": pl.health, "energy": pl.energy, "hospitalized_until": pl.hospitalized_until,
                "juice": self.qty(pl, "juice"),
                "auto_moves": InventoryMovement.objects.filter(player=pl, reference_kind="auto_consumption").count()}

    def _run(self, hours):
        a, b = self.player, self.other                                   # a: sem ranking; b: com snapshots abertas e finalizadas
        for p in (a, b):
            self.set_state(p, nutrition=D(12), energy=D(100))
            self.give(p, "juice", 40)
            self.enable(None, p)
        t0 = self.clk.now()
        snaps.ensure_open(t0)
        self.clk.advance(hours=hours)
        now = self.clk.now()
        refs = list(range(snaps.next_reference_after(t0), now + 1, HOUR))
        saved = player_hooks._checkpoints.pop(snaps.CHECKPOINT_NAME)     # A: o ranking não participa do catch-up
        try:
            sync_player(a.pk)
        finally:
            player_hooks._checkpoints[snaps.CHECKPOINT_NAME] = saved
        for ref in refs:
            snaps._open(ref, now)
        for ref in refs:
            snaps.finalize(ref, now)                                     # B: varredura e checkpoints do ranking
        sync_player(b.pk)
        return self._state(a), self._state(b), refs

    def _assert_neutral(self, hours):
        without, with_ranking, refs = self._run(hours)
        self.assertTrue(refs)
        self.assertEqual(without, with_ranking)
        self.assertEqual(with_ranking["auto_moves"], 2)                  # o auto-consumo agiu uma vez (Nutrição < 10), não a cada checkpoint

    def test_same_outcome_with_and_without_the_ranking_checkpoints_6h(self):
        self._assert_neutral(6)

    def test_same_outcome_with_and_without_the_ranking_checkpoints_20h(self):
        self._assert_neutral(20)
