"""
Concorrência da configuração de cenários (design/24 §24.11): alterar uma linha de dotação, ativar cenários e emitir dotações
seguem UM protocolo de travamento (`services._lock_scenarios`), sem deadlock e sem emissão que contradiga a linha.

Dois grupos:
  * PROPRIEDADES (rodam em SQLite e em PostgreSQL): seja qual for a ordem em que a corrida se resolva, o que foi emitido
    coincide com a configuração final, há no máximo um cenário ativo e a auditoria passa.
  * ORDEM ESTRITA (só PostgreSQL, onde `SELECT ... FOR UPDATE` bloqueia de verdade): uma thread segura o bloqueio no meio da
    operação e o teste confere que a outra espera e termina DEPOIS. Em SQLite esses testes são pulados (o banco serializa as
    escritas de outra forma), e o relatório diz isso: não há cobertura de PostgreSQL quando eles não rodam.
"""
import threading
import time
import unittest
from collections import Counter
from unittest import mock

from django.db import OperationalError, close_old_connections, connection
from django.test import TransactionTestCase

from ledger import models as ledger_models
from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import AccountKind
from ledger.models import Entry, GrantLineLockedError, LedgerScenario, ScenarioGrantLine

HOLD = 1.2          # quanto tempo a thread "lenta" segura o bloqueio nos testes de ordem estrita (segundos)
ON_PG = connection.vendor == "postgresql"


def _attempt(fn):
    """SQLite pode devolver 'database is locked': tenta de novo. Em PostgreSQL NÃO mascara nada (um deadlock tem de aparecer)."""
    if ON_PG:
        return fn()
    for _ in range(80):
        try:
            return fn()
        except OperationalError:
            time.sleep(0.02)
    raise AssertionError("não conseguiu executar após várias tentativas")


class Job:
    """Uma thread que roda `fn`, guarda resultado ou exceção e os instantes de início e fim (monotônicos)."""

    def __init__(self, fn, barrier=None, name=None):
        self.result = self.error = self.started = self.ended = None
        self._fn, self._barrier = fn, barrier
        self.thread = threading.Thread(target=self._run, name=name)

    def _run(self):
        try:
            if self._barrier is not None:
                self._barrier.wait(timeout=10)
            self.started = time.monotonic()
            try:
                self.result = _attempt(self._fn)
            except ledger.LedgerRefusal as refusal:
                self.result = refusal.result
            except Exception as exc:                  # noqa: BLE001 - o teste confere `error is None`
                self.error = exc
            self.ended = time.monotonic()
        finally:
            close_old_connections()
            connection.close()

    def start(self):
        self.thread.start()
        return self

    def join(self):
        self.thread.join(timeout=60)
        assert not self.thread.is_alive(), "thread presa (deadlock?)"
        return self


def run_together(*fns):
    barrier = threading.Barrier(len(fns))
    jobs = [Job(fn, barrier).start() for fn in fns]
    for j in jobs:
        j.join()
    for j in jobs:      # a recusa da guarda de imutabilidade da linha é um desfecho válido da corrida
        assert j.error is None or isinstance(j.error, GrantLineLockedError), repr(j.error)
    return jobs


class ScenarioConcurrencyBase(TransactionTestCase):
    def active_names(self):
        return list(LedgerScenario.objects.filter(active=True).values_list("name", flat=True))

    def emitted(self, account):
        return sum(Entry.objects.filter(nature="scenario_grant", to_account=account).values_list("amount", flat=True))

    def assertLedgerClean(self):
        rep = audit_ledger()
        self.assertTrue(rep.ok, rep.findings)
        self.assertLessEqual(len(self.active_names()), 1)


class ScenarioPropertyTests(ScenarioConcurrencyBase):
    def test_line_change_versus_grant_never_emits_a_value_that_contradicts_the_final_line(self):
        outcomes = Counter()
        for n in range(8):
            name = f"ln{n}"
            bank = ledger.get_or_create_account(AccountKind.MILITIA_BANK, 100 + n)
            ledger.create_scenario(name, {"militia_bank": 500})
            self.assertTrue(ledger.activate_scenario(name, ["militia_bank"]).ok)
            grant, change = run_together(
                lambda: ledger.grant_scenario_allocation(name, bank.pk, 500, role="militia_bank"),
                lambda: ledger.set_grant_line(name, "militia_bank", 900))
            line = ScenarioGrantLine.objects.get(scenario__name=name, role="militia_bank").amount
            emitted = self.emitted(bank)
            if emitted:        # a dotação foi primeiro: a linha ficou travada no valor emitido
                outcomes["grant_first"] += 1
                self.assertEqual((emitted, line, grant.result.ok), (500, 500, True))
                self.assertEqual(change.result.code, "GRANT_LINE_LOCKED")
            else:              # a alteração foi primeiro: a dotação de 500 diverge da linha de 900
                outcomes["change_first"] += 1
                self.assertEqual((line, grant.result.code), (900, "GRANT_AMOUNT_MISMATCH"))
            self.assertLedgerClean()
        self.assertEqual(sum(outcomes.values()), 8, outcomes)

    def _orm_mutation_versus_grant(self, mutate, refused_when_grant_first, label):
        outcomes = Counter()
        for n in range(8):
            name = f"{label}{n}"
            bank = ledger.get_or_create_account(AccountKind.MILITIA_BANK, 300 + n)
            ledger.create_scenario(name, {"militia_bank": 500})
            self.assertTrue(ledger.activate_scenario(name, ["militia_bank"]).ok)
            grant, change = run_together(
                lambda: ledger.grant_scenario_allocation(name, bank.pk, 500, role="militia_bank"),
                lambda: mutate(name))
            rows = list(ScenarioGrantLine.objects.filter(scenario__name=name, role="militia_bank").values_list("amount", flat=True))
            if self.emitted(bank):             # a dotação foi primeiro: a linha continua exatamente como foi emitida
                outcomes["grant_first"] += 1
                self.assertEqual((rows, grant.result.ok), ([500], True))
                self.assertIsInstance(change.error, GrantLineLockedError, change.result)
            else:                              # a mutação foi primeiro: a dotação vê a configuração já mudada
                outcomes["mutation_first"] += 1
                self.assertIsNone(change.error)
                self.assertEqual(rows, refused_when_grant_first[0])
                self.assertEqual(grant.result.code, refused_when_grant_first[1])
            self.assertLedgerClean()
        self.assertEqual(sum(outcomes.values()), 8, outcomes)

    def test_orm_update_versus_grant_never_changes_a_line_that_already_emitted(self):
        self._orm_mutation_versus_grant(
            lambda name: ScenarioGrantLine.objects.filter(scenario__name=name).update(amount=900),
            ([900], "GRANT_AMOUNT_MISMATCH"), "ou")

    def test_orm_delete_versus_grant_never_deletes_a_line_that_already_emitted(self):
        self._orm_mutation_versus_grant(
            lambda name: ScenarioGrantLine.objects.filter(scenario__name=name).delete(),
            ([], "SCENARIO_GRANT_UNSPECIFIED"), "od")

    def test_two_moves_or_a_move_and_a_delete_with_an_activation_end_consistent(self):
        """Duas mutações da MESMA linha (ainda sem dotação) + uma ativação, em paralelo, várias rodadas."""
        for n in range(6):
            d1, d2, d3 = (f"p{n}{k}" for k in (1, 2, 3))
            ledger.create_scenario(d1, {})
            ledger.create_scenario(d2, {"militia_bank": 500})
            ledger.create_scenario(d3, {})
            line = ScenarioGrantLine.objects.get(scenario__name=d2)
            second = ((lambda: ScenarioGrantLine.objects.filter(pk=line.pk).update(scenario=LedgerScenario.objects.get(name=d3)))
                      if n % 2 == 0 else (lambda: ScenarioGrantLine.objects.filter(pk=line.pk).delete()))
            run_together(
                lambda: ScenarioGrantLine.objects.filter(pk=line.pk).update(scenario=LedgerScenario.objects.get(name=d1)),
                second,
                lambda: ledger.activate_scenario(d1, []))
            where = list(ScenarioGrantLine.objects.filter(pk=line.pk).values_list("scenario__name", flat=True))
            self.assertIn(where, ([d1], [d3], []) if n % 2 == 0 else ([d1], []), (n, where))
            self.assertEqual(self.active_names(), [d1])
            self.assertLedgerClean()

    def test_concurrent_activations_never_deadlock_and_leave_exactly_one_active(self):
        names = [f"act{n}" for n in range(6)]
        for name in names:
            ledger.create_scenario(name, {"union": 1})
        for _ in range(4):
            jobs = run_together(*[lambda nm=nm: ledger.activate_scenario(nm, ["union"]) for nm in names])
            self.assertTrue(all(j.result.ok for j in jobs), [j.result for j in jobs])
            self.assertEqual(len(self.active_names()), 1, self.active_names())
            self.assertIn(self.active_names()[0], names)
        self.assertLedgerClean()

    def test_activation_versus_grant_in_flight(self):
        outcomes = Counter()
        for n in range(6):
            a, b = f"ga{n}", f"gb{n}"
            bank = ledger.get_or_create_account(AccountKind.MILITIA_BANK, 200 + n)
            for name in (a, b):
                ledger.create_scenario(name, {"militia_bank": 40})
            self.assertTrue(ledger.activate_scenario(a, ["militia_bank"]).ok)
            grant, act = run_together(
                lambda: ledger.grant_scenario_allocation(a, bank.pk, 40, role="militia_bank"),
                lambda: ledger.activate_scenario(b, ["militia_bank"]))
            self.assertTrue(act.result.ok, act.result)
            self.assertEqual(self.active_names(), [b])
            if grant.result.ok:
                outcomes["grant_first"] += 1
                self.assertEqual(self.emitted(bank), 40)
            else:
                outcomes["activation_first"] += 1
                self.assertEqual(grant.result.code, "SCENARIO_NOT_ACTIVE")
                self.assertEqual(self.emitted(bank), 0)
            self.assertLedgerClean()
        self.assertEqual(sum(outcomes.values()), 6, outcomes)

    def test_database_refuses_two_active_scenarios_even_around_the_service(self):
        from django.db import IntegrityError, transaction
        ledger.create_scenario("um", {"union": 1})
        ledger.create_scenario("dois", {"union": 1})
        self.assertTrue(ledger.activate_scenario("um", ["union"]).ok)
        with self.assertRaises(IntegrityError), transaction.atomic():
            LedgerScenario.objects.filter(name="dois").update(active=True)
        self.assertEqual(self.active_names(), ["um"])

    def test_set_grant_line_on_unknown_scenario_and_failed_change_leave_the_configuration_intact(self):
        with self.assertRaises(LedgerScenario.DoesNotExist):
            ledger.set_grant_line("nope", "union", 1)
        ledger.create_scenario("cfg", {"union": 10})
        self.assertTrue(ledger.activate_scenario("cfg", ["union"]).ok)
        self.assertTrue(ledger.grant_scenario_allocation("cfg", ledger.union_account().pk, 10, role="union").ok)
        with self.assertRaises(ledger.LedgerRefusal) as cm:
            ledger.set_grant_line("cfg", "union", 11)
        self.assertEqual(cm.exception.result.code, "GRANT_LINE_LOCKED")
        self.assertEqual(ScenarioGrantLine.objects.get(scenario__name="cfg", role="union").amount, 10)
        self.assertLedgerClean()


@unittest.skipUnless(ON_PG, "ordem estrita de bloqueio: só tem efeito em PostgreSQL (SELECT ... FOR UPDATE)")
class PostgresLockOrderTests(ScenarioConcurrencyBase):
    """Uma thread segura o bloqueio do cenário DEPOIS de validar/travar; a outra deve esperar e terminar depois."""

    def setUp(self):
        self.bank = ledger.get_or_create_account(AccountKind.MILITIA_BANK, 1)
        self.bank2 = ledger.get_or_create_account(AccountKind.MILITIA_BANK, 2)
        ledger.create_scenario("A", {"militia_bank": 500})
        ledger.create_scenario("B", {"militia_bank": 500})
        self.assertTrue(ledger.activate_scenario("A", ["militia_bank"]).ok)

    def slow_after_check(self, entered):
        """`_check_grant` real e, em seguida, segura a transação (e o bloqueio do cenário) por HOLD segundos, uma vez."""
        real, first = ledger._check_grant, threading.Event()

        def hooked(permit, leg, locked):
            real(permit, leg, locked)
            if not first.is_set():
                first.set()
                entered.set()
                time.sleep(HOLD)
        return mock.patch.object(ledger, "_check_grant", hooked)

    def test_line_change_waits_for_a_grant_in_flight_and_is_then_locked(self):
        entered = threading.Event()
        with self.slow_after_check(entered):
            grant = Job(lambda: ledger.grant_scenario_allocation("A", self.bank.pk, 500, role="militia_bank")).start()
            self.assertTrue(entered.wait(10))
            change = Job(lambda: ledger.set_grant_line("A", "militia_bank", 900)).start()
            grant.join(), change.join()
        self.assertIsNone(grant.error), self.assertIsNone(change.error)
        self.assertTrue(grant.result.ok, grant.result)
        self.assertEqual(change.result.code, "GRANT_LINE_LOCKED")             # relida a emissão DEPOIS do bloqueio
        self.assertGreaterEqual(change.ended, grant.ended - 0.3, "a alteração terminou antes de a emissão confirmar")
        self.assertGreater(change.ended - change.started, HOLD / 2, "a alteração não esperou o bloqueio")
        self.assertEqual(ScenarioGrantLine.objects.get(scenario__name="A", role="militia_bank").amount, 500)
        self.assertEqual(self.emitted(self.bank), 500)
        self.assertLedgerClean()

    def test_activation_waits_for_a_grant_in_flight_then_later_grants_are_refused(self):
        entered = threading.Event()
        with self.slow_after_check(entered):
            grant = Job(lambda: ledger.grant_scenario_allocation("A", self.bank.pk, 500, role="militia_bank")).start()
            self.assertTrue(entered.wait(10))
            activation = Job(lambda: ledger.activate_scenario("B", ["militia_bank"])).start()
            grant.join(), activation.join()
        self.assertIsNone(grant.error), self.assertIsNone(activation.error)
        self.assertTrue(grant.result.ok and activation.result.ok, (grant.result, activation.result))
        self.assertGreaterEqual(activation.ended, grant.ended - 0.3, "a ativação terminou antes de a emissão confirmar")
        self.assertGreater(activation.ended - activation.started, HOLD / 2, "a ativação não esperou o bloqueio")
        self.assertEqual(self.active_names(), ["B"])
        later = ledger.grant_scenario_allocation("A", self.bank2.pk, 500, role="militia_bank")
        self.assertEqual(later.code, "SCENARIO_NOT_ACTIVE")
        self.assertEqual((self.emitted(self.bank), self.emitted(self.bank2)), (500, 0))
        self.assertLedgerClean()

    def test_grant_waits_for_an_activation_in_flight_and_is_then_refused(self):
        entered, real = threading.Event(), ledger._lock_scenarios

        def slow_activation(name=None):
            rows = real(name)
            if name is None:                    # só a ativação trava todos os cenários
                entered.set()
                time.sleep(HOLD)
            return rows
        with mock.patch.object(ledger, "_lock_scenarios", slow_activation):
            activation = Job(lambda: ledger.activate_scenario("B", ["militia_bank"])).start()
            self.assertTrue(entered.wait(10))
            grant = Job(lambda: ledger.grant_scenario_allocation("A", self.bank.pk, 500, role="militia_bank")).start()
            activation.join(), grant.join()
        self.assertIsNone(activation.error), self.assertIsNone(grant.error)
        self.assertTrue(activation.result.ok, activation.result)
        self.assertEqual(grant.result.code, "SCENARIO_NOT_ACTIVE")            # emissão relida o estado DEPOIS do bloqueio
        self.assertGreaterEqual(grant.ended, activation.ended - 0.3)
        self.assertGreater(grant.ended - grant.started, HOLD / 2, "a emissão não esperou a ativação")
        self.assertEqual(self.active_names(), ["B"])
        self.assertEqual(self.emitted(self.bank), 0)
        self.assertLedgerClean()

    def test_two_activations_in_flight_serialize_without_deadlock(self):
        entered, real, first = threading.Event(), ledger._lock_scenarios, threading.Event()

        def slow_first(name=None):
            rows = real(name)
            if name is None and not first.is_set():
                first.set()
                entered.set()
                time.sleep(HOLD)
            return rows
        with mock.patch.object(ledger, "_lock_scenarios", slow_first):
            one = Job(lambda: ledger.activate_scenario("A", ["militia_bank"])).start()
            self.assertTrue(entered.wait(10))
            two = Job(lambda: ledger.activate_scenario("B", ["militia_bank"])).start()
            one.join(), two.join()
        self.assertTrue(one.error is None and two.error is None, (one.error, two.error))
        self.assertTrue(one.result.ok and two.result.ok)
        self.assertEqual(self.active_names(), ["B"])                         # a segunda esperou e foi a última
        self.assertGreater(two.ended - two.started, HOLD / 2)
        self.assertLedgerClean()


@unittest.skipUnless(ON_PG, "ordem estrita de bloqueio: só tem efeito em PostgreSQL (SELECT ... FOR UPDATE)")
class PostgresOrmGuardLockOrderTests(PostgresLockOrderTests.__bases__[0]):
    """A guarda de imutabilidade da linha segue o mesmo protocolo: uma emissão em andamento termina ANTES da mutação."""

    setUp = PostgresLockOrderTests.setUp
    slow_after_check = PostgresLockOrderTests.slow_after_check

    def _mutation_waits_and_is_refused(self, mutate):
        entered = threading.Event()
        with self.slow_after_check(entered):
            grant = Job(lambda: ledger.grant_scenario_allocation("A", self.bank.pk, 500, role="militia_bank")).start()
            self.assertTrue(entered.wait(10))
            change = Job(mutate).start()
            grant.join(), change.join()
        self.assertIsNone(grant.error)
        self.assertTrue(grant.result.ok, grant.result)
        self.assertIsInstance(change.error, GrantLineLockedError, (change.error, change.result))   # histórico lido DEPOIS do bloqueio
        self.assertGreaterEqual(change.ended, grant.ended - 0.3, "a mutação terminou antes de a emissão confirmar")
        self.assertGreater(change.ended - change.started, HOLD / 2, "a mutação não esperou o bloqueio")
        self.assertEqual(list(ScenarioGrantLine.objects.filter(scenario__name="A").values_list("role", "amount")),
                         [("militia_bank", 500)])
        self.assertEqual(self.emitted(self.bank), 500)
        self.assertLedgerClean()

    def test_orm_update_waits_for_a_grant_in_flight_and_is_refused(self):
        self._mutation_waits_and_is_refused(
            lambda: ScenarioGrantLine.objects.filter(scenario__name="A").update(amount=900))

    def test_orm_delete_waits_for_a_grant_in_flight_and_is_refused(self):
        self._mutation_waits_and_is_refused(lambda: ScenarioGrantLine.objects.filter(scenario__name="A").delete())

    def test_instance_save_waits_for_a_grant_in_flight_and_is_refused(self):
        def change():
            line = ScenarioGrantLine.objects.get(scenario__name="A", role="militia_bank")
            line.amount = 900
            line.save()
        self._mutation_waits_and_is_refused(change)

    def test_scenario_delete_waits_for_a_grant_in_flight_and_is_refused(self):
        self._mutation_waits_and_is_refused(lambda: LedgerScenario.objects.filter(name="A").delete())


class _Gate:
    def __init__(self):
        self.entered, self.go, self.used = threading.Event(), threading.Event(), False


@unittest.skipUnless(ON_PG, "intercalamento determinístico por bloqueios de linha: só tem efeito em PostgreSQL")
class PostgresLockOrderWithMovingLineTests(ScenarioConcurrencyBase):
    """
    O intercalamento que, com leitura PRÉVIA dos cenários + bloqueio parcial, dava ciclo com `activate_scenario`:
      X move a linha D2→D1; Y (move D2→D3 ou exclui) espera X; X confirma; Y consegue seus bloqueios e PARA (segurando-os);
      a ativação entra e pega o que está livre; Y é liberada e relê a linha, que agora está em D1.
    Com bloqueio parcial, Y pediria D1 (fora da ordem) e travaria com a ativação (deadlock). Com o protocolo atual (todos os
    cenários, em ordem, como primeiro passo; nenhuma verificação trava mais nada) todas terminam.
    """

    def setUp(self):
        ledger.create_scenario("D1", {})
        ledger.create_scenario("D2", {"militia_bank": 500})
        ledger.create_scenario("D3", {})
        self.pks = {n: LedgerScenario.objects.get(name=n).pk for n in ("D1", "D2", "D3")}
        # ordem global de pk é D1 < D2 < D3 (o que torna a aquisição de D1 depois de D2/D3 uma violação da ordem)
        self.assertLess(self.pks["D1"], self.pks["D2"])
        self.assertLess(self.pks["D2"], self.pks["D3"])
        self.line = ScenarioGrantLine.objects.get(scenario__name="D2", role="militia_bank")
        self.bank = ledger.get_or_create_account(AccountKind.MILITIA_BANK, 1)

    def choreography(self, second_op):
        gates = {"X": _Gate(), "Y": _Gate()}
        real = ledger_models.lock_scenarios

        def hooked(ids=None, names=None):
            rows = real(ids, names)
            gate = gates.get(threading.current_thread().name)
            if gate is not None and not gate.used:        # só a PRIMEIRA aquisição de cada thread marcada pausa
                gate.used = True
                gate.entered.set()
                if not gate.go.wait(30):
                    raise AssertionError("pausa não liberada")
            return rows

        line_pk, d1 = self.line.pk, self.pks["D1"]
        with mock.patch.object(ledger_models, "lock_scenarios", hooked):
            x = Job(lambda: ScenarioGrantLine.objects.filter(pk=line_pk).update(scenario_id=d1), name="X").start()
            self.assertTrue(gates["X"].entered.wait(15), "X não chegou a travar")
            y = Job(second_op, name="Y").start()
            time.sleep(0.7)                                # Y fica esperando os bloqueios de X
            self.assertIsNone(y.ended, "Y deveria estar esperando X")
            gates["X"].go.set()                            # X confirma e libera
            self.assertTrue(gates["Y"].entered.wait(15), "Y não chegou a travar depois de X")
            a = Job(lambda: ledger.activate_scenario("D1", []), name="A").start()
            time.sleep(0.9)                                # a ativação pega o que estiver livre e espera o resto
            gates["Y"].go.set()                            # Y relê (a linha agora está em D1) e continua
            for j in (x, y, a):
                j.join()
        errors = {j.thread.name: j.error for j in (x, y, a) if j.error is not None}
        self.assertEqual(errors, {}, "alguma operação falhou (deadlock?)")
        self.assertTrue(a.result.ok, a.result)
        self.assertEqual(self.active_names(), ["D1"])
        return x, y, a

    def assertImmutableAfterEmission(self, scenario):
        """Depois do intercalamento a configuração continua consistente e a imutabilidade pós-emissão segue valendo."""
        self.assertTrue(ledger.activate_scenario(scenario, ["militia_bank"]).ok)
        self.assertTrue(ledger.grant_scenario_allocation(scenario, self.bank.pk, 500, role="militia_bank").ok)
        line = ScenarioGrantLine.objects.get(scenario__name=scenario, role="militia_bank")
        for mutate in (lambda: ScenarioGrantLine.objects.filter(pk=line.pk).update(amount=900),
                       lambda: ScenarioGrantLine.objects.filter(pk=line.pk).update(scenario_id=self.pks["D1"]),
                       lambda: ScenarioGrantLine.objects.filter(pk=line.pk).delete(),
                       lambda: ledger.set_grant_line(scenario, "militia_bank", 900)):
            with self.assertRaises((GrantLineLockedError, ledger.LedgerRefusal)):
                mutate()
        self.assertEqual(list(ScenarioGrantLine.objects.filter(pk=line.pk).values_list("scenario__name", "amount")),
                         [(scenario, 500)])
        self.assertEqual(self.emitted(self.bank), 500)
        self.assertLedgerClean()

    def test_two_moves_of_the_same_line_with_a_concurrent_activation_do_not_deadlock(self):
        d3 = self.pks["D3"]
        self.choreography(lambda: ScenarioGrantLine.objects.filter(pk=self.line.pk).update(scenario_id=d3))
        # X moveu para D1 e Y (depois) para D3: a linha existe uma única vez, em D3, com o valor original
        self.assertEqual(list(ScenarioGrantLine.objects.values_list("scenario__name", "role", "amount")),
                         [("D3", "militia_bank", 500)])
        self.assertImmutableAfterEmission("D3")

    def test_a_move_and_a_delete_of_the_same_line_with_a_concurrent_activation_do_not_deadlock(self):
        self.choreography(lambda: ScenarioGrantLine.objects.filter(pk=self.line.pk).delete())
        self.assertEqual(ScenarioGrantLine.objects.count(), 0)          # X moveu e Y apagou a linha que X deixou em D1
        ledger.set_grant_line("D3", "militia_bank", 500)                # recriar uma linha ainda sem dotação é livre
        self.assertImmutableAfterEmission("D3")
