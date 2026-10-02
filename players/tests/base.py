from decimal import Decimal

from django.test import TestCase

from accounts.models import Usuario
from core.clock import ManualClock, use_clock
from core.timeline import game_ts
from players import qol, rules
from players.models import Player
from players.services import create_player, get_snapshot, sync_player

# 12:00 em São Paulo = 15:00 UTC: exatamente numa fronteira de ciclo de 10 minutos.
T0 = game_ts(2026, 10, 5, 12)
D = Decimal
CYCLE = 600  # 10 minutos de jogo, em segundos
HOUR = 3600


class PlayerTestCase(TestCase):
    """Relógio manual no instante T0 e um jogador recém-criado."""

    def setUp(self):
        self.clk = ManualClock(T0)
        cm = use_clock(self.clk)
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.addCleanup(qol.clear_qol_base_providers)
        self.addCleanup(rules.clear_regional_recovery_providers)
        self.player = self.new_player("p1")

    def new_player(self, name):
        return create_player(Usuario.objects.create_user(name))

    def state(self, player=None):
        return sync_player((player or self.player).pk)

    def snap(self, player=None):
        return get_snapshot((player or self.player).pk)

    def set_state(self, player=None, **fields):
        Player.objects.filter(pk=(player or self.player).pk).update(**fields)

    def neutral_qol(self, target="1"):
        """Registra um provedor estrutural que leva a QoL Base ao valor `target` (padrão 1,00 = neutro)."""
        qol.register_qol_base_provider("test_structural", lambda p, a: D(target) - D("0.5"))
