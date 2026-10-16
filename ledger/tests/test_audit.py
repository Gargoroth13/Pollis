import json
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, connection, transaction

from ledger import services as ledger
from ledger.audit import audit_ledger, ledger_metrics
from ledger.constants import Nature
from ledger.models import Account, Entry, Obligation, RemunerationCounter, Transaction

from .base import LedgerTestCase


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
