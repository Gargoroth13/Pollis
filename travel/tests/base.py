import math
from decimal import ROUND_CEILING, Decimal

from geography import services as geo
from geography.models import Lot
from players.tests.base import CYCLE, HOUR, T0, PlayerTestCase  # noqa: F401
from travel import services
from travel.models import Journey, PlayerLocation

D = Decimal


class TravelTestCase(PlayerTestCase):
    """PlayerTestCase (mundo pequeno, relógio manual, jogador) + auxiliares determinísticos de lotes e viagem."""

    def location(self, player=None):
        return PlayerLocation.objects.select_related("lot").get(player=player or self.player).lot

    def by_distance(self, origin):
        """Lotes (exceto a origem) do mais próximo ao mais distante."""
        others = list(Lot.objects.exclude(pk=origin.pk).order_by("id"))
        return sorted(others, key=lambda l: (geo.distance_between(origin, l), l.id))

    def near(self, origin=None):
        return self.by_distance(origin or self.location())[0]

    def far(self, origin=None):
        return self.by_distance(origin or self.location())[-1]

    def expected_seconds(self, a, b, minutes_per_unit=15):
        minutes = geo.distance_between(a, b) * D(minutes_per_unit)
        return max(1, int((minutes * 60).to_integral_value(rounding=ROUND_CEILING)))

    def go(self, destination, player=None):
        return services.start_travel((player or self.player).pk, destination.pk)

    def where(self, player=None):
        return services.get_location((player or self.player).pk)
