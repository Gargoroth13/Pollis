"""
Imutabilidade da configuração de dotação depois da primeira dotação (design/24 §24.11): vale contra o ORM (instância, lote,
upsert, exclusão, cascata, recriação), contra o renome do cenário e, se alguém contornar o ORM por SQL direto, o serviço de
emissão recusa novas emissões (`GRANT_HISTORY_INCONSISTENT`) e a auditoria aponta as dotações antigas.
"""
from django.db import connection
from django.db.models import F, Value

from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import AccountKind
from ledger.models import (Account, Entry, GrantLineLockedError, LedgerImmutableError, LedgerScenario, ScenarioGrantLine,
                           Transaction)

from .base import LedgerTestCase


class GrantLineTestCase(LedgerTestCase):
    def setUp(self):
        super().setUp()
        ledger.create_scenario("gl", {"union": 5_000, "militia_bank": 800})
        self.assertTrue(ledger.activate_scenario("gl", ["union", "militia_bank"]).ok)
        ledger.create_scenario("other", {"militia_bank": 800})
        self.sc = LedgerScenario.objects.get(name="gl")
        self.other = LedgerScenario.objects.get(name="other")
        self.bank1, self.bank2, self.bank3 = (ledger.get_or_create_account(AccountKind.MILITIA_BANK, n) for n in (1, 2, 3))
        self.assertTrue(ledger.grant_scenario_allocation("gl", self.bank1.pk, 800, role="militia_bank").ok)
        self.used = ScenarioGrantLine.objects.get(scenario=self.sc, role="militia_bank")     # já emitiu
        self.unused = ScenarioGrantLine.objects.get(scenario=self.sc, role="union")          # ainda não emitiu

    def state(self):
        return (dict(Account.objects.values_list("pk", "balance")), Entry.objects.count(), Transaction.objects.count())

    def lines(self):
        return sorted(ScenarioGrantLine.objects.values_list("scenario__name", "role", "amount"))

    def assertLocked(self, call, exc=GrantLineLockedError):
        before_state, before_lines = self.state(), self.lines()
        with self.assertRaises(exc) as cm:
            call()
        if exc is GrantLineLockedError:
            self.assertEqual(cm.exception.code, "GRANT_LINE_LOCKED")
        self.assertEqual((self.state(), self.lines()), (before_state, before_lines), "a recusa não pode deixar rastro")


class OrmWritePathsAreRefusedAfterTheFirstGrant(GrantLineTestCase):
    def test_deletion_paths(self):
        qs = ScenarioGrantLine.objects
        self.assertLocked(lambda: self.used.delete())
        self.assertLocked(lambda: qs.filter(pk=self.used.pk).delete())
        self.assertLocked(lambda: qs.all().delete())                       # atômico: nem a linha sem dotação some junto
        self.assertLocked(lambda: self.sc.delete())                        # cascata
        self.assertLocked(lambda: LedgerScenario.objects.filter(pk=self.sc.pk).delete())
        self.assertLocked(lambda: ScenarioGrantLine._base_manager.filter(pk=self.used.pk).delete())
        self.assertLocked(lambda: qs.filter(pk=self.used.pk)._raw_delete("default"), LedgerImmutableError)

    def test_update_paths(self):
        qs, other = ScenarioGrantLine.objects, self.other
        pk = self.used.pk
        self.assertLocked(lambda: qs.filter(pk=pk).update(amount=900))
        self.assertLocked(lambda: qs.filter(pk=pk).update(amount=F("amount") + 1))
        self.assertLocked(lambda: qs.filter(pk=pk).update(amount=None))
        self.assertLocked(lambda: qs.filter(pk=pk).update(role="state"))
        self.assertLocked(lambda: qs.filter(pk=pk).update(scenario=other))
        self.assertLocked(lambda: qs.filter(pk=pk).update(scenario_id=other.pk))
        self.assertLocked(lambda: qs.all().update(amount=1))               # lote que inclui a linha com dotação
        self.assertLocked(lambda: ScenarioGrantLine._base_manager.filter(pk=pk).update(amount=900))
        self.assertLocked(lambda: qs.filter(pk=pk).update(role=F("role")), LedgerImmutableError)

    def test_instance_paths(self):
        for field, value in (("amount", 900), ("role", "state"), ("scenario", self.other)):
            line = ScenarioGrantLine.objects.get(pk=self.used.pk)
            setattr(line, field, value)
            self.assertLocked(line.save)
            self.assertLocked(lambda: line.save(update_fields=[field]))
        line = ScenarioGrantLine.objects.get(pk=self.used.pk)
        line.amount = 900                                                  # update_fields sem `amount`: nada muda de fato
        line.save(update_fields=["role"])
        self.assertEqual(ScenarioGrantLine.objects.get(pk=self.used.pk).amount, 800)

    def test_batch_and_upsert_paths(self):
        used = ScenarioGrantLine.objects.get(pk=self.used.pk)
        used.amount = 900
        self.assertLocked(lambda: ScenarioGrantLine.objects.bulk_update([used], ["amount"]))
        self.assertLocked(lambda: ScenarioGrantLine.objects.update_or_create(
            scenario=self.sc, role="militia_bank", defaults={"amount": 900}))
        self.assertLocked(lambda: ScenarioGrantLine.objects.bulk_create(
            [ScenarioGrantLine(scenario=self.sc, role="militia_bank", amount=900)], update_conflicts=True,
            update_fields=["amount"], unique_fields=["scenario", "role"]), LedgerImmutableError)

    def test_service_path(self):
        before = self.lines()
        with self.assertRaises(ledger.LedgerRefusal) as cm:
            ledger.set_grant_line("gl", "militia_bank", 900)
        self.assertEqual(cm.exception.result.code, "GRANT_LINE_LOCKED")
        self.assertEqual(self.lines(), before)

    def test_scenario_rename_is_refused_after_grants_but_free_before(self):
        sc = LedgerScenario.objects.get(pk=self.sc.pk)
        sc.name = "gl2"
        self.assertLocked(sc.save)
        self.assertLocked(lambda: LedgerScenario.objects.filter(pk=self.sc.pk).update(name="gl2"))
        self.assertLocked(lambda: LedgerScenario.objects.filter(pk=self.sc.pk).update(name=F("name")), GrantLineLockedError)
        self.assertEqual(LedgerScenario.objects.get(pk=self.sc.pk).name, "gl")
        free = LedgerScenario.objects.get(pk=self.other.pk)               # sem dotações: renomear e excluir continuam livres
        free.name = "other2"
        free.save()
        LedgerScenario.objects.filter(pk=self.other.pk).update(name="other3")
        self.assertEqual(LedgerScenario.objects.get(pk=self.other.pk).name, "other3")
        free.delete()
        self.assertFalse(LedgerScenario.objects.filter(pk=self.other.pk).exists())


class RecreationAndTamperingTests(GrantLineTestCase):
    def test_delete_and_recreate_with_another_value_cannot_emit_the_tampered_amount(self):
        self.assertLocked(lambda: self.used.delete())                      # 1. pelo ORM nem apaga
        before = self.state()
        with connection.cursor() as c:                                     # 2. contorna o ORM: apaga a linha por SQL
            c.execute("DELETE FROM ledger_scenariograntline WHERE id = %s", [self.used.pk])
        with self.assertRaises(GrantLineLockedError):                      # 3. recriar com outro valor pelo ORM: recusado
            ScenarioGrantLine.objects.create(scenario=self.sc, role="militia_bank", amount=900)
        with self.assertRaises(ledger.LedgerRefusal) as cm:                # pelo serviço também
            ledger.set_grant_line("gl", "militia_bank", 900)
        self.assertEqual(cm.exception.result.code, "GRANT_LINE_LOCKED")
        with self.assertRaises(GrantLineLockedError):                      # nem mover outra linha para o par com histórico
            ScenarioGrantLine.objects.filter(pk=self.unused.pk).update(role="militia_bank")
        for amount in (900, 800):                                          # sem linha, nenhuma emissão, com qualquer valor
            res = ledger.grant_scenario_allocation("gl", self.bank2.pk, amount, role="militia_bank")
            self.assertEqual((res.ok, res.code), (False, "SCENARIO_GRANT_UNSPECIFIED"))
        self.assertEqual(self.state(), before)
        # reparar com o valor HISTÓRICO é permitido e volta a emitir normalmente
        ledger.set_grant_line("gl", "militia_bank", 800)
        self.assertTrue(ledger.grant_scenario_allocation("gl", self.bank2.pk, 800, role="militia_bank").ok)
        self.assertTrue(audit_ledger().ok)


class SqlTamperedLineTests(GrantLineTestCase):
    audit_at_end = False

    def tamper(self, sql, *params):
        with connection.cursor() as c:
            c.execute(sql, params)

    def test_line_changed_by_direct_sql_refuses_new_emissions_and_the_audit_flags_the_old_ones(self):
        self.tamper("UPDATE ledger_scenariograntline SET amount = 900 WHERE id = %s", self.used.pk)
        before = self.state()
        for amount in (900, 800):
            res = ledger.grant_scenario_allocation("gl", self.bank2.pk, amount, role="militia_bank")
            self.assertEqual((res.ok, res.code), (False, "GRANT_HISTORY_INCONSISTENT"), (amount, res.detail))
            self.assertEqual((res.detail["configured"], res.detail["historical"]), (900, [800]))
        self.assertEqual(self.state(), before)                              # nada de transação, lançamento ou saldo novo
        self.assertEqual(self.bal(self.bank2), 0)
        findings = audit_ledger().findings
        self.assertIn("GRANT_AMOUNT_MISMATCH", {f["code"] for f in findings})
        self.assertEqual([f["account"] for f in findings if f["code"] == "GRANT_AMOUNT_MISMATCH"], [self.bank1.pk])
        replay = ledger.grant_scenario_allocation("gl", self.bank1.pk, 800, role="militia_bank")
        self.assertEqual((replay.ok, replay.detail["already_posted"]), (True, True))     # replay da original continua valendo

    def test_line_deleted_and_recreated_by_direct_sql_with_another_value(self):
        self.tamper("DELETE FROM ledger_scenariograntline WHERE id = %s", self.used.pk)
        self.tamper("INSERT INTO ledger_scenariograntline (scenario_id, role, amount) VALUES (%s, 'militia_bank', 900)",
                    self.sc.pk)
        before = self.state()
        res = ledger.grant_scenario_allocation("gl", self.bank3.pk, 900, role="militia_bank")
        self.assertEqual((res.ok, res.code), (False, "GRANT_HISTORY_INCONSISTENT"))
        self.assertEqual(self.state(), before)
        self.assertIn("GRANT_AMOUNT_MISMATCH", {f["code"] for f in audit_ledger().findings})

    def test_other_roles_and_scenarios_are_not_affected_by_the_tampered_pair(self):
        self.tamper("UPDATE ledger_scenariograntline SET amount = 900 WHERE id = %s", self.used.pk)
        self.assertTrue(ledger.grant_scenario_allocation("gl", ledger.union_account().pk, 5_000, role="union").ok)
        ledger.create_scenario("fresh", {"militia_bank": 800})
        self.assertTrue(ledger.activate_scenario("fresh", ["militia_bank"]).ok)
        self.assertTrue(ledger.grant_scenario_allocation("fresh", self.bank2.pk, 800, role="militia_bank").ok)


class NormalFlowsKeepWorkingTests(GrantLineTestCase):
    def test_idempotent_calls_that_change_nothing_are_allowed_even_after_grants(self):
        ledger.set_grant_line("gl", "militia_bank", 800)
        ScenarioGrantLine.objects.filter(pk=self.used.pk).update(amount=800, role="militia_bank")
        line = ScenarioGrantLine.objects.get(pk=self.used.pk)
        line.save()
        line.save(update_fields=["amount"])
        ScenarioGrantLine.objects.update_or_create(scenario=self.sc, role="militia_bank", defaults={"amount": 800})
        ScenarioGrantLine.objects.bulk_update([line], ["amount"])
        self.assertEqual(ScenarioGrantLine.objects.get(pk=self.used.pk).amount, 800)

    def test_lines_without_grants_change_freely_and_do_not_lock_each_other(self):
        ledger.set_grant_line("gl", "union", 6_000)                         # papel sem dotação, mesmo cenário
        ScenarioGrantLine.objects.filter(pk=self.unused.pk).update(amount=7_000)
        self.unused.refresh_from_db()
        self.unused.amount = 8_000
        self.unused.save()
        ledger.set_grant_line("other", "militia_bank", 1)                   # mesmo papel, outro cenário
        ScenarioGrantLine.objects.filter(scenario=self.other).update(amount=2)
        ledger.set_grant_line("gl", "state", 3)                             # linha nova
        ScenarioGrantLine.objects.filter(scenario=self.sc, role="state").update(role="municipality")
        ScenarioGrantLine.objects.filter(scenario=self.sc, role="municipality").delete()
        ScenarioGrantLine.objects.bulk_create([ScenarioGrantLine(scenario=self.other, role="union", amount=5)])
        ScenarioGrantLine.objects.filter(scenario=self.other, role="union").update(amount=6)
        self.assertEqual(dict(ScenarioGrantLine.objects.filter(scenario=self.sc).values_list("role", "amount")),
                         {"union": 8_000, "militia_bank": 800})
        self.assertEqual(ledger.activate_scenario("gl", ["union", "militia_bank"]).code, "OK")
        self.assertTrue(ledger.grant_scenario_allocation("gl", self.bank2.pk, 800, role="militia_bank").ok)
        self.assertTrue(ledger.grant_scenario_allocation("gl", ledger.union_account().pk, 8_000, role="union").ok)
        self.assertTrue(audit_ledger().ok)
