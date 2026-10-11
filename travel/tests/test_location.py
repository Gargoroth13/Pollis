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

    def capital_lots(self):
        from geography.models import State
        state = State.objects.exclude(capital=None).order_by("id").first()
        return Lot.objects.filter(neighborhood__city_id=state.capital_id).order_by("neighborhood__index", "index")

    def test_the_player_starts_in_the_capital(self):
        """Decisão do GD (2026-10-07): o jogador pode começar na capital."""
        from geography.models import State
        state = State.objects.exclude(capital=None).order_by("id").first()
        self.assertEqual(self.location().neighborhood.city_id, state.capital_id)
        self.assertEqual(self.location().pk, self.capital_lots().first().pk)
        self.assertEqual(services.default_initial_lot().pk, self.capital_lots().first().pk)

    def test_the_capital_comes_from_the_scenario_not_from_territorial_order(self):
        """Com capital_city_index=1 o jogador nasce na SEGUNDA cidade: seguir a capital != pegar o primeiro lote do mundo."""
        from django.test import override_settings
        from geography.balance import get_scenario
        from geography.generator import generate_world
        from geography.tests.base import SMALL, wipe_world
        from travel.models import Journey
        Journey.objects.all().delete()
        PlayerLocation.objects.all().delete()
        Player.objects.all().delete()
        wipe_world()
        generate_world(get_scenario(**{**SMALL, "capital_city_index": 1}))
        first_world_lot = Lot.objects.order_by("neighborhood__city__state_id", "neighborhood__city__index",
                                               "neighborhood__index", "index").first()
        p = self.new_player("capital1")
        self.assertEqual(self.location(p).neighborhood.city.index, 1)
        self.assertNotEqual(self.location(p).pk, first_world_lot.pk)

    def test_no_random_spawn_every_new_player_gets_the_same_lot(self):
        lots = {self.location(self.new_player(f"n{i}")).pk for i in range(8)}
        self.assertEqual(lots, {self.location().pk})

    def test_many_players_in_the_capital_are_not_a_capacity_problem(self):
        """A moradia inicial é garantida e NÃO consome a capacidade dos lotes: nenhum lote muda, nenhum jogador é recusado."""
        from geography.models import Neighborhood
        snapshot = lambda: (list(Lot.objects.order_by("id").values_list("id", "category", "neighborhood_id")),
                            [n.lot_capacity() for n in Neighborhood.objects.order_by("id")])
        before = snapshot()
        n = 3 * Lot.objects.filter(category="residential").count()
        for i in range(n):
            self.new_player(f"crowd{i}")
        self.assertGreater(n, Lot.objects.filter(category="residential").count())          # mais jogadores que lotes residenciais
        self.assertEqual(PlayerLocation.objects.filter(lot=self.location()).count(), n + 1)
        self.assertEqual(before, snapshot())

    def test_without_a_defined_capital_it_falls_back_to_the_first_lot_of_the_world(self):
        from geography.models import State
        first = Lot.objects.order_by("neighborhood__city__state_id", "neighborhood__city__index", "neighborhood__index", "index").first()
        State.objects.update(capital=None)
        self.assertEqual(services.default_initial_lot().pk, first.pk)

    def test_a_capital_without_lots_falls_back_to_the_first_lot_of_the_world(self):
        from geography.models import City, State
        first = Lot.objects.order_by("neighborhood__city__state_id", "neighborhood__city__index", "neighborhood__index", "index").first()
        state = State.objects.exclude(capital=None).order_by("id").first()
        empty = City.objects.create(state=state, index=99, name="vazia", x=0, y=0)
        State.objects.filter(pk=state.pk).update(capital=empty)
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
