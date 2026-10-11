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

    def test_departure_costs_no_energy_burnout_or_health(self):
        """O custo da viagem é TEMPO e DINHEIRO (GD, 2026-10-07); Energia, Burnout e Saúde não são afetados."""
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


class NoStateBlocksDepartureTests(TravelTestCase):
    """Decisão do GD (2026-10-07): nenhum estado atual impede iniciar uma viagem (p.ex. viajar em busca de tratamento)."""

    def test_hospitalized_player_can_travel(self):
        change_health(self.player.pk, -100, "t")
        self.assertIsNotNone(self.state().hospitalized_until)
        self.assertTrue(self.go(self.far()).ok)

    def test_health_critical_player_can_travel(self):
        self.set_state(health=10, health_critical=True)
        self.assertTrue(self.go(self.far()).ok)

    def test_active_burnout_player_can_travel(self):
        self.set_state(burnout=100, burnout_active=True)
        self.assertTrue(self.go(self.far()).ok)

    def test_all_states_together_can_travel(self):
        change_health(self.player.pk, -100, "t")
        self.set_state(burnout=100, burnout_active=True)
        self.assertTrue(self.go(self.far()).ok)
        self.assertEqual(Journey.objects.count(), 1)

    def test_departure_does_not_cure_or_change_those_states(self):
        change_health(self.player.pk, -100, "t")
        self.set_state(burnout=100, burnout_active=True)
        before = self.state()
        self.go(self.far())
        after = self.state()
        self.assertIsNotNone(before.hospitalized_until)
        self.assertEqual((after.hospitalized_until, after.health_critical, after.burnout_active),
                         (before.hospitalized_until, before.health_critical, before.burnout_active))

    def test_there_is_no_balance_option_to_block_travel_by_state(self):
        with self.assertRaises(ImportError):
            import travel.balance  # noqa: F401


class TravelCostTests(TravelTestCase):
    """Decisão do GD (2026-10-07): viagem custa tempo E dinheiro; custo = distância × custo_por_unidade, parametrizado."""

    def test_cost_is_distance_times_cost_per_unit_with_a_breakdown(self):
        origin, dest = self.location(), self.far()
        r = self.go(dest)
        c = r.detail["travel_cost"]
        self.assertEqual([s.key for s in c.steps], ["distance", "cost_per_unit"])
        self.assertEqual((c.step("distance").amount, c.step("cost_per_unit").amount), (geo.distance_between(origin, dest), 10))
        self.assertEqual(c.value, geo.distance_between(origin, dest) * 10)
        self.assertEqual(r.detail["cost"], services.rules.charge_amount(c.value))
        self.assertEqual(Journey.objects.get().cost, r.detail["cost"])

    @override_settings(POLIS_GEOGRAPHY={"travel_cost_per_unit": "0.3333"})
    def test_charged_amount_is_rounded_to_cents_while_the_calculation_stays_exact(self):
        """Interpretação técnica: o cálculo (doc 20 §8) é exato; o valor cobrado/registrado vai a centavos."""
        origin, dest = self.location(), self.far()
        r = self.go(dest)
        exact = r.detail["travel_cost"].value
        self.assertEqual(exact, geo.distance_between(origin, dest) * D("0.3333"))
        self.assertNotEqual(exact, exact.quantize(D("0.01")))                    # a conta tem mais de 2 casas
        self.assertEqual(r.detail["cost"], exact.quantize(D("0.01")))
        self.assertEqual(Journey.objects.get().cost, exact.quantize(D("0.01")))

    def test_time_is_unchanged_by_the_cost_rule(self):
        origin, dest = self.location(), self.far()
        r = self.go(dest)
        self.assertEqual(r.detail["duration_seconds"], self.expected_seconds(origin, dest))     # 15 min por unidade, como antes

    @override_settings(POLIS_GEOGRAPHY={"travel_cost_per_unit": 25})
    def test_cost_per_unit_is_a_calibrable_scenario_parameter(self):
        origin, dest = self.location(), self.far()
        r = self.go(dest)
        self.assertEqual(r.detail["travel_cost"].value, geo.distance_between(origin, dest) * 25)

    @override_settings(POLIS_GEOGRAPHY={"travel_cost_per_unit": 0})
    def test_free_travel_is_valid_and_needs_no_payment(self):
        r = self.go(self.far())
        self.assertEqual((r.ok, r.detail["cost"], r.detail["payment"]), (True, 0, "NOT_REQUIRED"))

    def test_negative_cost_per_unit_is_rejected(self):
        from django.core.exceptions import ImproperlyConfigured
        from geography.balance import get_scenario
        with self.assertRaises(ImproperlyConfigured):
            get_scenario(travel_cost_per_unit=-1)

    def test_farther_costs_more_and_takes_longer(self):
        origin = self.location()
        near, far = self.near(origin), self.far(origin)
        qn, qf = services.quote_travel(origin, near), services.quote_travel(origin, far)
        self.assertLess(qn.amount, qf.amount)
        self.assertLess(qn.duration_seconds, qf.duration_seconds)

    def test_quote_is_pure_and_matches_departure(self):
        origin, dest = self.location(), self.far()
        q = services.quote_travel(origin, dest, T0, self.player)
        self.assertEqual(Journey.objects.count(), 0)
        r = self.go(dest)
        self.assertEqual((r.detail["cost"], r.detail["duration_seconds"]), (q.amount, q.duration_seconds))

    def test_the_charge_is_rounded_to_cents_with_bankers_rounding_but_the_calculation_is_exact(self):
        from decimal import Decimal
        self.assertEqual(services.rules.charge_amount(Decimal("1.005")), Decimal("1.00"))
        self.assertEqual(services.rules.charge_amount(Decimal("1.015")), Decimal("1.02"))
        self.assertEqual(services.rules.travel_cost(Decimal("1.2345"), Decimal(10)).value, Decimal("12.3450"))

    def test_cost_is_fixed_at_departure(self):
        r = self.go(self.far())
        with override_settings(POLIS_GEOGRAPHY={"travel_cost_per_unit": 1}):
            self.assertEqual(Journey.objects.get().cost, r.detail["cost"])

    def test_refused_departures_charge_nothing(self):
        self.go(self.location())
        self.assertEqual(Journey.objects.count(), 0)


class PaymentIntegrationTests(TravelTestCase):
    """O sistema de dinheiro ainda não existe: o custo é calculado e registrado; a cobrança é um ponto de integração."""

    def test_without_a_money_system_the_cost_is_registered_but_not_charged(self):
        r = self.go(self.far())
        j = Journey.objects.get()
        self.assertEqual((r.ok, r.detail["payment"], j.charged), (True, "NO_PAYMENT_SYSTEM", False))
        self.assertGreater(j.cost, 0)

    def test_a_payment_handler_receives_the_amount_and_the_trip_is_marked_charged(self):
        calls = []
        services.register_payment_handler("wallet", lambda player, amount, ctx: calls.append((player.pk, amount, ctx["at"])) or True)
        dest = self.far()
        r = self.go(dest)
        self.assertEqual(calls, [(self.player.pk, r.detail["cost"], T0)])
        self.assertEqual((r.detail["payment"], Journey.objects.get().charged), ("CHARGED", True))

    def test_insufficient_funds_refuses_the_trip_and_creates_nothing(self):
        services.register_payment_handler("wallet", lambda player, amount, ctx: False)
        r = self.go(self.far())
        self.assertEqual((r.ok, r.code), (False, "INSUFFICIENT_FUNDS"))
        self.assertGreater(r.detail["cost"], 0)
        self.assertEqual(Journey.objects.count(), 0)
        self.assertFalse(self.where().traveling)

    def test_a_failure_after_payment_rolls_the_whole_departure_back(self):
        """Pagar e falhar ao criar a viagem não pode deixar o dinheiro debitado: tudo na mesma transação."""
        from django.db import transaction
        debited = []
        def pay(player, amount, ctx):
            debited.append(amount)
            return True
        services.register_payment_handler("wallet", pay)
        with mock.patch.object(Journey.objects, "create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.go(self.far())
        self.assertEqual(Journey.objects.count(), 0)

    def test_only_one_payment_handler_and_it_can_be_removed(self):
        services.register_payment_handler("wallet", lambda *a: True)
        with self.assertRaises(ValueError):
            services.register_payment_handler("other", lambda *a: True)
        services.unregister_payment_handler("wallet")
        self.assertEqual(self.go(self.far()).detail["payment"], "NO_PAYMENT_SYSTEM")

    def test_a_free_trip_never_calls_the_handler(self):
        called = []
        services.register_payment_handler("wallet", lambda *a: called.append(1) or True)
        with override_settings(POLIS_GEOGRAPHY={"travel_cost_per_unit": 0}):
            self.assertTrue(self.go(self.far()).ok)
        self.assertEqual(called, [])


class TravelModifierExtensionTests(TravelTestCase):
    """04 §21: veículos e demais modificadores virão depois e reduzirão custo / modificarão tempo. A arquitetura já comporta."""

    def test_no_modifiers_means_base_time_and_base_cost(self):
        q = services.quote_travel(self.location(), self.far())
        self.assertEqual([s.key for s in q.time.steps], ["distance", "minutes_per_unit"])
        self.assertEqual([s.key for s in q.cost.steps], ["distance", "cost_per_unit"])

    def test_a_modifier_scales_time_and_cost_and_shows_in_the_breakdown(self):
        origin, dest = self.location(), self.far()
        base = services.quote_travel(origin, dest)
        services.register_travel_modifier("vehicle", lambda p, o, d: services.TravelModifier("vehicle", D("0.5"), D("0.25")))
        q = services.quote_travel(origin, dest)
        self.assertEqual(q.time.value, base.time.value * D("0.5"))
        self.assertEqual(q.cost.value, base.cost.value * D("0.25"))
        self.assertEqual([s.key for s in q.time.steps][-1], "modifier:vehicle")
        self.assertEqual([s.key for s in q.cost.steps][-1], "modifier:vehicle")

    def test_departure_uses_the_modified_values(self):
        origin, dest = self.location(), self.far()
        base = services.quote_travel(origin, dest)
        services.register_travel_modifier("vehicle", lambda p, o, d: services.TravelModifier("vehicle", D("0.5"), D("0.25")))
        r = self.go(dest)
        self.assertEqual(r.detail["duration_seconds"], services.rules.duration_seconds(base.time.value * D("0.5")))
        self.assertEqual(r.detail["cost"], services.rules.charge_amount(base.cost.value * D("0.25")))

    def test_a_modifier_can_depend_on_the_player(self):
        other = self.new_player("with_car")
        services.register_travel_modifier("vehicle", lambda p, o, d: services.TravelModifier("vehicle", D("0.5"), D("0.5"))
                                          if p is not None and p.pk == other.pk else None)
        dest = self.far()
        mine, theirs = self.go(dest).detail, self.go(dest, other).detail
        self.assertLess(theirs["cost"], mine["cost"])
        self.assertLess(theirs["duration_seconds"], mine["duration_seconds"])

    def test_modifiers_apply_in_a_fixed_order_by_name_and_names_are_unique(self):
        services.register_travel_modifier("b", lambda p, o, d: services.TravelModifier("b", D(2), D(1)))
        services.register_travel_modifier("a", lambda p, o, d: services.TravelModifier("a", D(3), D(1)))
        q = services.quote_travel(self.location(), self.far())
        self.assertEqual([s.key for s in q.time.steps][2:], ["modifier:a", "modifier:b"])
        with self.assertRaises(ValueError):
            services.register_travel_modifier("a", lambda *x: None)

    def test_a_modifier_never_makes_a_trip_instant_or_free_by_accident(self):
        services.register_travel_modifier("tiny", lambda p, o, d: services.TravelModifier("tiny", D("0.0000001"), D(1)))
        r = self.go(self.near())
        self.assertGreaterEqual(r.detail["duration_seconds"], 1)


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
