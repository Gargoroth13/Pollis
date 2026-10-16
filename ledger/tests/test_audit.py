import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction

from ledger import services as ledger
from ledger.audit import audit_ledger, ledger_metrics
from ledger.constants import Nature
from ledger.models import Account, Entry, Hold, Obligation, RemunerationCounter, Transaction

from .base import D, LedgerTestCase


class AuditTests(LedgerTestCase):
    audit_at_end = False

    def setUp(self):
        super().setUp()
        self.a, self.b = self.company(1), self.company(2)
        self.fund(self.a, 1000)
        self.pay(self.a, self.b, 300)

    def codes(self):
        return {f["code"] for f in audit_ledger().findings}

    def test_clean_ledger_passes(self):
        rep = audit_ledger()
        self.assertTrue(rep.ok, rep.findings)
        self.assertEqual((rep.stats["emitted"], rep.stats["operational"]), (1000, 1000))

    def test_detects_tampered_balance(self):
        Account.objects.filter(pk=self.a.pk).update(balance=999)
        self.assertIn("STORED_BALANCE_DIFFERS_FROM_LOG", self.codes())
        self.assertIn("BALANCES_DO_NOT_SUM_TO_ZERO", self.codes())

    def test_detects_tampered_entry_amount_even_bypassing_service(self):
        with connection.cursor() as c:                 # adulteração direta no banco, fora de qualquer API
            c.execute("UPDATE ledger_entry SET amount = amount + 1 WHERE nature = 'sale'")
        self.assertIn("ENTRY_FROM_CHAIN_BROKEN", self.codes())

    def test_detects_deleted_entry(self):
        with connection.cursor() as c:
            c.execute("DELETE FROM ledger_entry WHERE nature = 'sale'")
        self.assertIn("STORED_BALANCE_DIFFERS_FROM_LOG", self.codes())

    def test_database_itself_refuses_negative_balances_and_positive_issuance(self):
        """Defesa em profundidade: a restrição do banco impede o que a auditoria também procuraria."""
        for pk, value in ((self.b.pk, -5), (ledger.issuance_account().pk, 5)):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Account.objects.filter(pk=pk).update(balance=value)

    def test_detects_issuance_origin_with_wrong_nature(self):
        iss = ledger.issuance_account()
        with connection.cursor() as c:
            c.execute("UPDATE ledger_entry SET nature = 'sale' WHERE nature = 'scenario_grant'")
        codes = self.codes()
        self.assertIn("ISSUANCE_WITH_WRONG_NATURE", codes)
        self.assertEqual(Entry.objects.filter(from_account=iss, nature="sale").count(), 1)

    def test_detects_sink_as_origin(self):
        sink = ledger.sink_account()
        ledger.transfer(self.a.pk, sink.pk, 10, Nature.CAMPAIGN_COST, key="s", reference_kind="t", reference_id=1)
        with connection.cursor() as c:
            c.execute("UPDATE ledger_entry SET from_account_id = %s, to_account_id = %s WHERE nature = 'campaign_cost'",
                      [sink.pk, self.a.pk])
        self.assertIn("SINK_AS_ORIGIN", self.codes())

    def test_detects_emission_not_matching_balances(self):
        Account.objects.filter(pk=ledger.issuance_account().pk).update(balance=-2000)
        codes = self.codes()
        self.assertTrue({"EMITTED_NOT_EQUAL_TO_BALANCES", "STORED_BALANCE_DIFFERS_FROM_LOG"} <= codes)

    def test_detects_hold_over_balance_and_overpaid_obligation(self):
        from ledger.models import Hold
        h = ledger.hold(self.a.pk, 100, key="h", reference_kind="c", reference_id=1).detail["hold_id"]
        Hold.objects.filter(pk=h).update(original_amount=10 ** 6, amount=10 ** 6)
        self.assertIn("HOLDS_EXCEED_BALANCE", self.codes())
        from ledger import obligations
        oid = obligations.open_obligation(self.a.pk, self.b.pk, 50, Nature.GOV_TRANSFER, key="o", reference_kind="t",
                                          reference_id=1).detail["obligation_id"]
        with connection.cursor() as c:
            c.execute("UPDATE ledger_obligation SET amount_paid = 50, status = 'open' WHERE id = %s", [oid])
        self.assertIn("OBLIGATION_OPEN_BUT_SETTLED", self.codes())

    def test_detects_counter_not_matching_recognized_requests(self):
        RemunerationCounter.objects.create(player_id=1, competence_day=1, c_s=5, c_t=5)
        self.assertIn("COUNTER_WITHOUT_RECOGNIZED_REQUESTS", self.codes())

    def test_detects_remuneration_entry_outside_payroll(self):
        with connection.cursor() as c:
            c.execute("UPDATE ledger_entry SET nature = 'wage' WHERE nature = 'sale'")
        self.assertIn("REMUNERATION_OUTSIDE_PAYROLL", self.codes())

    def test_detects_transaction_without_entries_and_closed_account_with_money(self):
        Transaction.objects.create(key="orphan", payload_hash="x", at=1)
        self.assertIn("TRANSACTION_WITHOUT_ENTRIES", self.codes())
        Account.objects.filter(pk=self.b.pk).update(closed=True)
        self.assertIn("CLOSED_ACCOUNT_NOT_EMPTY", self.codes())

    def test_detects_reversal_that_does_not_mirror(self):
        seq = Entry.objects.get(nature="sale").pk
        self.assertTrue(ledger.reverse(seq, "x", key="rv").ok)
        self.assertTrue(audit_ledger().ok)
        rev = Entry.objects.get(nature="reversal")
        with connection.cursor() as c:
            c.execute("UPDATE ledger_entry SET reverses_id = %s WHERE seq = %s", [Entry.objects.filter(nature="scenario_grant").first().pk, rev.pk])
        self.assertIn("REVERSAL_DOES_NOT_MIRROR_ORIGINAL", self.codes())

    def test_command_exit_code_and_json(self):
        out = StringIO()
        call_command("audit_ledger", stdout=out)
        self.assertIn("achados=0", out.getvalue())
        out = StringIO()
        call_command("audit_ledger", "--json", stdout=out)
        self.assertTrue(json.loads(out.getvalue())["ok"])
        Account.objects.filter(pk=self.a.pk).update(balance=1)
        with self.assertRaises(CommandError):
            call_command("audit_ledger", stdout=StringIO())

    def test_metrics(self):
        sink = ledger.sink_account()
        ledger.transfer(self.a.pk, sink.pk, 100, Nature.CAMPAIGN_COST, key="s", reference_kind="t", reference_id=1)
        ret = ledger.open_retention("x", "c:1")
        ledger.retain(self.a.pk, ret.pk, 50, key="r", reference_kind="t", reference_id=2)
        ledger.hold(self.a.pk, 10, key="h", reference_kind="t", reference_id=3)
        m = ledger_metrics()
        self.assertEqual((m["emitted_total"], m["in_circulation"], m["retained"], m["sink_destroyed"], m["reserved"]),
                         (1000, 850, 50, 100, 10))
        self.assertEqual(m["emitted_total"], m["in_circulation"] + m["retained"] + m["sink_destroyed"])
        self.assertEqual(m["accounts_granted"], 1)
        out = StringIO()
        call_command("ledger_metrics", stdout=out)
        self.assertEqual(json.loads(out.getvalue())["emitted_total"], 1000)


class AuditRobustnessTests(LedgerTestCase):
    """Adulteração direta (fora do ORM protegido) e valores fora do domínio viram ACHADOS estruturados, nunca exceção."""
    audit_at_end = False

    def setUp(self):
        super().setUp()
        self.a, self.b = self.company(1), self.company(2)
        self.fund(self.a, 1000)
        self.pay(self.a, self.b, 300, category="shop", operation="buy")
        self.sale_tx = Entry.objects.get(nature="sale").transaction

    def report(self):
        rep = audit_ledger()                                     # não pode levantar
        json.dumps(rep.to_dict(), default=str)                   # e o resultado é exportável
        return rep

    def codes(self):
        return {f["code"] for f in self.report().findings}

    def sql(self, statement, params=()):
        with connection.cursor() as c:
            c.execute(statement, params)

    def test_clean_baseline(self):
        self.assertTrue(self.report().ok, self.report().findings)

    # --- metadados da transação ---
    def test_tampered_transaction_instant_actor_hash_and_key(self):
        self.sql("UPDATE ledger_transaction SET at = at + 5 WHERE id = %s", [self.sale_tx.pk])
        self.assertIn("TRANSACTION_AT_MISMATCH", self.codes())
        self.sql("UPDATE ledger_transaction SET at = %s WHERE id = %s", [self.sale_tx.at, self.sale_tx.pk])
        self.assertTrue(self.report().ok)
        self.sql("UPDATE ledger_transaction SET actor = 'outro' WHERE id = %s", [self.sale_tx.pk])
        self.assertIn("TRANSACTION_ACTOR_MISMATCH", self.codes())
        self.sql("UPDATE ledger_transaction SET actor = %s WHERE id = %s", [self.sale_tx.actor, self.sale_tx.pk])
        self.sql("UPDATE ledger_transaction SET payload_hash = %s WHERE id = %s", ["0" * 64, self.sale_tx.pk])
        self.assertIn("TRANSACTION_HASH_MISMATCH", self.codes())
        self.sql("UPDATE ledger_transaction SET payload_hash = %s WHERE id = %s", [self.sale_tx.payload_hash, self.sale_tx.pk])
        self.sql("UPDATE ledger_transaction SET key = '' WHERE id = %s", [self.sale_tx.pk])
        self.assertIn("TRANSACTION_KEY_EMPTY", self.codes())

    def test_tampered_payload_content_is_caught_even_if_the_hash_is_recomputed(self):
        from ledger.services import payload_digest
        payload = dict(self.sale_tx.payload)
        payload["legs"] = [list(payload["legs"][0][:2]) + [payload["legs"][0][2] + 1] + list(payload["legs"][0][3:])]
        h = payload_digest(payload)
        self.sql("UPDATE ledger_transaction SET payload = %s, payload_hash = %s WHERE id = %s",
                 [json.dumps(payload), h, self.sale_tx.pk])
        codes = self.codes()
        self.assertIn("TRANSACTION_PAYLOAD_MISMATCH", codes)      # hash coerente com o payload, mas o payload não é o que foi gravado
        self.assertNotIn("TRANSACTION_HASH_MISMATCH", codes)

    def test_payload_of_the_wrong_shape(self):
        for raw in ('[1, 2]', '"texto"', '{}', 'null'):
            self.sql("UPDATE ledger_transaction SET payload = %s WHERE id = %s", [raw, self.sale_tx.pk])
            rep = self.report()
            self.assertFalse(rep.ok, raw)
            self.assertTrue({f["code"] for f in rep.findings} & {"TRANSACTION_PAYLOAD_INVALID", "TRANSACTION_HASH_MISMATCH",
                                                                 "TRANSACTION_PAYLOAD_MISMATCH"}, raw)

    def test_entry_reference_and_day_diverging_from_payload(self):
        self.sql("UPDATE ledger_entry SET reference_id = 'outra' WHERE nature = 'sale'")
        self.assertIn("TRANSACTION_PAYLOAD_MISMATCH", self.codes())
        self.sql("UPDATE ledger_entry SET reference_id = %s WHERE nature = 'sale'", [self.sale_tx.payload["reference"][1]])
        self.sql("UPDATE ledger_entry SET category = 'x' WHERE nature = 'sale'")
        self.assertIn("TRANSACTION_PAYLOAD_MISMATCH", self.codes())

    def test_entries_of_one_transaction_that_disagree_with_each_other(self):
        buyer, seller = self.company(3), self.company(4)
        self.fund(buyer, 1000)
        res = ledger.post_taxed_payment(buyer.pk, seller.pk, 1000, nature=Nature.SALE, tax_rate=D("0.1"), key="tx2",
                                        reference_kind="sale", reference_id=9)
        last = res.detail["seqs"][-1]
        self.sql("UPDATE ledger_entry SET at = at + 1 WHERE seq = %s", [last])
        self.assertTrue({"TRANSACTION_AT_MISMATCH"} <= self.codes())
        self.sql("UPDATE ledger_entry SET at = at - 1, reference_id = 'x' WHERE seq = %s", [last])
        self.assertIn("TRANSACTION_ENTRIES_INCONSISTENT", self.codes())

    # --- valores fora do domínio das enumerações ---
    def test_invalid_enum_values_are_findings_not_exceptions(self):
        h = ledger.hold(self.a.pk, 10, key="h", reference_kind="t", reference_id=1).detail["hold_id"]
        from ledger import obligations
        o = obligations.open_obligation(self.a.pk, self.b.pk, 5, Nature.GOV_TRANSFER, key="o", reference_kind="t",
                                       reference_id=1, competence_day=1).detail["obligation_id"]
        Account.objects.filter(pk=self.b.pk).update(kind="bogus")
        self.sql("UPDATE ledger_entry SET nature = 'inventada' WHERE nature = 'sale'")
        Hold.objects.filter(pk=h).update(status="???")
        Obligation.objects.filter(pk=o).update(status="zzz", nature="nada")
        rep = self.report()
        found = {(f["model"], f["field"]) for f in rep.findings if f["code"] == "INVALID_ENUM_VALUE"}
        self.assertTrue({("Account", "kind"), ("Entry", "nature"), ("Hold", "status"), ("Obligation", "status"),
                         ("Obligation", "nature")} <= found, found)
        for f in rep.findings:
            self.assertNotEqual(f["code"], "AUDIT_SECTION_FAILED", f)       # nenhuma seção caiu: foi tratado explicitamente
        self.assertTrue(all(f["invariant"] == 15 for f in rep.findings if f["code"] == "INVALID_ENUM_VALUE"))

    def test_invalid_enum_values_in_remuneration_requests_and_explained(self):
        from ledger.models import RemunerationRequest
        RemunerationRequest.objects.create(
            key="r1", payload_hash="x", player_id=1, payer=self.a, nature="bogus", due=10, competence_day=1, earned_at=1,
            policy="talvez", reference_kind="t", reference_id="1", status="quase")
        RemunerationRequest.objects.create(
            key="r2", payload_hash="x", player_id=1, payer=self.a, nature="political_salary", due=10, competence_day=1,
            earned_at=1, policy="pending", reference_kind="t", reference_id="1", status="recognized", recognized=10,
            pending=10, explained=["não é dict"])
        rep = self.report()
        found = {(f.get("model"), f.get("field")) for f in rep.findings if f["code"] == "INVALID_ENUM_VALUE"}
        self.assertTrue({("RemunerationRequest", "nature"), ("RemunerationRequest", "status"),
                         ("RemunerationRequest", "policy")} <= found, found)
        self.assertIn("REQUEST_EXPLAINED_INVALID", {f["code"] for f in rep.findings})
        self.assertNotIn("AUDIT_SECTION_FAILED", {f["code"] for f in rep.findings})

    def test_non_remuneration_nature_in_a_request_is_reported(self):
        from ledger.models import RemunerationRequest
        RemunerationRequest.objects.create(
            key="r1", payload_hash="x", player_id=1, payer=self.a, nature="sale", due=10, competence_day=1, earned_at=1,
            policy="pending", reference_kind="t", reference_id="1")
        self.assertIn("REQUEST_NATURE_NOT_REMUNERATION", self.codes())

    def test_unexpected_failure_in_one_section_becomes_a_finding_and_other_sections_still_run(self):
        from unittest import mock
        from ledger import audit
        Account.objects.filter(pk=self.a.pk).update(balance=1)         # um problema real, em outra seção
        boom = mock.Mock(side_effect=RuntimeError("falha inesperada"))
        sections = tuple((n, boom if n == "transactions" else f) for n, f in audit._SECTIONS)
        with mock.patch.object(audit, "_SECTIONS", sections):
            rep = audit.audit_ledger()
        codes = {f["code"] for f in rep.findings}
        self.assertIn("AUDIT_SECTION_FAILED", codes)
        self.assertIn("STORED_BALANCE_DIFFERS_FROM_LOG", codes)       # a seção do log ainda rodou
        failed = next(f for f in rep.findings if f["code"] == "AUDIT_SECTION_FAILED")
        self.assertEqual(failed["section"], "transactions")
        self.assertIn("falha inesperada", failed["error"])

    def test_command_reports_invalid_data_without_a_traceback(self):
        Account.objects.filter(pk=self.b.pk).update(kind="bogus")
        out = StringIO()
        with self.assertRaises(CommandError) as cm:
            call_command("audit_ledger", stdout=out)
        self.assertIn("violação", str(cm.exception))
        self.assertIn("INVALID_ENUM_VALUE", out.getvalue())
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("audit_ledger", "--json", stdout=out)
        data = json.loads(out.getvalue())
        self.assertFalse(data["ok"])
        self.assertTrue(any(f["code"] == "INVALID_ENUM_VALUE" for f in data["findings"]))

    def test_metrics_tolerate_unknown_account_kind(self):
        Account.objects.filter(pk=self.b.pk).update(kind="bogus")
        m = ledger_metrics()
        self.assertIn("bogus", m["by_account_kind"])
        self.assertEqual(m["emitted_total"], 1000)

    # (Entrada apontando para conta inexistente não é testada: a chave estrangeira do banco já a impede.)
