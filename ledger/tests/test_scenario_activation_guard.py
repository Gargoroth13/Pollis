"""
Estado do cenário (`LedgerScenario.active`) pelo ORM (design/24 §24.11): ativar só por `services.activate_scenario`, que valida
as dotações exigidas; o ORM (instância, queryset, lote, criação) recusa a transição para ativo e nunca cria cenário ativo.
Desativar é livre, mas passa pelo protocolo de bloqueio (todos os cenários primeiro). Concorrência: `test_scenario_concurrency.py`.
"""
import ast
import pathlib
from contextlib import contextmanager
from unittest import mock

from django.db import connection
from django.db.models import Case, Value, When

from ledger import models as ledger_models
from ledger import services as ledger
from ledger.models import (GrantLineLockedError, LedgerImmutableError, LedgerScenario, ScenarioActivationForbiddenError,
                           ScenarioGrantLine, _activation_permit)

from .base import LedgerTestCase


class ScenarioActivationGuardCase(LedgerTestCase):
    def setUp(self):
        super().setUp()
        ledger.create_scenario("ok", {"union": 100})
        ledger.create_scenario("ok2", {"union": 200})
        ledger.create_scenario("incompleto", {"union": None})       # dotação exigida NÃO especificada: não pode ficar ativo
        self.ok, self.ok2, self.bad = (LedgerScenario.objects.get(name=n) for n in ("ok", "ok2", "incompleto"))

    def active(self):
        return sorted(LedgerScenario.objects.filter(active=True).values_list("name", flat=True))

    def assertForbidden(self, call, expect_active=()):
        with self.assertRaises(ScenarioActivationForbiddenError) as cm:
            call()
        self.assertEqual(cm.exception.code, "SCENARIO_ACTIVATION_FORBIDDEN")
        self.assertEqual(self.active(), sorted(expect_active), "a recusa não pode alterar o cenário ativo")


class OrmCannotActivateAScenario(ScenarioActivationGuardCase):
    def test_queryset_update_paths(self):
        qs = LedgerScenario.objects
        self.assertForbidden(lambda: qs.filter(pk=self.bad.pk).update(active=True))
        self.assertForbidden(lambda: qs.all().update(active=True))
        self.assertForbidden(lambda: qs.filter(pk=self.ok.pk).update(active=Value(True)))              # expressão
        self.assertForbidden(lambda: qs.filter(pk=self.ok.pk).update(
            active=Case(When(name="ok", then=Value(True)), default=Value(False))))
        self.assertForbidden(lambda: qs.filter(pk=self.ok.pk).update(active=True, created_at=5))
        self.assertForbidden(lambda: LedgerScenario._base_manager.filter(pk=self.bad.pk).update(active=True))
        self.assertEqual(LedgerScenario.objects.get(pk=self.ok.pk).created_at, self.ok.created_at)

    def test_instance_save_paths(self):
        for scenario in (self.bad, self.ok):
            scenario.active = True
            self.assertForbidden(scenario.save)
            self.assertForbidden(lambda s=scenario: s.save(update_fields=["active"]))
            self.assertForbidden(lambda s=scenario: s.save(force_update=True))
        # instância "nova" com pk explícito de um cenário existente vira UPDATE no Django: também é uma ativação
        self.assertForbidden(LedgerScenario(pk=self.bad.pk, name="incompleto", active=True).save)

    def test_creation_never_yields_an_active_scenario(self):
        self.assertForbidden(lambda: LedgerScenario.objects.create(name="novo", active=True))
        self.assertForbidden(LedgerScenario(name="novo2", active=True).save)
        self.assertForbidden(lambda: LedgerScenario.objects.get_or_create(name="novo3", defaults={"active": True}))
        self.assertForbidden(lambda: LedgerScenario.objects.update_or_create(name="incompleto", defaults={"active": True}))
        self.assertForbidden(lambda: LedgerScenario.objects.bulk_create([LedgerScenario(name="lote", active=True)]))
        self.assertFalse(LedgerScenario.objects.filter(name__in=["novo", "novo2", "novo3", "lote"]).exists())

    def test_bulk_update_and_upsert_paths(self):
        self.bad.active = True
        self.assertForbidden(lambda: LedgerScenario.objects.bulk_update([self.bad], ["active"]))
        with self.assertRaises(LedgerImmutableError):               # upsert em lote poderia ativar/renomear por baixo
            LedgerScenario.objects.bulk_create([LedgerScenario(name="incompleto", active=True)], update_conflicts=True,
                                               update_fields=["active"], unique_fields=["name"])
        self.assertEqual(self.active(), [])

    def test_save_update_fields_that_exclude_active_do_not_activate(self):
        self.ok.active = True                                        # só em memória
        self.ok.created_at = 7
        self.ok.save(update_fields=["created_at"])
        self.assertEqual((self.active(), LedgerScenario.objects.get(pk=self.ok.pk).created_at), ([], 7))

    def test_creating_an_inactive_scenario_stays_free(self):
        sc = LedgerScenario.objects.create(name="livre")
        LedgerScenario.objects.bulk_create([LedgerScenario(name="lote-livre")])
        self.assertEqual((sc.active, self.active()), (False, []))

    def test_the_activation_permit_belongs_to_one_scenario_and_ends_with_its_block(self):
        with _activation_permit(self.ok.pk):
            LedgerScenario.objects.filter(pk=self.ok.pk).update(active=True)       # o autorizado, nesse bloco
            self.assertForbidden(lambda: LedgerScenario.objects.filter(pk=self.ok2.pk).update(active=True), ["ok"])
            self.assertForbidden(lambda: LedgerScenario.objects.all().update(active=True), ["ok"])
        LedgerScenario.objects.filter(pk=self.ok.pk).update(active=False)
        self.assertForbidden(lambda: LedgerScenario.objects.filter(pk=self.ok.pk).update(active=True))     # fora do bloco


class ActivationThroughTheServiceStillValidates(ScenarioActivationGuardCase):
    def test_service_refuses_an_incomplete_scenario_and_the_orm_cannot_get_around_it(self):
        res = ledger.activate_scenario("incompleto", ["union"])
        self.assertEqual((res.ok, res.code, res.detail["missing"]), (False, "SCENARIO_GRANT_UNSPECIFIED", ["union"]))
        self.assertEqual(self.active(), [])
        self.bad.active = True
        self.assertForbidden(self.bad.save)
        self.assertEqual(self.active(), [])
        ledger.set_grant_line("incompleto", "union", 0)              # zero explícito vale
        self.assertTrue(ledger.activate_scenario("incompleto", ["union"]).ok)
        self.assertEqual(self.active(), ["incompleto"])

    def test_service_switches_the_active_scenario_and_keeps_exactly_one(self):
        self.assertTrue(ledger.activate_scenario("ok", ["union"]).ok)
        self.assertTrue(ledger.activate_scenario("ok2", ["union"]).ok)
        self.assertEqual(self.active(), ["ok2"])
        self.assertTrue(ledger.activate_scenario("ok2", ["union"]).ok)           # idempotente
        self.assertEqual(self.active(), ["ok2"])
        self.assertEqual(ledger.activate_scenario("nao-existe", []).code, "SCENARIO_NOT_FOUND")
        self.assertEqual(self.active(), ["ok2"])
        # a recusa por dotação faltante não desativa o cenário que já estava ativo
        self.assertEqual(ledger.activate_scenario("incompleto", ["union"]).code, "SCENARIO_GRANT_UNSPECIFIED")
        self.assertEqual(self.active(), ["ok2"])

    def test_a_stale_instance_is_refused(self):
        self.assertTrue(ledger.activate_scenario("ok", ["union"]).ok)
        stale = LedgerScenario.objects.get(pk=self.ok.pk)
        self.assertTrue(ledger.activate_scenario("ok2", ["union"]).ok)
        self.assertForbidden(stale.save, ["ok2"])


class DeactivationIsFreeButStillProtected(ScenarioActivationGuardCase):
    def setUp(self):
        super().setUp()
        self.assertTrue(ledger.activate_scenario("ok", ["union"]).ok)

    def reactivate(self):
        self.assertTrue(ledger.activate_scenario("ok", ["union"]).ok)

    def test_every_deactivation_path_works(self):
        LedgerScenario.objects.filter(pk=self.ok.pk).update(active=False)
        self.assertEqual(self.active(), [])
        self.reactivate()
        sc = LedgerScenario.objects.get(pk=self.ok.pk)
        sc.active = False
        sc.save()
        self.assertEqual(self.active(), [])
        self.reactivate()
        sc = LedgerScenario.objects.get(pk=self.ok.pk)
        sc.active = False
        LedgerScenario.objects.bulk_update([sc], ["active"])
        self.assertEqual(self.active(), [])
        self.reactivate()
        LedgerScenario.objects.filter(pk=self.ok.pk).update(active=Value(False))
        self.assertEqual(self.active(), [])

    def test_keeping_the_active_one_active_is_a_no_op_and_allowed(self):
        LedgerScenario.objects.filter(pk=self.ok.pk).update(active=True)
        sc = LedgerScenario.objects.get(pk=self.ok.pk)
        sc.save()
        sc.save(update_fields=["active"])
        LedgerScenario.objects.bulk_update([sc], ["active"])
        self.assertEqual(self.active(), ["ok"])

    def test_rename_and_delete_rules_are_unchanged(self):
        self.assertTrue(ledger.grant_scenario_allocation(
            "ok", ledger.union_account().pk, 100, role="union").ok)
        sc = LedgerScenario.objects.get(pk=self.ok.pk)
        sc.name = "renomeado"
        with self.assertRaises(GrantLineLockedError):
            sc.save()
        with self.assertRaises(GrantLineLockedError):
            LedgerScenario.objects.filter(pk=sc.pk).update(name="renomeado")
        with self.assertRaises(GrantLineLockedError):
            LedgerScenario.objects.filter(pk=sc.pk).delete()
        # renomear com pk explícito numa instância "nova" também é UPDATE: precisa passar pela mesma guarda
        with self.assertRaises(GrantLineLockedError):
            LedgerScenario(pk=sc.pk, name="outro", active=True).save()
        self.assertEqual(self.active(), ["ok"])


class ExplicitPkWriteOnAGrantLineIsStillGuarded(ScenarioActivationGuardCase):
    """Mesma classe de contorno: instância nova com pk de linha existente vira UPDATE no Django."""

    def test_new_instance_with_the_pk_of_a_used_line_cannot_change_it(self):
        self.assertTrue(ledger.activate_scenario("ok", ["union"]).ok)
        self.assertTrue(ledger.grant_scenario_allocation(
            "ok", ledger.union_account().pk, 100, role="union").ok)
        line = ScenarioGrantLine.objects.get(scenario=self.ok, role="union")
        empty = ledger.create_scenario("vazio", {})
        with self.assertRaises(GrantLineLockedError):
            ScenarioGrantLine(pk=line.pk, scenario=self.ok, role="union", amount=999).save()
        # mover a linha usada para outro cenário (par sem histórico): o "novo" não revela o par de origem
        with self.assertRaises(GrantLineLockedError):
            ScenarioGrantLine(pk=line.pk, scenario=empty, role="union", amount=100).save()
        self.assertEqual(list(ScenarioGrantLine.objects.filter(pk=line.pk).values_list("scenario__name", "amount")),
                         [("ok", 100)])


class TheActivationPermitIsAnInternalMechanismNotApi(ScenarioActivationGuardCase):
    """
    Fronteira de confiança: a API pública para ativar um cenário é `activate_scenario()`, que valida as dotações exigidas sob os
    bloqueios globais. `_activation_permit` é mecanismo INTERNO desse fluxo (privado, sem validação própria). A recusa do ORM
    evita a ativação acidental pelos caminhos comuns; ela NÃO é uma defesa contra código Python que use o mecanismo interno de
    propósito, e por isso o fluxo é garantido por convenção + este teste: um só ponto de uso, dentro de `activate_scenario`.
    """

    PACKAGE = pathlib.Path(ledger.__file__).resolve().parent

    def test_the_permit_is_private_and_not_exposed_by_the_public_modules(self):
        self.assertFalse(hasattr(ledger_models, "activation_permit"))
        self.assertFalse(hasattr(ledger, "activation_permit"))
        self.assertTrue(callable(ledger_models._activation_permit))

    def test_the_only_production_use_is_inside_activate_scenario(self):
        users = []
        for path in sorted(self.PACKAGE.rglob("*.py")):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            if "_activation_permit" in path.read_text():
                users.append(path.name)
        self.assertEqual(users, ["models.py", "services.py"])          # definição e único consumidor
        tree = ast.parse((self.PACKAGE / "services.py").read_text())
        activate = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "activate_scenario")
        inside = {id(n) for n in ast.walk(activate)}
        uses = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "_activation_permit"]
        self.assertEqual(len(uses), 1)
        self.assertIn(id(uses[0]), inside, "o mecanismo interno só pode ser usado dentro de activate_scenario")

    @contextmanager
    def spy_on_the_permit(self):
        calls = []
        real = ledger._activation_permit

        @contextmanager
        def spy(pk):
            have = dict(ScenarioGrantLine.objects.filter(scenario_id=pk).values_list("role", "amount"))
            calls.append({"pk": pk, "lines": have, "in_atomic_block": connection.in_atomic_block})
            with real(pk):
                yield
        with mock.patch.object(ledger, "_activation_permit", spy):
            yield calls

    def test_the_service_validates_the_required_grants_before_it_grants_the_permit(self):
        with self.spy_on_the_permit() as calls:
            refused = ledger.activate_scenario("incompleto", ["union"])
            self.assertEqual((refused.ok, refused.code), (False, "SCENARIO_GRANT_UNSPECIFIED"))
            self.assertEqual(calls, [], "sem dotação exigida explícita a permissão nem chega a ser concedida")
            self.assertEqual(ledger.activate_scenario("nao-existe", ["union"]).code, "SCENARIO_NOT_FOUND")
            self.assertEqual(calls, [])
            self.assertTrue(ledger.activate_scenario("ok", ["union"]).ok)
        self.assertEqual(calls, [{"pk": self.ok.pk, "lines": {"union": 100}, "in_atomic_block": True}])
        self.assertEqual(self.active(), ["ok"])

    def test_the_service_keeps_validating_every_required_role(self):
        with self.spy_on_the_permit() as calls:
            res = ledger.activate_scenario("ok", ["union", "militia_bank"])        # militia_bank não está na linha de "ok"
            self.assertEqual((res.ok, res.code, res.detail["missing"]), (False, "SCENARIO_GRANT_UNSPECIFIED", ["militia_bank"]))
        self.assertEqual((calls, self.active()), ([], []))
