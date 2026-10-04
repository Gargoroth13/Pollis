import math
from decimal import Decimal as D
from types import SimpleNamespace as P

from django.test import SimpleTestCase, TestCase, override_settings

from geography import services, spatial
from geography.models import City, Lot

from .base import GeoTestCase


class DistanceTests(SimpleTestCase):
    def test_euclidean_is_derived_from_coordinates(self):
        self.assertEqual(spatial.distance(P(x=D(0), y=D(0)), P(x=D(3), y=D(4))), D(5))

    def test_manhattan_alternative(self):
        self.assertEqual(spatial.distance(P(x=D(0), y=D(0)), P(x=D(3), y=D(4)), "manhattan"), D(7))

    def test_symmetric_and_zero_for_the_same_place(self):
        a, b = P(x=D("1.5"), y=D("-2")), P(x=D("-4"), y=D("0.25"))
        self.assertEqual(spatial.distance(a, b), spatial.distance(b, a))
        self.assertEqual(spatial.distance(a, a), 0)

    def test_triangle_inequality(self):
        a, b, c = P(x=D(0), y=D(0)), P(x=D(5), y=D(1)), P(x=D(2), y=D(7))
        self.assertLessEqual(spatial.distance(a, c), spatial.distance(a, b) + spatial.distance(b, c))

    def test_unknown_metric_rejected(self):
        with self.assertRaises(ValueError):
            spatial.distance(P(x=D(0), y=D(0)), P(x=D(1), y=D(1)), "chebyshev")

    def test_is_exact_decimal_so_it_is_deterministic(self):
        self.assertEqual(spatial.distance(P(x=D(0), y=D(0)), P(x=D(1), y=D(1))), D(2).sqrt())


class LayoutTests(SimpleTestCase):
    def test_neighborhoods_are_concentrated_around_the_center_not_a_uniform_grid(self):
        """08 §3.1: distribuição concentrada, semelhante à gaussiana/espiral."""
        radius = D("1.5")
        pts = spatial.neighborhood_offsets(25, radius)
        radii = sorted(math.hypot(float(x), float(y)) for x, y in pts)
        self.assertEqual(len(set(pts)), 25)                            # nenhum bairro sobre outro
        self.assertAlmostEqual(radii[-1], float(radius), places=2)     # o mais externo está no raio da cidade
        uniform_median = float(radius) / math.sqrt(2)                  # mediana de um disco uniforme
        self.assertLess(radii[12], 0.7 * uniform_median)               # a metade interna é bem mais central
        self.assertLess(radii[0], 0.2)                                 # há bairro bem no centro

    def test_a_single_neighborhood_sits_at_the_center(self):
        self.assertEqual(spatial.neighborhood_offsets(1, D(3)), [(D(0), D(0))])

    def test_layout_has_no_randomness(self):
        self.assertEqual(spatial.neighborhood_offsets(25, D(2)), spatial.neighborhood_offsets(25, D(2)))

    def test_spiral_starts_at_the_origin_and_never_overlaps(self):
        pts = spatial.spiral_offsets(40, D(6))
        self.assertEqual(pts[0], (D(0), D(0)))
        self.assertEqual(len(set(pts)), 40)

    def test_lot_grid_is_centered_with_exact_spacing(self):
        pts = spatial.lot_offsets(9, D("0.01"))
        self.assertEqual(len(set(pts)), 9)
        self.assertEqual(pts[4], (D(0), D(0)))                          # centro da grade 3x3
        self.assertEqual(pts[1][0] - pts[0][0], D("0.01"))
        self.assertEqual(spatial.lot_offsets(0, D("0.01")), [])

    def test_lot_grid_for_non_square_counts(self):
        for n in (1, 2, 5, 10, 50):
            self.assertEqual(len(set(spatial.lot_offsets(n, D("0.01")))), n)


class DistanceBetweenPlacesTests(GeoTestCase):
    def test_distance_between_real_places_comes_from_their_coordinates(self):
        self.world()
        a, b = City.objects.order_by("index")
        self.assertEqual(services.distance_between(a, b), spatial.distance(a, b))
        self.assertGreater(services.distance_between(a, b), 0)

    def test_it_works_across_levels(self):
        """Estado, cidade, bairro e lote são todos localizáveis pela mesma regra."""
        self.world()
        lot = Lot.objects.first()
        city = lot.neighborhood.city
        self.assertGreaterEqual(services.distance_between(lot, city), 0)

    @override_settings(POLIS_GEOGRAPHY={"distance_metric": "manhattan"})
    def test_metric_comes_from_the_scenario(self):
        self.world()
        a, b = City.objects.order_by("index")
        self.assertEqual(services.distance_between(a, b), abs(a.x - b.x) + abs(a.y - b.y))
