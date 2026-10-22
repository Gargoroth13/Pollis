from core import ticks
from core.models import WorldClock
from geography.models import Neighborhood
from players.tests.base import T0, PlayerTestCase
from schools import services
from schools.audit import audit_schools
from schools.constants import SchoolKind
from schools.models import School


class SchoolBase(PlayerTestCase):
    """Mundo pequeno, relógio manual em T0 e jogador p1; ao fim de TODO teste as escolas estão íntegras."""

    audit_schools_at_end = True

    def setUp(self):
        super().setUp()
        WorldClock.load()
        WorldClock.objects.filter(pk=1).update(anchor_game=T0, world_processed_until=T0)
        self.addCleanup(self._audit_schools)
        self.addCleanup(services.unregister_residence_provider, "test_residences")
        self.home = School.objects.get(initial=True)          # a do bairro de origem do p1 (criada pela matrícula inicial)
        self.nb = self.home.neighborhood_id

    def _audit_schools(self):
        if self.audit_schools_at_end:
            report = audit_schools()
            self.assertTrue(report.ok, report.findings)

    def make_school(self, kind=SchoolKind.PUBLIC, neighborhood=None, owner=None, name="Escola", stars=None):
        res = services.create_school(neighborhood_id=neighborhood or self.nb, kind=kind, name=name, stars=stars,
                                     owner_id=None if kind is SchoolKind.PUBLIC else (owner or self.player).pk)
        self.assertTrue(res.ok, res)
        return School.objects.get(pk=res.detail["school"])

    def other_neighborhood(self):
        return Neighborhood.objects.exclude(pk=self.nb).order_by("id").first().pk

    def assertRefused(self, res, code, **detail):
        self.assertEqual((res.ok, res.code), (False, code), (res.code, res.detail))
        for k, v in detail.items():
            self.assertEqual(res.detail.get(k), v, (k, res.detail))

    def provide_residences(self, n):
        services.unregister_residence_provider("test_residences")
        services.register_residence_provider("test_residences", lambda neighborhood_id: n)

    def midnight_tick(self, day_offset=1):
        """Leva o relógio à virada do dia `day_offset` depois do de T0 (00:05) e roda os ticks do mundo."""
        from ledger.money import competence_day_of
        from market.rollup import day_bounds
        self.clk.set(day_bounds(competence_day_of(T0) + day_offset)[0] + 300)
        return ticks.advance_world()
