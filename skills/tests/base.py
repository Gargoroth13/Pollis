from decimal import Decimal

from core.breakdown import Calc
from players import services as player_services
from players.actions import Action
from players.tests.base import CYCLE, HOUR, T0, PlayerTestCase  # noqa: F401
from skills import curves, services
from skills.constants import Skill
from skills.models import PlayerSkill

D = Decimal
INT, PHY, CHA = Skill.INTELLIGENCE, Skill.PHYSICAL, Skill.CHARISMA


class SkillTestCase(PlayerTestCase):
    """PlayerTestCase (relógio manual em T0 + jogador) com limpeza dos pontos de extensão de Skills."""

    def setUp(self):
        super().setUp()
        self.addCleanup(services.clear_initial_level_providers)
        for name in ("test_curve", "test_dr", "test_prod"):
            self.addCleanup(curves.unregister_progress_curve, name)
            self.addCleanup(curves.unregister_production_curve, name)

    def levels(self, player=None):
        return services.get_levels((player or self.player).pk)

    def act(self, action, player=None, **kw):
        """Faz uma ação com Energia cheia (para os testes de skill não esbarrarem no custo de energia)."""
        p = player or self.player
        self.set_state(p, energy=100)
        return player_services.perform_action(p.pk, action, **kw)

    def set_level(self, skill, level, player=None):
        PlayerSkill.objects.filter(player=player or self.player, skill=skill.value).update(level=level)

    def qol(self, value):
        return Calc("baseline", value).result()
