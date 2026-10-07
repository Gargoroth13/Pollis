from unittest import mock

from django.test import override_settings

from geography import services as geo
from players import hooks
from players.models import Player
from players.services import change_health, get_snapshot, sync_player
from travel import services
from travel.models import Journey, PlayerLocation

from .base import CYCLE, D, HOUR, T0, TravelTestCase


class DepartureTests(TravelTestCase):
    def test_travel_between_lots_records_origin_destination_and_instants(self):
        origin, dest = self.location(), self.far()
        r = self.go(dest)
        self.assertTrue(r.ok)
        j = Journey.objects.get()
        self.assertEqual((j.player_id, j.origin_id, j.destination_id, j.departed_at, j.completed), (self.player.pk, origin.pk, dest.pk, T0, False))
        self.assertEqual(j.arrives_at, T0 + self.expected_seconds(origin, dest))
        self.assertEqual((r.detail["departed_at"], r.detail["arrives_at"], r.detail["duration_seconds"]),
                         (T0, j.arrives_at, j.arrives_at - T0))

    def test_base_time_is_distance_times_minutes_per_unit(self):
        """04 §21 (corrigido pelo GD): tempo-base = distância × minutos_por_unidade; valor inicial 15."""
        origin, dest = self.location(), self.far()
        tt = self.go(dest).detail["travel_time"]
        self.assertEqual([s.key for s in tt.steps], ["distance", "minutes_per_unit"])
        self.assertEqual((tt.step("distance").amount, tt.step("minutes_per_unit").amount), (geo.distance_between(origin, dest), 15))
        self.assertEqual(tt.value, geo.base_travel_minutes(origin, dest))        # mesma fonte da Geografia
        self.assertEqual(tt.computed_at, T0)                                      # 20.9

    def test_distance_is_derived_from_geography_never_stored(self):
        """04 §21: 'não armazenada como atributo independente'. A viagem guarda o que ela É, não a distância."""
        names = {f.name for f in Journey._meta.get_fields()} | {f.name for f in PlayerLocation._meta.get_fields()}
        self.assertFalse({n for n in names if "dist" in n or "minutes" in n or "duration" in n})

    def test_estimate_is_pure_and_matches_what_departure_will_use(self):
        origin, dest = self.location(), self.far()
        est = services.estimate_travel(origin, dest)
        self.assertEqual(Journey.objects.count(), 0)                              # só estima, não cria nada
        self.assertEqual(self.go(dest).detail["travel_time"].value, est.value)

    @override_settings(POLIS_GEOGRAPHY={"travel_minutes_per_unit": 30})
    def test_minutes_per_unit_is_a_calibrable_scenario_parameter(self):
        origin, dest = self.location(), self.far()
        self.assertEqual(self.go(dest).detail["duration_seconds"], self.expected_seconds(origin, dest, 30))

    def test_changing_the_parameter_later_does_not_alter_a_journey_in_progress(self):
        dest = self.far()
        arrives = self.go(dest).detail["arrives_at"]
        with override_settings(POLIS_GEOGRAPHY={"travel_minutes_per_unit": 1}):
            self.assertEqual(Journey.objects.get().arrives_at, arrives)
            self.assertEqual(self.where().arrives_at, arrives)

    def test_while_traveling_the_player_is_still_reported_at_the_origin(self):
        origin = self.location()
        self.go(self.far())
        w = self.where()
        self.assertEqual((w.traveling, w.lot.pk, w.destination.pk), (True, origin.pk, self.far(origin).pk))
        self.assertEqual(self.location().pk, origin.pk)

    def test_departure_costs_no_energy_burnout_money_or_health(self):
        """O 04 não define custo de viagem: nenhum foi inventado."""
        before = self.state()
        r = self.go(self.far())
        after = self.state()
        self.assertTrue(r.ok)
        self.assertEqual((after.energy, after.burnout, after.health, after.nutrition), (before.energy, before.burnout, before.health, before.nutrition))

    def test_traveling_does_not_change_the_normal_evolution_of_the_players_state(self):
        control = self.new_player("control")
        self.go(self.far())
        self.clk.advance(seconds=3 * HOUR)
        a, b = self.state(), self.state(control)
        self.assertEqual((a.energy, a.health, a.nutrition, a.burnout), (b.energy, b.health, b.nutrition, b.burnout))


class ArrivalTests(TravelTestCase):
    def test_arrival_happens_exactly_at_the_computed_instant(self):
        dest = self.far()
        arrives = self.go(dest).detail["arrives_at"]
        self.clk.set(arrives - 1)
        w = self.where()
        self.assertEqual((w.traveling, w.remaining_seconds), (True, 1))
        self.clk.set(arrives)
        w = self.where()
        self.assertEqual((w.traveling, w.lot.pk, w.remaining_seconds), (False, dest.pk, None))
        self.assertTrue(Journey.objects.get().completed)

    def test_arrival_is_recorded_at_the_planned_time_not_when_the_player_looks(self):
        dest = self.far()
        arrives = self.go(dest).detail["arrives_at"]
        self.clk.advance(days=3)
        self.where()
        self.assertEqual(Journey.objects.get().arrives_at, arrives)               # não vira o instante do acesso
        self.assertEqual(self.location().pk, dest.pk)

    def test_arrival_between_two_cycles_needs_the_access_hook(self):
        """Chega ENTRE dois ciclos de 10 min. Só o hook de acesso (On Access) a conclui no instante exato."""
        self.near_destination = self.near().pk
        r = self.go(self.near())
        self.assertNotEqual(r.detail["arrives_at"] % CYCLE, 0)                     # pré-condição: chega ENTRE dois ciclos
        self.clk.set(r.detail["arrives_at"])
        self.assertFalse(self.where().traveling)
        self.assertEqual(self.where().lot.pk, self.near_destination)

    def test_without_the_access_hook_a_between_cycles_arrival_is_not_seen(self):
        """Prova de que o hook é necessário: sem ele, o estado fica velho até o próximo ciclo."""
        hooks.unregister_access_hook("travel")
        self.addCleanup(hooks.register_access_hook, "travel", services.settle_arrivals)
        r = self.go(self.near())
        self.assertNotEqual(r.detail["arrives_at"] % CYCLE, 0)                     # pré-condição: chega ENTRE dois ciclos
        self.clk.set(r.detail["arrives_at"])
        self.assertTrue(self.where().traveling)                                    # já passou da hora, mas nada concluiu
        self.assertFalse(Journey.objects.get().completed)

    def test_the_cycle_handler_completes_the_trip_in_the_time_systems_own_order(self):
        """Sem o hook de acesso, o handler do ciclo de 10 min conclui a viagem ao cruzar o primeiro ciclo após a chegada."""
        hooks.unregister_access_hook("travel")
        self.addCleanup(hooks.register_access_hook, "travel", services.settle_arrivals)
        dest = self.far()
        arrives = self.go(dest).detail["arrives_at"]
        self.clk.set(arrives + CYCLE)                                              # cruza pelo menos um ciclo depois da chegada
        w = self.where()
        self.assertEqual((w.traveling, w.lot.pk), (False, dest.pk))

    def test_cycle_handler_does_not_complete_before_arrival(self):
        hooks.unregister_access_hook("travel")
        self.addCleanup(hooks.register_access_hook, "travel", services.settle_arrivals)
        arrives = self.go(self.far()).detail["arrives_at"]
        self.clk.set(arrives - CYCLE)                                              # vários ciclos já passaram, mas ainda não chegou
        self.assertTrue(self.where().traveling)

    def test_accessing_often_never_changes_the_outcome(self):
        """04 §22: acessar a cada ciclo ou só no fim dá o MESMO resultado."""
        a, b = self.player, self.new_player("lazy")
        dest = self.far()
        self.go(dest, a), self.go(dest, b)
        arrives = Journey.objects.get(player=a).arrives_at
        while self.clk.now() < arrives + 2 * CYCLE:
            self.clk.advance(seconds=CYCLE // 2)
            sync_player(a.pk)
        sync_player(b.pk)
        wa, wb = self.where(a), self.where(b)
        self.assertEqual((wa.lot.pk, wa.traveling), (wb.lot.pk, wb.traveling))
        self.assertEqual((wa.lot.pk, wa.traveling), (dest.pk, False))
        self.assertEqual(Journey.objects.get(player=a).arrives_at, Journey.objects.get(player=b).arrives_at)

    def test_a_new_trip_can_start_after_arrival_from_the_new_place(self):
        first = self.far()
        self.clk.advance(seconds=self.go(first).detail["duration_seconds"])
        second = self.far(first)
        r = self.go(second)
        self.assertTrue(r.ok)
        self.assertEqual(Journey.objects.get(completed=False).origin_id, first.pk)
        self.clk.advance(seconds=r.detail["duration_seconds"])
        self.assertEqual(self.where().lot.pk, second.pk)
        self.assertEqual(Journey.objects.filter(player=self.player, completed=True).count(), 2)

    def test_players_travel_independently(self):
        other = self.new_player("other")
        self.go(self.far())
        self.assertTrue(self.where().traveling)
        self.assertFalse(self.where(other).traveling)


class RefusalTests(TravelTestCase):
    def test_cannot_start_a_second_trip_while_traveling(self):
        self.go(self.far())
        arrives = Journey.objects.get().arrives_at
        r = self.go(self.near())
        self.assertEqual((r.ok, r.code), (False, "ALREADY_TRAVELING"))
        self.assertEqual((Journey.objects.count(), Journey.objects.get().arrives_at), (1, arrives))

    def test_cannot_travel_to_where_you_already_are(self):
        r = self.go(self.location())
        self.assertEqual((r.ok, r.code), (False, "SAME_LOCATION"))
        self.assertEqual(Journey.objects.count(), 0)

    def test_unknown_destination_is_a_refusal_not_an_exception(self):
        r = services.start_travel(self.player.pk, 10 ** 9)
        self.assertEqual((r.ok, r.code), (False, "INVALID_DESTINATION"))
        self.assertEqual(Journey.objects.count(), 0)

    def test_a_refusal_changes_nothing_about_location_or_state(self):
        before = self.state()
        self.go(self.location())
        after = self.state()
        self.assertEqual((self.location().pk, after.energy, after.processed_until), (self.location().pk, before.energy, before.processed_until))


class BlockedDepartureConfigTests(TravelTestCase):
    """[ABERTO] O 04 não define estados que impeçam PARTIR: por padrão nenhum impede; é configurável."""

    def test_by_default_nothing_prevents_departing(self):
        change_health(self.player.pk, -100, "t")                                   # hospitalizado e Saúde Crítica
        self.set_state(burnout=100, burnout_active=True)
        self.assertTrue(self.go(self.far()).ok)

    @override_settings(POLIS_TRAVEL_BALANCE={"travel_blocking_states": ["hospitalized", "health_critical", "burnout_active"]})
    def test_configured_states_prevent_departing_in_a_fixed_order(self):
        change_health(self.player.pk, -100, "t")
        self.assertEqual(self.go(self.far()).code, "HOSPITALIZED")
        self.clk.advance(seconds=6 * HOUR)                                         # hospitalização termina
        self.state()                                                               # sincroniza ANTES de forçar o estado
        self.set_state(health=10, health_critical=True, hospitalized_until=None)
        self.assertEqual(self.go(self.far()).code, "HEALTH_CRITICAL")
        self.set_state(health=100, health_critical=False, burnout=100, burnout_active=True)
        self.assertEqual(self.go(self.far()).code, "BURNOUT_ACTIVE")
        self.assertEqual(Journey.objects.count(), 0)


class AtomicityTests(TravelTestCase):
    def test_failure_after_the_journey_is_created_rolls_everything_back(self):
        with mock.patch.object(Player, "save", side_effect=RuntimeError("falha depois de criar a viagem")):
            with self.assertRaises(RuntimeError):
                self.go(self.far())
        self.assertEqual(Journey.objects.count(), 0)
        self.assertFalse(self.where().traveling)

    def test_failure_while_completing_a_trip_rolls_back_the_arrival(self):
        dest = self.far()
        self.go(dest)
        self.clk.advance(days=1)
        with mock.patch.object(Player, "save", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                sync_player(self.player.pk)
        self.assertFalse(Journey.objects.get().completed)                           # a chegada também foi desfeita
        self.assertNotEqual(self.location().pk, dest.pk)
        self.assertEqual(self.where().lot.pk, dest.pk)                              # e na tentativa seguinte conclui normalmente


class QueryCostTests(TravelTestCase):
    """
    O handler de chegada roda a cada ciclo de 10 min, e uma ausência de 2 dias são ~288 ciclos. A viagem ativa tem de ser
    consultada UMA vez por catch-up (cache do contexto), não uma vez por ciclo.
    """

    def journey_queries(self, fn):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            fn()
        return sum(1 for q in ctx.captured_queries if "travel_journey" in q["sql"])

    @override_settings(POLIS_GEOGRAPHY={"travel_minutes_per_unit": 100000})
    def test_a_long_absence_with_a_trip_in_progress_costs_a_constant_number_of_journey_queries(self):
        self.go(self.far())                                                       # viagem de muitos dias
        self.clk.advance(days=2)
        n = self.journey_queries(lambda: sync_player(self.player.pk))
        self.assertTrue(Journey.objects.get().arrives_at > self.clk.now())         # ainda viajando: não é atalho por conclusão
        self.assertLessEqual(n, 4, f"{n} consultas à viagem para ~288 ciclos")

    def test_a_long_absence_without_any_trip_also_costs_a_constant_number(self):
        self.clk.advance(days=2)
        self.assertLessEqual(self.journey_queries(lambda: sync_player(self.player.pk)), 4)
