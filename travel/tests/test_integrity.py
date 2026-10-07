from django.db import IntegrityError, transaction

from geography.models import Lot
from players.models import Player
from travel.integrity import check_integrity
from travel.models import Journey, PlayerLocation

from .base import T0, TravelTestCase


class DatabaseConstraintTests(TravelTestCase):
    def test_at_most_one_active_journey_per_player(self):
        self.go(self.far())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Journey.objects.create(player=self.player, origin=self.location(), destination=self.far(), departed_at=T0, arrives_at=T0 + 9)

    def test_a_journey_cannot_start_and_end_at_the_same_lot(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Journey.objects.create(player=self.player, origin=self.location(), destination=self.location(), departed_at=T0, arrives_at=T0 + 9)

    def test_a_journey_arrives_after_it_departs(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Journey.objects.create(player=self.player, origin=self.location(), destination=self.far(), departed_at=T0, arrives_at=T0)

    def test_completed_journeys_do_not_count_as_the_active_one(self):
        self.clk.advance(seconds=self.go(self.far()).detail["duration_seconds"])
        self.where()
        self.assertTrue(self.go(self.far(self.location())).ok)


class TravelIntegrityTests(TravelTestCase):
    def codes(self):
        return check_integrity().codes

    def test_a_fresh_world_is_intact(self):
        self.new_player("other")
        r = check_integrity()
        self.assertTrue(r.ok, r.violations)
        self.assertEqual(r.stats["players"], 2)

    def test_intact_during_and_after_a_trip(self):
        self.go(self.far())
        self.assertEqual(self.codes(), [])
        self.clk.advance(days=1)
        self.where()
        self.assertEqual(self.codes(), [])

    def test_player_without_location(self):
        PlayerLocation.objects.filter(player=self.player).delete()
        self.assertEqual(self.codes(), ["PLAYER_WITHOUT_LOCATION"])

    def test_active_journey_that_does_not_start_where_the_player_is(self):
        self.go(self.far())
        PlayerLocation.objects.filter(player=self.player).update(lot=Lot.objects.exclude(pk=self.location().pk).first())
        self.assertEqual(self.codes(), ["ACTIVE_JOURNEY_ORIGIN_NOT_LOCATION"])

    def test_a_trip_that_arrived_but_was_never_settled(self):
        """O jogador já foi processado além da chegada e a viagem segue ativa: o sistema de tempo falhou."""
        self.go(self.far())
        Player.objects.filter(pk=self.player.pk).update(processed_until=Journey.objects.get().arrives_at + 1)
        self.assertEqual(self.codes(), ["JOURNEY_NOT_SETTLED"])

    def test_location_that_is_not_the_last_destination(self):
        dest = self.far()
        self.clk.advance(seconds=self.go(dest).detail["duration_seconds"])
        self.where()
        PlayerLocation.objects.filter(player=self.player).update(lot=self.near(dest))
        self.assertEqual(self.codes(), ["LOCATION_NOT_LAST_DESTINATION"])
