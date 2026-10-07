from django.db.models import ProtectedError
from django.db import IntegrityError, transaction

from accounts.models import Usuario
from geography.models import Lot
from players.models import Player
from players.services import create_player
from travel import services
from travel.models import PlayerLocation
from travel.services import WorldNotGenerated

from .base import TravelTestCase


class InitialLocationTests(TravelTestCase):
    """04 §24: o jogador possui localização inicial física no mundo."""

    def test_every_new_player_has_a_valid_lot(self):
        for name in ("a", "b", "c"):
            p = self.new_player(name)
            self.assertTrue(Lot.objects.filter(pk=self.location(p).pk).exists())
        self.assertEqual(PlayerLocation.objects.count(), Player.objects.count())

    def test_default_is_the_first_lot_of_the_world_in_territorial_order(self):
        first = Lot.objects.order_by("neighborhood__city__state_id", "neighborhood__city__index", "neighborhood__index", "index").first()
        self.assertEqual(self.location().pk, first.pk)
        self.assertEqual(services.default_initial_lot().pk, first.pk)

    def test_a_creation_system_can_decide_the_initial_lot(self):
        """04 §24 / 01 §1: a regra vem da criação do jogador (contexto de nascimento), que ainda não existe."""
        target = Lot.objects.filter(category="residential").first()
        services.register_initial_location_provider("birth", lambda player: target)
        self.assertEqual(self.location(self.new_player("born")).pk, target.pk)
        self.assertNotEqual(self.location().pk, target.pk)                      # quem já existia não muda

    def test_first_provider_by_name_that_answers_wins_and_none_falls_through(self):
        a, b = Lot.objects.filter(category="residential")[:2]
        services.register_initial_location_provider("b_second", lambda p: b)
        services.register_initial_location_provider("a_first", lambda p: a)
        self.assertEqual(self.location(self.new_player("x")).pk, a.pk)
        services.clear_initial_location_providers()
        services.register_initial_location_provider("a_silent", lambda p: None)
        self.assertEqual(self.location(self.new_player("y")).pk, services.default_initial_lot().pk)

    def test_provider_names_are_unique(self):
        services.register_initial_location_provider("birth", lambda p: None)
        with self.assertRaises(ValueError):
            services.register_initial_location_provider("birth", lambda p: None)

    def test_without_a_world_no_player_is_created_not_even_half_of_one(self):
        """Sem lote não há localização válida: a criação falha INTEIRA (transação), em vez de criar jogador sem lugar."""
        from geography.tests.base import wipe_world
        from travel.models import Journey
        Journey.objects.all().delete()
        PlayerLocation.objects.all().delete()
        Player.objects.all().delete()
        wipe_world()
        user = Usuario.objects.create_user("no_world")
        with self.assertRaises(WorldNotGenerated):
            create_player(user)
        self.assertFalse(Player.objects.filter(user=user).exists())
        self.assertEqual(PlayerLocation.objects.count(), 0)


class LocationIntegrityTests(TravelTestCase):
    def test_one_location_per_player(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlayerLocation.objects.create(player=self.player, lot=Lot.objects.first())

    def test_a_lot_with_a_player_cannot_be_deleted_from_under_them(self):
        with self.assertRaises(ProtectedError):
            self.location().delete()

    def test_human_and_bot_get_the_same_kind_of_location(self):
        bot = create_player(Usuario.objects.create_user("bot_01"))
        self.assertEqual(self.location(bot).pk, self.location().pk)

    def test_get_location_reports_where_the_player_is_when_not_traveling(self):
        w = self.where()
        self.assertEqual((w.lot.pk, w.traveling, w.destination, w.arrives_at, w.remaining_seconds),
                         (self.location().pk, False, None, None, None))
