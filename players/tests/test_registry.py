"""
Action Registry (P1.03; design/21 §20). O registro DESCREVE e DELEGA: estes testes provam que ele não reimplementa regra
(mesmos códigos e resultados dos serviços), que o contrato do descritor não inventa semântica, que parâmetros internos não
entram por ele e que disponibilidade geral e validação de alvo são coisas distintas.
"""
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from core.breakdown import Explained
from players import hooks, registry, rules
from players.actions import Action
from players.balance import get_balance
from players.models import Player
from players.services import change_health, perform_action
from travel import services as travel
from travel.models import Journey
from travel.tests.base import CYCLE, HOUR, TravelTestCase

D = Decimal
PLAYER_ACTIONS = ("work", "study", "leisure")


def avail(player_id):
    return {a.action_id: a for a in registry.available_actions(player_id)}


class DescriptorContractTests(TravelTestCase):
    """21 §20: ID, nome, categoria, requisitos, custo, cooldown, alvo, efeitos, visibilidade. Nada inventado."""

    def test_the_actions_are_registered_with_stable_ids(self):
        self.assertEqual([d.id for d in registry.list_descriptors()],
                         ["auto_consumption", "consume", "found_company", "fund_company", "leisure", "send_item", "study", "travel", "work"])
        self.assertEqual({d.id: d.name for d in registry.list_descriptors()},
                         {"work": "Trabalhar", "study": "Estudar", "leisure": "Lazer", "travel": "Viajar",
                          "consume": "Consumir", "send_item": "Enviar item pelo Correio",
                          "auto_consumption": "Configurar Auto-consumo", "found_company": "Fundar empresa",
                          "fund_company": "Aportar capital na empresa"})

    def test_travel_is_not_added_to_the_energy_action_enum(self):
        """Viajar não tem custo de Energia (04 §2.2): o enum Action continua com as 3 ações de custo fixo."""
        self.assertEqual({a.value for a in Action}, {"work", "study", "leisure"})
        self.assertEqual({d.id for d in registry.list_descriptors()} - {a.value for a in Action}, {"travel", "consume", "send_item", "auto_consumption", "found_company", "fund_company"})

    def test_every_contract_field_is_present(self):
        for d in registry.list_descriptors():
            self.assertEqual(set(d.to_dict()), {"id", "name", "category", "requirements", "cost", "cooldown", "target",
                                                "effects", "visibility"})

    def test_undefined_design_fields_are_explicitly_unspecified_not_invented(self):
        for d in registry.list_descriptors():
            self.assertEqual((d.category, d.visibility), (registry.UNSPECIFIED, registry.UNSPECIFIED), d.id)
            self.assertEqual(d.cooldown, registry.NO_COOLDOWN, d.id)

    def test_targets(self):
        for a in PLAYER_ACTIONS:
            self.assertEqual(registry.get_descriptor(a).target, registry.TargetSpec(registry.TARGET_NONE, False))
        self.assertEqual(registry.get_descriptor("travel").target, registry.TargetSpec(registry.TARGET_LOT, True))
        self.assertEqual(registry.get_descriptor("consume").target, registry.TargetSpec(registry.TARGET_PRODUCT, True))
        self.assertEqual(registry.get_descriptor("send_item").target, registry.TargetSpec(registry.TARGET_PARAMS, True))
        self.assertEqual(registry.get_descriptor("auto_consumption").target, registry.TargetSpec(registry.TARGET_PARAMS, True))

    def test_availability_lists_actions_in_a_deterministic_id_order(self):
        self.assertEqual([a.action_id for a in registry.available_actions(self.player.pk)],
                         ["auto_consumption", "consume", "found_company", "fund_company", "leisure", "send_item", "study", "travel", "work"])

    def test_descriptors_are_immutable(self):
        with self.assertRaises(Exception):
            registry.get_descriptor("work").name = "x"

    def test_duplicate_id_is_an_error_and_never_overwrites(self):
        before = registry.get_descriptor("work")
        with self.assertRaises(ValueError):
            registry.register_action(registry.ActionDescriptor("work", "Outro"), check=None, execute=None, preview=None)
        self.assertIs(registry.get_descriptor("work"), before)

    def test_ids_must_be_stable_identifiers(self):
        for bad in ("", "Work", "1work", "work now", "trabalhar-x", "açao"):
            with self.assertRaises(ValueError, msg=bad):
                registry.ActionDescriptor(bad, "x")

    def test_a_target_less_action_cannot_require_a_target(self):
        with self.assertRaises(ValueError):
            registry.TargetSpec(registry.TARGET_NONE, True)
        with self.assertRaises(ValueError):
            registry.TargetSpec("planet")

    def test_unknown_action_is_a_code_not_an_exception(self):
        self.assertEqual(registry.execute_action(self.player.pk, "fly").code, "UNKNOWN_ACTION")
        c = registry.check_action(self.player.pk, "fly")
        self.assertEqual((c.available, c.code), (False, "UNKNOWN_ACTION"))

    def test_a_test_action_can_be_registered_and_removed(self):
        d = registry.ActionDescriptor("noop_test", "Nada")
        registry.register_action(d, check=lambda *a: None, execute=lambda pid, t: registry.ActionResult(True, "OK"),
                                 preview=lambda *a: {})
        self.addCleanup(registry.unregister_action, "noop_test")
        self.assertIn("noop_test", [x.id for x in registry.list_descriptors()])
        self.assertTrue(registry.execute_action(self.player.pk, "noop_test").ok)


class RequirementsDeclaredTests(TravelTestCase):
    """`requirements` é documentação: nenhum código de recusa real das regras do dono pode escapar dela."""

    def test_every_real_refusal_is_declared_or_comes_from_a_provider(self):
        providers = {"TRAVELING"}
        states = [dict(health=D(0)), dict(health=D(15)), dict(burnout=D(100), burnout_active=True), dict(energy=D(0)),
                  dict(energy=D(5))]
        seen = set()
        for i, st in enumerate(states):
            p = self.new_player(f"r{i}")
            if "health" in st:
                change_health(p.pk, -D(100) + st["health"], "test")
            self.set_state(p, **{k: v for k, v in st.items() if k != "health"})
            for aid, a in avail(p.pk).items():
                if aid == "travel" or a.available:
                    continue
                codes = {a.code, *a.blocked_by}
                seen |= codes
                self.assertLessEqual(codes - providers, set(registry.get_descriptor(aid).requirements), (aid, st))
        self.assertTrue({"HOSPITALIZED", "HEALTH_CRITICAL", "BURNOUT_ACTIVE", "INSUFFICIENT_ENERGY"} <= seen, seen)


class ParameterProtectionTests(TravelTestCase):
    def test_internal_context_params_are_rejected_not_ignored(self):
        before = self.state()
        for name, value in (("burnout_risk", 0), ("effect", object()), ("activity", hooks.ActivityContext())):
            r = registry.execute_action(self.player.pk, "work", **{name: value})
            self.assertEqual((r.ok, r.code), (False, "INVALID_PARAMS"), name)
            self.assertEqual(r.detail["internal"], [name])
        after = self.state()
        self.assertEqual((after.energy, after.burnout, after.last_work_at), (before.energy, before.burnout, before.last_work_at))

    def test_burnout_risk_cannot_be_used_to_dodge_burnout_through_the_registry(self):
        registry.execute_action(self.player.pk, "work", burnout_risk=0)
        self.assertEqual(self.state().burnout, D(0))            # nada executou
        self.assertTrue(registry.execute_action(self.player.pk, "work").ok)
        self.assertEqual(self.state().burnout, get_balance().burnout_gain_work)   # risco padrão 1: custo integral

    def test_unknown_params_are_rejected_too(self):
        r = registry.execute_action(self.player.pk, "study", foo=1, burnout_risk=2)
        self.assertEqual((r.code, r.detail["rejected"], r.detail["internal"]), ("INVALID_PARAMS", ["burnout_risk", "foo"], ["burnout_risk"]))

    def test_leisure_effect_cannot_be_injected(self):
        r = registry.execute_action(self.player.pk, "leisure", effect=object())
        self.assertEqual(r.code, "INVALID_PARAMS")

    def test_internal_params_are_exactly_the_context_params_of_perform_action(self):
        import inspect
        extra = set(inspect.signature(perform_action).parameters) - {"player_id", "action"}
        self.assertEqual(registry.INTERNAL_PARAMS, extra)


class TargetRulesTests(TravelTestCase):
    def test_actions_without_target_refuse_one(self):
        for a in PLAYER_ACTIONS:
            r = registry.execute_action(self.player.pk, a, 5)
            self.assertEqual((r.ok, r.code), (False, "TARGET_NOT_ALLOWED"), a)
            c = registry.check_action(self.player.pk, a, 5)
            self.assertEqual((c.available, c.code), (False, "TARGET_NOT_ALLOWED"), a)
        self.assertEqual(self.state().energy, get_balance().energy_max)   # nada foi gasto

    def test_travel_without_target_is_refused_with_target_required(self):
        r = registry.execute_action(self.player.pk, "travel")
        self.assertEqual((r.ok, r.code), (False, "TARGET_REQUIRED"))
        self.assertEqual(Journey.objects.count(), 0)

    def test_malformed_targets_are_invalid_params_and_never_reach_the_database(self):
        for bad in ("12", 1.5, True, [1], 2 ** 63, -2 ** 63 - 1, D(3)):
            r = registry.execute_action(self.player.pk, "travel", bad)
            self.assertEqual((r.ok, r.code), (False, "INVALID_PARAMS"), repr(bad))
            c = registry.check_action(self.player.pk, "travel", bad)
            self.assertEqual((c.available, c.code, c.target_validated), (False, "INVALID_PARAMS", False), repr(bad))

    def test_nonexistent_lot_keeps_the_travel_domain_code(self):
        r = registry.execute_action(self.player.pk, "travel", 10 ** 9)
        self.assertEqual((r.ok, r.code), (False, "INVALID_DESTINATION"))


class GeneralAvailabilityVersusTargetTests(TravelTestCase):
    """Sem alvo: Viajar continua na disponibilidade geral; com alvo: valida o destino. Não enumera lotes."""

    def test_travel_stays_generally_available_without_a_target(self):
        a = avail(self.player.pk)["travel"]
        self.assertEqual((a.available, a.code, a.target_required, a.target_validated, a.preview), (True, "OK", True, False, {}))

    def test_with_a_target_the_destination_is_validated(self):
        ok = registry.check_action(self.player.pk, "travel", self.far().pk)
        self.assertEqual((ok.available, ok.code, ok.target_validated), (True, "OK", True))
        same = registry.check_action(self.player.pk, "travel", self.location().pk)
        self.assertEqual((same.available, same.code, same.target_validated), (False, "SAME_LOCATION", True))
        bad = registry.check_action(self.player.pk, "travel", 10 ** 9)
        self.assertEqual((bad.available, bad.code), (False, "INVALID_DESTINATION"))

    def test_already_traveling_removes_it_from_general_availability(self):
        self.go(self.far())
        self.assertEqual((avail(self.player.pk)["travel"].available, avail(self.player.pk)["travel"].code), (False, "ALREADY_TRAVELING"))
        self.assertEqual(registry.check_action(self.player.pk, "travel", self.near().pk).code, "ALREADY_TRAVELING")

    def test_availability_never_lists_or_queries_all_lots(self):
        with CaptureQueriesContext(connection) as ctx:
            registry.available_actions(self.player.pk)
        self.assertFalse([q for q in ctx.captured_queries if 'FROM "geography_lot"' in q["sql"]], "não deve enumerar lotes")

    def test_checking_creates_no_journey_and_charges_nothing(self):
        handler = mock.Mock(return_value=True)
        travel.register_payment_handler("t", handler)
        registry.check_action(self.player.pk, "travel", self.far().pk)
        registry.available_actions(self.player.pk)
        handler.assert_not_called()
        self.assertEqual(Journey.objects.count(), 0)

    def test_execution_revalidates_after_a_stale_check(self):
        """A consulta é consultiva: o estado muda entre ela e a execução, e a execução decide."""
        self.assertTrue(registry.check_action(self.player.pk, "work").available)
        self.set_state(energy=D(0))
        r = registry.execute_action(self.player.pk, "work")
        self.assertEqual((r.ok, r.code), (False, "INSUFFICIENT_ENERGY"))
        dest = self.far()
        self.assertTrue(registry.check_action(self.player.pk, "travel", dest.pk).available)
        self.go(self.near())
        r = registry.execute_action(self.player.pk, "travel", dest.pk)
        self.assertEqual((r.ok, r.code), (False, "ALREADY_TRAVELING"))
        self.assertEqual(Journey.objects.count(), 1)


class RefusalEquivalenceTests(TravelTestCase):
    """Cada recusa do registro é a MESMA do serviço direto (código e motivos)."""

    def _twin(self, name):
        return self.new_player(name)

    def _states(self):
        yield "fresh", {}
        yield "no_energy", dict(energy=D(0))
        yield "low_energy_study_ok", dict(energy=D(10))
        yield "burnout_active", dict(burnout=D(100), burnout_active=True)
        yield "hospitalized", None
        yield "critical", None

    def _prepare(self, player, name):
        if name == "hospitalized":
            change_health(player.pk, -D(100), "test")
        elif name == "critical":
            change_health(player.pk, -D(85), "test")
        else:
            st = dict(self._states_map[name])
            if st:
                self.set_state(player, **st)

    _states_map = dict(fresh={}, no_energy=dict(energy=D(0)), low_energy_study_ok=dict(energy=D(10)),
                       burnout_active=dict(burnout=D(100), burnout_active=True))

    def test_codes_and_reasons_match_the_direct_service_in_every_state(self):
        for name in ("fresh", "no_energy", "low_energy_study_ok", "burnout_active", "hospitalized", "critical"):
            for aid in PLAYER_ACTIONS:
                a, b = self._twin(f"a_{name}_{aid}"), self._twin(f"b_{name}_{aid}")
                self._prepare(a, name)
                self._prepare(b, name)
                predicted = registry.check_action(a.pk, aid)
                via_registry = registry.execute_action(a.pk, aid)
                direct = perform_action(b.pk, Action(aid))
                self.assertEqual((via_registry.ok, via_registry.code), (direct.ok, direct.code), (name, aid))
                self.assertEqual(via_registry.detail.get("reasons"), direct.detail.get("reasons"), (name, aid))
                self.assertEqual((predicted.available, predicted.code), (direct.ok, direct.code), (name, aid))
                self.assertEqual(list(predicted.blocked_by), direct.detail.get("reasons", []), (name, aid))

    def test_hospitalization_follows_the_balance_parameter(self):
        """A lista de ações bloqueadas na hospitalização é configuração do 04: o registro a segue, não a copia."""
        change_health(self.player.pk, -D(100), "test")
        self.assertEqual(avail(self.player.pk)["leisure"].code, "HOSPITALIZED")
        with override_settings(POLIS_BALANCE={"hospitalization_blocked_actions": ("work",)}):
            a = avail(self.player.pk)
            self.assertEqual((a["leisure"].available, a["work"].code), (True, "HOSPITALIZED"))
            self.assertTrue(registry.execute_action(self.player.pk, "leisure").ok)

    def test_energy_boundary_exactly_the_cost_is_enough(self):
        """Energia == custo basta (04 §2.2); um centésimo de milionésimo a menos, não: igual ao serviço direto."""
        for aid, cost in (("work", 20), ("study", 10), ("leisure", 10)):
            for energy, ok in ((D(cost), True), (D(cost) - D("0.000001"), False)):
                a, b = self.new_player(f"e{aid}{ok}a"), self.new_player(f"e{aid}{ok}b")
                self.set_state(a, energy=energy)
                self.set_state(b, energy=energy)
                predicted = registry.check_action(a.pk, aid)
                self.assertEqual(predicted.available, ok, (aid, energy))
                self.assertEqual(registry.execute_action(a.pk, aid).ok, ok, (aid, energy))
                self.assertEqual(perform_action(b.pk, Action(aid)).ok, ok, (aid, energy))

    def test_start_travel_without_destination_is_invalid_destination_even_while_traveling(self):
        """Comportamento anterior da extração preservado: sem destino, INVALID_DESTINATION (antes de ALREADY_TRAVELING)."""
        self.assertEqual(travel.start_travel(self.player.pk, None).code, "INVALID_DESTINATION")
        self.go(self.far())
        self.assertEqual(travel.start_travel(self.player.pk, None).code, "INVALID_DESTINATION")
        self.assertEqual(travel.start_travel(self.player.pk, 10 ** 9).code, "INVALID_DESTINATION")

    def test_travel_is_available_in_every_player_state(self):
        """GD 2026-10-07: nenhum estado impede partir."""
        change_health(self.player.pk, -D(100), "test")
        self.set_state(energy=D(0), burnout=D(100), burnout_active=True)
        self.assertTrue(avail(self.player.pk)["travel"].available)
        self.assertTrue(registry.execute_action(self.player.pk, "travel", self.far().pk).ok)


class ExecutionEquivalenceTests(TravelTestCase):
    def test_player_actions_give_the_same_result_as_the_direct_service(self):
        for aid in PLAYER_ACTIONS:
            a, b = self.new_player(f"x{aid}"), self.new_player(f"y{aid}")
            via, direct = registry.execute_action(a.pk, aid), perform_action(b.pk, Action(aid))
            self.assertEqual((via.ok, via.code), (direct.ok, direct.code))
            self.assertEqual(via.detail, direct.detail, aid)
            sa, sb = self.state(a), self.state(b)
            self.assertEqual((sa.energy, sa.burnout, sa.last_work_at), (sb.energy, sb.burnout, sb.last_work_at))

    def test_travel_gives_the_same_result_as_start_travel(self):
        a, b = self.new_player("ta"), self.new_player("tb")
        dest = self.far(self.location(a))
        via, direct = registry.execute_action(a.pk, "travel", dest.pk), travel.start_travel(b.pk, dest.pk)
        self.assertEqual((via.ok, via.code), (direct.ok, direct.code))
        strip = lambda d: {k: v for k, v in d.items() if k != "journey_id"}
        self.assertEqual(strip(via.detail), strip(direct.detail))
        ja, jb = Journey.objects.get(player=a), Journey.objects.get(player=b)
        self.assertEqual((ja.origin_id, ja.destination_id, ja.departed_at, ja.arrives_at, ja.cost, ja.charged),
                         (jb.origin_id, jb.destination_id, jb.departed_at, jb.arrives_at, jb.cost, jb.charged))

    def test_travel_via_registry_still_has_no_energy_or_burnout_cost(self):
        before = self.state()
        registry.execute_action(self.player.pk, "travel", self.far().pk)
        after = self.state()
        self.assertEqual((after.energy, after.burnout), (before.energy, before.burnout))

    def test_execution_goes_through_the_real_services(self):
        with mock.patch("players.registry.services.perform_action", wraps=perform_action) as spy:
            registry.execute_action(self.player.pk, "work")
        spy.assert_called_once_with(self.player.pk, Action.WORK)
        with mock.patch("travel.registration.services.start_travel", wraps=travel.start_travel) as spy:
            registry.execute_action(self.player.pk, "travel", self.far().pk)
        spy.assert_called_once_with(self.player.pk, self.far().pk)


class CostPreviewTests(TravelTestCase):
    def test_energy_and_burnout_come_from_balance_and_rules(self):
        a = avail(self.player.pk)
        bal = get_balance()
        self.assertEqual([a[x].preview["energy_cost"] for x in ("work", "study", "leisure")],
                         [bal.energy_cost_work, bal.energy_cost_study, bal.energy_cost_leisure])
        self.assertEqual([a[x].preview["energy_cost"] for x in ("work", "study", "leisure")], [D(20), D(10), D(10)])
        for x in PLAYER_ACTIONS:
            bc = a[x].preview["burnout_change"]
            self.assertIsInstance(bc, Explained)
            self.assertEqual(bc, rules.burnout_change(Action(x), D(1), bal))
        self.assertEqual([a[x].preview["burnout_change"].value for x in PLAYER_ACTIONS], [D(5), D(3), D(-10)])

    def test_preview_follows_balance_overrides(self):
        with override_settings(POLIS_BALANCE={"energy_cost_work": 30}):
            self.assertEqual(avail(self.player.pk)["work"].preview["energy_cost"], D(30))

    def test_preview_equals_what_execution_then_charges(self):
        for x in PLAYER_ACTIONS:
            p = self.new_player(f"pv{x}")
            preview = avail(p.pk)[x].preview
            r = registry.execute_action(p.pk, x)
            self.assertEqual(r.detail["energy_spent"], preview["energy_cost"])
            self.assertEqual(r.detail["burnout_change"], preview["burnout_change"])

    def test_preview_shows_cost_even_when_the_action_is_refused(self):
        self.set_state(energy=D(0))
        a = avail(self.player.pk)["work"]
        self.assertEqual((a.available, a.code, a.preview["energy_cost"]), (False, "INSUFFICIENT_ENERGY", D(20)))

    def test_travel_preview_is_the_quote_with_breakdowns(self):
        dest = self.far()
        c = registry.check_action(self.player.pk, "travel", dest.pk)
        q = travel.quote_travel(self.location(), dest, self.clk.now(), self.player)
        self.assertEqual((c.preview["travel_time"], c.preview["travel_cost"]), (q.time, q.cost))
        self.assertEqual((c.preview["duration_seconds"], c.preview["amount"]), (q.duration_seconds, q.amount))
        self.assertIsInstance(c.preview["travel_cost"], Explained)
        self.assertEqual(c.preview["travel_time"].computed_at, self.clk.now())

    def test_travel_money_is_calculated_not_charged_without_a_payment_system(self):
        c = registry.check_action(self.player.pk, "travel", self.far().pk)
        self.assertGreater(c.preview["amount"], 0)
        self.assertEqual(c.preview["payment"], "NO_PAYMENT_SYSTEM")
        r = registry.execute_action(self.player.pk, "travel", self.far().pk)
        self.assertEqual((r.detail["payment"], Journey.objects.get().charged), ("NO_PAYMENT_SYSTEM", False))

    def test_payment_status_variants(self):
        travel.register_payment_handler("t", lambda p, amount, ctx: True)
        self.assertEqual(registry.check_action(self.player.pk, "travel", self.far().pk).preview["payment"], "WOULD_CHARGE")
        with override_settings(POLIS_GEOGRAPHY={"travel_cost_per_unit": 0}):
            self.assertEqual(registry.check_action(self.player.pk, "travel", self.far().pk).preview["payment"], "NOT_REQUIRED")

    def test_travel_preview_matches_the_executed_journey(self):
        dest = self.far()
        pv = registry.check_action(self.player.pk, "travel", dest.pk).preview
        r = registry.execute_action(self.player.pk, "travel", dest.pk)
        self.assertEqual((r.detail["duration_seconds"], r.detail["cost"], r.detail["travel_time"], r.detail["travel_cost"]),
                         (pv["duration_seconds"], pv["amount"], pv["travel_time"], pv["travel_cost"]))

    def test_travel_modifiers_extension_is_reflected_in_the_preview(self):
        dest = self.far()
        base = registry.check_action(self.player.pk, "travel", dest.pk).preview
        travel.register_travel_modifier("vehicle", lambda p, o, d: travel.TravelModifier("vehicle", D("0.5"), D("0.3")))
        mod = registry.check_action(self.player.pk, "travel", dest.pk).preview
        self.assertLess(mod["duration_seconds"], base["duration_seconds"])
        self.assertIn("modifier:vehicle", [s.key for s in mod["travel_time"].steps])


class ExtensionMechanismsStillApplyTests(TravelTestCase):
    """Hooks e provedores de outros sistemas continuam efetivos pelo registro (sem caminho paralelo)."""

    def test_action_hooks_run_when_executed_through_the_registry(self):
        hooks.register_action_hook("zz_probe", lambda ctx: {"seen": ctx.action.value})
        self.addCleanup(hooks.unregister_action_hook, "zz_probe")
        r = registry.execute_action(self.player.pk, "study")
        self.assertEqual(r.detail["hooks"]["zz_probe"], {"seen": "study"})

    def test_a_failing_hook_undoes_the_action_atomically(self):
        def boom(ctx):
            raise RuntimeError("falha")
        hooks.register_action_hook("zz_boom", boom)
        self.addCleanup(hooks.unregister_action_hook, "zz_boom")
        before = self.state()
        with self.assertRaises(RuntimeError):
            registry.execute_action(self.player.pk, "work")
        after = self.state()
        self.assertEqual((after.energy, after.burnout, after.last_work_at), (before.energy, before.burnout, before.last_work_at))

    def test_a_block_provider_is_visible_in_availability_and_enforced_in_execution(self):
        hooks.register_block_provider("zz_block", lambda p, a, now, act: "EMPLOYER_CLOSED" if a is Action.WORK else None)
        self.addCleanup(hooks.unregister_block_provider, "zz_block")
        a = avail(self.player.pk)
        self.assertEqual((a["work"].available, a["work"].code, a["work"].blocked_by), (False, "EMPLOYER_CLOSED", ("EMPLOYER_CLOSED",)))
        self.assertTrue(a["study"].available)
        r = registry.execute_action(self.player.pk, "work")
        self.assertEqual((r.code, r.detail["reasons"]), ("EMPLOYER_CLOSED", ["EMPLOYER_CLOSED"]))

    def test_presence_block_while_traveling_through_the_registry(self):
        self.go(self.far())
        a = avail(self.player.pk)
        self.assertEqual((a["work"].code, a["study"].code), ("TRAVELING", "TRAVELING"))
        self.assertTrue(a["leisure"].available)
        self.assertEqual(registry.execute_action(self.player.pk, "work").code, "TRAVELING")
        self.assertTrue(registry.execute_action(self.player.pk, "leisure").ok)

    def test_travel_atomicity_if_the_payment_handler_fails(self):
        def boom(player, amount, ctx):
            raise RuntimeError("falha de pagamento")
        travel.register_payment_handler("boom", boom)
        with self.assertRaises(RuntimeError):
            registry.execute_action(self.player.pk, "travel", self.far().pk)
        self.assertEqual(Journey.objects.count(), 0)

    def test_insufficient_funds_comes_from_the_payment_handler_at_execution(self):
        travel.register_payment_handler("poor", lambda p, amount, ctx: False)
        self.assertTrue(registry.check_action(self.player.pk, "travel", self.far().pk).available)   # consultivo
        r = registry.execute_action(self.player.pk, "travel", self.far().pk)
        self.assertEqual((r.ok, r.code), (False, "INSUFFICIENT_FUNDS"))
        self.assertEqual(Journey.objects.count(), 0)


class LazyAndQueryCostTests(TravelTestCase):
    def _queries(self, fn):
        with CaptureQueriesContext(connection) as ctx:
            fn()
        return len(ctx.captured_queries)

    def test_availability_adds_a_constant_cost_on_top_of_the_lazy_sync(self):
        """O catch-up lazy (existente) custa o que custar; o registro soma um custo FIXO, independente do tempo decorrido."""
        from players.services import locked_player

        def sync(player):
            def run():
                with locked_player(player.pk):
                    pass
            return run

        def overhead(label):
            # Dois jogadores gêmeos com o MESMO trabalho lazy pendente: um sincroniza, o outro consulta a disponibilidade.
            a, b = self.new_player(f"{label}a"), self.new_player(f"{label}b")
            self.clk.advance(seconds=self.elapsed)
            return self._queries(lambda: registry.available_actions(a.pk)) - self._queries(sync(b))

        self.elapsed = 600
        short = overhead("s")
        self.elapsed = 30 * 86400
        self.assertEqual(overhead("l"), short)

    def test_availability_does_not_scale_with_the_number_of_players_or_registered_checks(self):
        base = self._queries(lambda: registry.available_actions(self.player.pk))
        for i in range(5):
            self.new_player(f"extra{i}")
        self.assertEqual(self._queries(lambda: registry.available_actions(self.player.pk)), base)

    def test_one_synchronized_session_for_all_actions(self):
        """Todas as ações num acesso só: bem menos queries que consultar uma a uma."""
        one_by_one = self._queries(lambda: [registry.check_action(self.player.pk, a) for a in ("work", "study", "leisure", "travel")])
        together = self._queries(lambda: registry.available_actions(self.player.pk))
        self.assertLess(together, one_by_one)

    def test_checking_is_idempotent_and_changes_no_gameplay_state(self):
        before = self.state()
        for _ in range(3):
            registry.available_actions(self.player.pk)
            registry.check_action(self.player.pk, "travel", self.far().pk)
        after = self.state()
        for f in ("energy", "health", "nutrition", "burnout", "processed_until", "last_work_at"):
            self.assertEqual(getattr(before, f), getattr(after, f), f)
        self.assertEqual(Journey.objects.count(), 0)

    def test_availability_after_elapsed_time_equals_executing_after_it(self):
        self.set_state(energy=D(0))
        self.clk.advance(seconds=6 * HOUR)       # regenera por ciclos de forma lazy
        a = avail(self.player.pk)["work"]
        r = registry.execute_action(self.player.pk, "work")
        self.assertEqual((a.available, a.code), (r.ok, r.code))
        self.assertTrue(r.ok)
