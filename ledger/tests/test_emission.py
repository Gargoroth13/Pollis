"""
Emissão (design/24 §24.11): `SCENARIO_GRANT` só é gravável pela via de dotação, e só no que o cenário ATIVO configurou
explicitamente (papel, tipo de conta e valor exato). Toda recusa deixa saldos, lançamentos e transações como estavam;
a auditoria (invariante 18) independe do serviço e pega o que escapar.
"""
from unittest import mock

from django.db import connection

from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import GRANT_ROLE_KINDS, AccountKind, Nature
from ledger.models import Account, Entry, LedgerScenario, ScenarioGrantLine, Transaction

from .base import LedgerTestCase


class EmissionTestCase(LedgerTestCase):
    def setUp(self):
        super().setUp()
        self.union = ledger.union_account()
        self.bank = ledger.get_or_create_account(AccountKind.MILITIA_BANK, 1)
        self.co = self.company(1)
        self.iss = ledger.issuance_account()

    def state(self):
        return (dict(Account.objects.values_list("pk", "balance")), Entry.objects.count(), Transaction.objects.count())

    def assertRefused(self, code, call, **detail):
        before = self.state()
        res = call()
        self.assertEqual((res.ok, res.code), (False, code), (res.code, res.detail))
        for k, v in detail.items():
            self.assertEqual(res.detail.get(k), v, (k, res.detail))
        self.assertEqual(self.state(), before, "recusa não pode deixar saldo, lançamento ou transação")
        return res

    def scenario(self, name="emi", lines=None, active=True):
        lines = {"union": 5_000, "militia_bank": 800} if lines is None else lines
        ledger.create_scenario(name, lines)
        if active:
            self.assertTrue(ledger.activate_scenario(name, list(lines)).ok)
        return name

    def grant_leg(self, to, amount, scenario="emi", role="union"):
        return ledger.Leg(self.iss.pk, to.pk, amount, Nature.SCENARIO_GRANT, operation="grant",
                          explained={"scenario": scenario, "role": role})


class DirectEmissionIsRefusedTests(EmissionTestCase):
    def test_transfer_from_issuance_is_refused_for_every_nature_including_scenario_grant(self):
        self.scenario()
        for nature in (Nature.SCENARIO_GRANT, Nature.SALE, Nature.GOV_TRANSFER):
            self.assertRefused("ISSUANCE_NOT_ALLOWED", lambda n=nature: ledger.transfer(
                self.iss.pk, self.union.pk, 5_000, n, key=f"t-{n.value}", reference_kind="scenario", reference_id="emi"))

    def test_transfer_with_scenario_grant_between_ordinary_accounts_is_refused(self):
        self.scenario()
        self.fund(self.co, 100)
        self.assertRefused("ISSUANCE_NOT_ALLOWED", lambda: ledger.transfer(
            self.co.pk, self.union.pk, 5, Nature.SCENARIO_GRANT, key="t2", reference_kind="scenario", reference_id="emi"))

    def test_post_transaction_with_scenario_grant_is_refused_even_when_it_mimics_the_exact_configured_grant(self):
        self.scenario()
        res = self.assertRefused("ISSUANCE_NOT_ALLOWED", lambda: ledger.post_transaction(
            [self.grant_leg(self.union, 5_000)], key=f"grant:emi:{self.union.pk}", reference_kind="scenario",
            reference_id="emi"))
        self.assertEqual(res.detail["why"], "grant_path_only")

    def test_post_transaction_grant_mixed_with_ordinary_legs_is_refused(self):
        self.scenario()
        self.fund(self.co, 100)
        self.assertRefused("ISSUANCE_NOT_ALLOWED", lambda: ledger.post_transaction(
            [self.grant_leg(self.union, 5_000), ledger.Leg(self.co.pk, self.union.pk, 1, Nature.SALE)],
            key="mix", reference_kind="scenario", reference_id="emi"))

    def test_taxed_payment_cannot_carry_the_grant_nature(self):
        self.scenario()
        self.fund(self.co, 100)
        res = ledger.post_taxed_payment(self.co.pk, self.union.pk, 10, nature=Nature.SCENARIO_GRANT, tax_rate=ledger.Decimal(0),
                                        territory=None, tax_nature=Nature.TAX_INCOME, key="tp", reference_kind="x",
                                        reference_id="1")
        self.assertFalse(res.ok)
        self.assertEqual(Entry.objects.filter(nature="scenario_grant").count(), 1)        # só a dotação do fund()

    def test_a_permit_cannot_be_reused_for_something_else(self):
        self.scenario()
        permit = ledger._GrantPermit("emi", "union", self.union.pk, 5_000)
        ordinary = [ledger.Leg(self.co.pk, self.union.pk, 1, Nature.SALE)]
        self.assertRefused("ISSUANCE_NOT_ALLOWED", lambda: ledger.post_transaction(
            ordinary, key="reuse", reference_kind="t", reference_id="1", _grant=permit))
        # permissão que não descreve a transação (outro valor / outra chave / outro destino)
        for kw in ({"key": f"grant:emi:{self.union.pk}", "amount": 4_999}, {"key": "other-key", "amount": 5_000}):
            self.assertRefused("ISSUANCE_NOT_ALLOWED", lambda kw=kw: ledger.post_transaction(
                [self.grant_leg(self.union, kw["amount"])], key=kw["key"], reference_kind="scenario",
                reference_id="emi", _grant=permit))
        self.assertRefused("ISSUANCE_NOT_ALLOWED", lambda: ledger.post_transaction(
            [self.grant_leg(self.bank, 5_000)], key=f"grant:emi:{self.union.pk}", reference_kind="scenario",
            reference_id="emi", _grant=permit))
        self.assertRefused("ISSUANCE_NOT_ALLOWED", lambda: ledger.post_transaction(
            [self.grant_leg(self.union, 5_000)], key=f"grant:emi:{self.union.pk}", reference_kind="scenario",
            reference_id="emi", _grant="not-a-permit"))

    def test_even_a_forged_permit_is_revalidated_against_the_scenario(self):
        self.scenario()
        forged = ledger._GrantPermit("emi", "union", self.union.pk, 9_999_999)        # valor que o cenário não configurou
        self.assertRefused("GRANT_AMOUNT_MISMATCH", lambda: ledger.post_transaction(
            [self.grant_leg(self.union, 9_999_999)], key=f"grant:emi:{self.union.pk}", reference_kind="scenario",
            reference_id="emi", _grant=forged), configured=5_000, requested=9_999_999)
        self.assertTrue(audit_ledger().ok)


class GrantValidationTests(EmissionTestCase):
    def test_exact_configured_grant_is_posted_once_and_recorded(self):
        self.scenario()
        res = ledger.grant_scenario_allocation("emi", self.union.pk, 5_000, role="union")
        self.assertTrue(res.ok, res)
        e = Entry.objects.get(nature="scenario_grant")
        self.assertEqual((e.from_account_id, e.to_account_id, e.amount, e.reference_kind, e.reference_id),
                         (self.iss.pk, self.union.pk, 5_000, "scenario", "emi"))
        self.assertEqual(e.explained, {"scenario": "emi", "role": "union"})
        again = ledger.grant_scenario_allocation("emi", self.union.pk, 5_000, role="union")
        self.assertEqual((again.ok, again.detail["already_posted"]), (True, True))
        self.assertEqual(Entry.objects.filter(nature="scenario_grant").count(), 1)
        self.assertEqual(self.bal(self.union), 5_000)

    def test_divergent_amount_is_refused_up_and_down(self):
        self.scenario()
        for amount in (5_001, 4_999, 1, 10**9):
            self.assertRefused("GRANT_AMOUNT_MISMATCH", lambda a=amount: ledger.grant_scenario_allocation(
                "emi", self.union.pk, a, role="union"), configured=5_000, requested=amount)

    def test_role_incompatible_with_account_kind_is_refused(self):
        self.scenario()
        for role, account in (("union", self.bank), ("militia_bank", self.union), ("union", self.co), ("militia_bank", self.co)):
            self.assertRefused("GRANT_ROLE_ACCOUNT_MISMATCH", lambda r=role, a=account: ledger.grant_scenario_allocation(
                "emi", a.pk, 5_000 if r == "union" else 800, role=r), role=role)

    def test_unknown_or_empty_role_is_refused(self):
        self.scenario()
        for role in ("", "company", "x", "UNION"):
            self.assertRefused("GRANT_ROLE_UNKNOWN", lambda r=role: ledger.grant_scenario_allocation(
                "emi", self.union.pk, 5_000, role=r))

    def test_role_without_explicit_line_or_with_unspecified_value_is_refused(self):
        self.scenario(lines={"union": 5_000, "militia_bank": None}, active=False)
        ledger.set_grant_line("emi", "union", 5_000)
        self.assertEqual(ledger.activate_scenario("emi", ["union"]).code, "OK")
        self.assertRefused("SCENARIO_GRANT_UNSPECIFIED", lambda: ledger.grant_scenario_allocation(
            "emi", self.bank.pk, 800, role="militia_bank"), missing=["militia_bank"])
        self.scenario("sem-linha", {"union": 1}, active=True)
        self.assertRefused("SCENARIO_GRANT_UNSPECIFIED", lambda: ledger.grant_scenario_allocation(
            "sem-linha", self.bank.pk, 800, role="militia_bank"), missing=["militia_bank"])

    def test_unknown_or_inactive_scenario_is_refused(self):
        self.assertRefused("SCENARIO_NOT_FOUND", lambda: ledger.grant_scenario_allocation(
            "nope", self.union.pk, 5, role="union"))
        self.scenario("rascunho", {"union": 5_000}, active=False)
        self.assertRefused("SCENARIO_NOT_ACTIVE", lambda: ledger.grant_scenario_allocation(
            "rascunho", self.union.pk, 5_000, role="union"))
        self.scenario("a", {"union": 5_000})
        self.scenario("b", {"union": 5_000})                     # ativar "b" desativa "a"
        self.assertRefused("SCENARIO_NOT_ACTIVE", lambda: ledger.grant_scenario_allocation(
            "a", self.union.pk, 5_000, role="union"))
        self.assertTrue(ledger.grant_scenario_allocation("b", self.union.pk, 5_000, role="union").ok)

    def test_replay_after_the_scenario_is_deactivated_returns_the_original_without_new_money(self):
        self.scenario("a", {"union": 5_000})
        first = ledger.grant_scenario_allocation("a", self.union.pk, 5_000, role="union")
        self.scenario("b", {"union": 1})
        again = ledger.grant_scenario_allocation("a", self.union.pk, 5_000, role="union")
        self.assertEqual((again.ok, again.detail["already_posted"], again.detail["transaction_id"]),
                         (True, True, first.detail["transaction_id"]))
        self.assertEqual(self.bal(self.union), 5_000)

    def test_zero_amount_and_invalid_amounts_are_refused(self):
        self.scenario()
        for amount in (0, -1, 1.5, True):
            res = ledger.grant_scenario_allocation("emi", self.union.pk, amount, role="union")
            self.assertFalse(res.ok, amount)
        self.assertEqual(Entry.objects.count(), 0)

    def test_closed_or_missing_destination_is_refused(self):
        self.scenario()
        self.assertRefused("ACCOUNT_NOT_FOUND", lambda: ledger.grant_scenario_allocation(
            "emi", 987_654, 5_000, role="union"))

    def test_grant_line_rules(self):
        self.scenario()
        with self.assertRaises(ValueError):
            ledger.set_grant_line("emi", "company", 10)           # papel fora do design 24 §24.11
        ledger.set_grant_line("emi", "union", 6_000)              # sem dotação feita ainda: pode mudar
        ledger.set_grant_line("emi", "union", 5_000)
        self.assertTrue(ledger.grant_scenario_allocation("emi", self.union.pk, 5_000, role="union").ok)
        ledger.set_grant_line("emi", "union", 5_000)              # mesmo valor: sem efeito
        with self.assertRaises(ledger.LedgerRefusal) as cm:
            ledger.set_grant_line("emi", "union", 9_000)          # já emitiu: não reescreve o que foi emitido
        self.assertEqual(cm.exception.result.code, "GRANT_LINE_LOCKED")
        ledger.set_grant_line("emi", "militia_bank", 1)           # outra linha, sem dotações: livre
        self.assertEqual(ScenarioGrantLine.objects.get(scenario__name="emi", role="union").amount, 5_000)

    def test_production_role_map_is_closed_to_the_documented_roles(self):
        from ledger import constants
        self.assertEqual(set(constants.GRANT_ROLE_KINDS) - {"test_any"},
                         {"player", "union", "state", "municipality", "militia_bank"})

    def test_a_grant_cannot_be_reversed(self):
        self.scenario()
        ledger.grant_scenario_allocation("emi", self.union.pk, 5_000, role="union")
        e = Entry.objects.get(nature="scenario_grant")
        self.assertRefused("REVERSAL_NOT_POSSIBLE", lambda: ledger.reverse(e.pk, "teste", key="rv"))


class AuditEmissionTests(EmissionTestCase):
    audit_at_end = False

    def setUp(self):
        super().setUp()
        self.scenario()
        ledger.grant_scenario_allocation("emi", self.union.pk, 5_000, role="union")
        ledger.grant_scenario_allocation("emi", self.bank.pk, 800, role="militia_bank")

    def codes(self):
        return {f["code"] for f in audit_ledger().findings}

    def raw(self, sql, *params):
        with connection.cursor() as c:
            c.execute(sql, params)

    def test_valid_grants_pass_and_refused_api_attempts_leave_the_audit_clean(self):
        self.assertTrue(audit_ledger().ok, audit_ledger().findings)
        before = self.state()
        ledger.grant_scenario_allocation("emi", self.union.pk, 1, role="union")
        ledger.grant_scenario_allocation("emi", self.co.pk, 5_000, role="union")
        ledger.post_transaction([self.grant_leg(self.co, 77)], key="x", reference_kind="scenario", reference_id="emi")
        ledger.transfer(self.iss.pk, self.co.pk, 77, Nature.SCENARIO_GRANT, key="y", reference_kind="t", reference_id=1)
        self.assertEqual(self.state(), before)
        self.assertTrue(audit_ledger().ok)

    def test_line_changed_after_the_fact_is_a_divergence(self):
        self.raw("UPDATE ledger_scenariograntline SET amount = 4000 WHERE role = 'union'")      # SQL direto: o ORM recusa
        self.assertIn("GRANT_AMOUNT_MISMATCH", self.codes())

    def test_line_removed_or_scenario_removed(self):
        self.raw("DELETE FROM ledger_scenariograntline WHERE role = 'union'")                   # SQL direto: o ORM recusa
        self.assertIn("GRANT_LINE_MISSING", self.codes())
        self.raw("DELETE FROM ledger_scenariograntline")
        self.raw("DELETE FROM ledger_ledgerscenario WHERE name = 'emi'")
        self.assertIn("GRANT_SCENARIO_UNKNOWN", self.codes())

    def test_entry_tampered_in_the_database(self):
        self.raw("UPDATE ledger_entry SET reference_id = 'fantasma' WHERE to_account_id = %s", self.union.pk)
        self.assertIn("GRANT_SCENARIO_UNKNOWN", self.codes())

    def test_recorded_role_tampered(self):
        e = Entry.objects.get(to_account=self.bank)
        self.raw("UPDATE ledger_entry SET explained = %s WHERE seq = %s", '{"scenario": "emi", "role": "union"}', e.pk)
        found = {f["code"] for f in audit_ledger().findings}
        self.assertIn("GRANT_ROLE_ACCOUNT_MISMATCH", found)
        self.assertIn("GRANT_AMOUNT_MISMATCH", found)            # o valor 800 não é o da linha `union`
        for bad in ('{"scenario": "emi"}', '{"scenario": "emi", "role": 7}', '{"scenario": "emi", "role": "company"}', '[]'):
            self.raw("UPDATE ledger_entry SET explained = %s WHERE seq = %s", bad, e.pk)
            self.assertIn("GRANT_ROLE_INVALID", self.codes(), bad)

    def test_explained_scenario_and_key_tampered(self):
        e = Entry.objects.get(to_account=self.bank)
        self.raw("UPDATE ledger_entry SET explained = %s WHERE seq = %s", '{"scenario": "outro", "role": "militia_bank"}', e.pk)
        self.assertIn("GRANT_EXPLAINED_MISMATCH", self.codes())
        self.raw("UPDATE ledger_transaction SET key = 'grant:emi:999999' WHERE id = %s", e.transaction_id)
        self.assertIn("GRANT_KEY_MISMATCH", self.codes())

    def test_destination_swapped_in_the_database_is_detected(self):
        e = Entry.objects.get(to_account=self.bank)
        self.raw("UPDATE ledger_entry SET to_account_id = %s WHERE seq = %s", self.co.pk, e.pk)
        self.assertIn("GRANT_ROLE_ACCOUNT_MISMATCH", self.codes())

    def test_issuance_outside_the_service_is_flagged_even_if_the_service_check_is_bypassed(self):
        """A auditoria não confia no serviço: se a validação for contornada (ex.: bug), a emissão inválida aparece."""
        fresh = [ledger.get_or_create_account(AccountKind.MILITIA_BANK, n) for n in (10, 11)]
        cases = {
            "GRANT_AMOUNT_MISMATCH": ("emi", fresh[0], 801, "militia_bank"),
            "GRANT_ROLE_ACCOUNT_MISMATCH": ("emi", self.co, 5_000, "union"),
        }
        for code, (scenario, account, amount, role) in cases.items():
            with mock.patch.object(ledger, "_check_grant"):
                res = ledger.grant_scenario_allocation(scenario, account.pk, amount, role=role)
            self.assertTrue(res.ok, res)
            self.assertIn(code, self.codes())
        with mock.patch.object(ledger, "_check_grant"):                  # papel desconhecido
            ledger.grant_scenario_allocation("emi", fresh[1].pk, 1, role="inventado")
        self.assertIn("GRANT_ROLE_INVALID", self.codes())

    def test_duplicate_grant_for_the_same_account_is_flagged(self):
        # segunda dotação ao mesmo destino, por fora do serviço (a chave idempotente impediria pelo serviço)
        class Forged(ledger._GrantPermit):
            __slots__ = ()

            def expected_key(self):
                return "grant:emi:duplicata"

        permit = Forged("emi", "militia_bank", self.bank.pk, 800)
        with mock.patch.object(ledger, "_check_grant"):
            ledger.post_transaction([self.grant_leg(self.bank, 800, role="militia_bank")], key="grant:emi:duplicata",
                                    reference_kind="scenario", reference_id="emi", _grant=permit)
        found = {f["code"] for f in audit_ledger().findings}
        self.assertIn("GRANT_DUPLICATE", found)
        self.assertIn("GRANT_KEY_MISMATCH", found)

    def test_grant_transaction_with_extra_legs_is_flagged(self):
        e = Entry.objects.get(to_account=self.union)
        # perna extra na mesma transação, adulterada fora da API
        extra = Entry.objects.get(pk=e.pk)
        extra.pk, extra._state.adding = None, True
        extra.save()
        self.assertIn("GRANT_TRANSACTION_NOT_SINGLE", self.codes())
