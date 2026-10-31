"""Fornecimento recorrente (design/18 §18.2, §18.5; checklist 18.13 itens 1-3, 7-12)."""
from companies import stock
from contracts import services
from contracts.constants import EventKind, ExecutionStatus, Status
from contracts.models import Contract, ContractEvent, ContractExecution, ContractsImmutableError
from ledger.models import Entry
from market.models import MarketTransaction

from .base import ContractBase


class SupplyExecutionTests(ContractBase):
    def test_an_active_supply_delivers_and_pays_every_day_then_closes_normally(self):
        cid = self.active_supply()
        seller0, buyer0, wheat0 = self.company_money(self.firm), self.company_money(self.mill), stock.quantity_of(self.firm, "wheat")
        money = self.circulation()
        self.tick(1)
        c = self.c(cid)
        self.assertEqual((c.status, c.next_sequence, c.next_due_day), (Status.ACTIVE.value, 1, self.day0 + 2))
        gross, tax = 100 * 1_000, 5_000                                 # 5% de imposto sobre vendas retido do valor (11 §11.1)
        self.assertEqual(self.company_money(self.mill), buyer0 - gross)
        self.assertEqual(self.company_money(self.firm) - seller0, gross - tax - 2_000)          # líquido da venda − folha do Dono do dia
        self.assertEqual((stock.quantity_of(self.firm, "wheat"), stock.quantity_of(self.mill, "wheat")), (wheat0 - 100, 100))
        self.tick(2)
        self.tick(3)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason, c.next_sequence, c.next_due_day), (Status.CLOSED.value, "completed", 3, None))
        self.assertEqual(stock.quantity_of(self.mill, "wheat"), 300)
        self.assertEqual(self.circulation(), money)                      # nada de dinheiro novo: imposto vai para a União
        txs = list(MarketTransaction.objects.order_by("id"))
        self.assertEqual([(t.channel, t.quantity, t.unit_price_cents, t.total_cents) for t in txs], [("contract", 100, 1_000, 100_000)] * 3)
        kinds = self.events(cid)
        self.assertEqual(kinds, ["created", "accepted", "accepted", "activated"] + ["executed"] * 3 + ["closed"])

    def test_running_the_same_tick_again_never_executes_an_occurrence_twice(self):
        cid = self.active_supply()
        self.tick(1)
        money, wheat = self.company_money(self.mill), stock.quantity_of(self.mill, "wheat")
        self.assertEqual(services.run_due(self.day0 + 1, self.clk.now())["executions"], 0)
        self.tick(1)
        self.assertEqual((self.company_money(self.mill), stock.quantity_of(self.mill, "wheat")), (money, wheat))
        self.assertEqual(ContractExecution.objects.filter(contract_id=cid).count(), 1)

    def test_a_tick_that_arrives_late_catches_up_every_missed_occurrence_in_order(self):
        cid = self.active_supply()
        self.tick(3)                                                      # o mundo pulou do dia 0 ao 3: ticks 1, 2 e 3 em ordem
        c = self.c(cid)
        self.assertEqual((c.status, c.next_sequence), (Status.CLOSED.value, 3))
        self.assertEqual([e.due_day for e in c.executions.order_by("sequence")], [self.day0 + 1, self.day0 + 2, self.day0 + 3])

    def test_weekly_and_monthly_calendars(self):
        from contracts import schedule
        from contracts.constants import Frequency
        from datetime import date
        jan31 = date(2027, 1, 31).toordinal()
        days = [date.fromordinal(schedule.shift(jan31, Frequency.MONTHLY, k)) for k in range(4)]
        self.assertEqual([(d.month, d.day) for d in days], [(1, 31), (2, 28), (3, 31), (4, 30)])       # dia do mês limitado ao fim do mês
        self.assertEqual(schedule.shift(10, Frequency.WEEKLY, 3), 31)
        self.assertEqual(schedule.count_until(10, Frequency.WEEKLY, 31), 4)
        self.assertEqual(schedule.count_until(10, Frequency.ONCE, 10), 1)
        cid = self.propose_supply(frequency="weekly", starts_on=self.day0 + 1, ends_on=self.day0 + 15)
        self.assertEqual(self.c(cid).occurrences, 3)
        once = self.propose_supply(frequency="once", starts_on=self.day0 + 2, ends_on=None)
        self.assertEqual((self.c(once).occurrences, self.c(once).ends_on), (1, self.day0 + 2))


class DeliveredQualityTests(ContractBase):
    def test_the_delivered_quality_is_frozen_at_delivery_and_blends_by_quantity_in_the_buyer_stock(self):
        from decimal import Decimal
        from companies.models import StockItem, StockMovement
        self.assertTrue(stock.credit_stock(self.mill, "wheat", 100, origin="t", key="q:seed", reference_kind="t", reference_id="1",
                                           quality=Decimal("80")).ok)
        StockItem.objects.filter(company_id=self.firm, product__key="wheat").update(quality=Decimal("40"))
        cid = self.active_supply(ends_on=self.day0 + 2)
        self.tick(1)
        e = ContractExecution.objects.get(contract_id=cid, sequence=0)
        self.assertEqual(e.detail["delivered_quality"], "40.000000")
        self.assertEqual(StockItem.objects.get(company_id=self.mill, product__key="wheat").quality, Decimal("60.000000"))      # (80·100 + 40·100)/200
        out, inc = (StockMovement.objects.get(key=f"contract:{cid}:exec:0:{k}") for k in ("out", "in"))
        self.assertEqual((out.explained["delivered_quality"], inc.explained["delivered_quality"]), ("40.000000", "40.000000"))
        StockItem.objects.filter(company_id=self.firm, product__key="wheat").update(quality=Decimal("90"))                     # muda DEPOIS
        self.assertEqual(ContractExecution.objects.get(pk=e.pk).detail["delivered_quality"], "40.000000")                       # congelada
        self.tick(2)
        self.assertEqual(ContractExecution.objects.get(contract_id=cid, sequence=1).detail["delivered_quality"], "90.000000")
        self.assertEqual(StockItem.objects.get(company_id=self.mill, product__key="wheat").quality, Decimal("70.000000"))      # (60·200 + 90·100)/300

    def test_an_unknown_quality_stays_unknown_never_zero(self):
        cid = self.active_supply(ends_on=self.day0 + 1)
        self.tick(1)
        self.assertIsNone(ContractExecution.objects.get(contract_id=cid, sequence=0).detail["delivered_quality"])


class SupplyFailureTests(ContractBase):
    def test_a_buyer_without_cash_fails_the_occurrence_with_who_what_and_how_much_and_nothing_moves(self):
        cid = self.active_supply(terms={"product": "wheat", "quantity": 100, "unit_price_cents": 10 ** 9}, penalty_cents=0)
        wheat, mill_money = stock.quantity_of(self.firm, "wheat"), self.company_money(self.mill)
        self.tick(1)
        c = self.c(cid)
        e = ContractExecution.objects.get(contract=c, sequence=0)
        self.assertEqual((e.status, e.failure_code, e.responsible, e.pending_quantity, e.pending_cents, e.ledger_key),
                         (ExecutionStatus.FAILED.value, "INSUFFICIENT_FUNDS", "b", 100, 100 * 10 ** 9, ""))
        self.assertEqual((c.status, c.failures, c.next_sequence), (Status.DEFAULTED.value, 1, 1))
        self.assertEqual((stock.quantity_of(self.firm, "wheat"), self.company_money(self.mill)), (wheat, mill_money))
        self.assertEqual(stock.quantity_of(self.mill, "wheat"), 0)
        self.assertEqual(MarketTransaction.objects.count(), 0)
        self.assertIn("default_entered", self.events(cid))

    def test_a_seller_without_stock_is_the_responsible_party(self):
        cid = self.active_supply(terms={"product": "wheat", "quantity": 1_000, "unit_price_cents": 100})
        self.tick(1)
        e = ContractExecution.objects.get(contract_id=cid, sequence=0)
        self.assertEqual((e.failure_code, e.responsible, e.pending_quantity), ("INSUFFICIENT_STOCK", "a", 1_000))
        self.assertEqual(self.c(cid).status, Status.DEFAULTED.value)

    def test_a_buyer_whose_stock_is_full_is_responsible_and_the_whole_act_is_undone(self):
        cid = self.active_supply()
        from companies import params
        from unittest import mock
        with mock.patch.dict(params.STOCK_CAPACITY_PER_STAR, {1: 50}):
            self.tick(1)
        e = ContractExecution.objects.get(contract_id=cid, sequence=0)
        self.assertEqual((e.failure_code, e.responsible), ("STOCK_FULL", "b"))
        self.assertEqual(stock.quantity_of(self.firm, "wheat"), 400)                  # a saída do vendedor foi desfeita junto
        self.assertEqual(MarketTransaction.objects.count(), 0)

    def test_the_default_is_cured_by_the_next_success_and_a_late_end_is_closed_with_failures(self):
        cid = self.active_supply(terms={"product": "wheat", "quantity": 250, "unit_price_cents": 100}, frequency="daily",
                                 starts_on=self.day0 + 1, ends_on=self.day0 + 3)
        self.tick(1)                                                      # 250: ok, sobram 150
        self.tick(2)                                                      # 250: falta estoque
        self.assertEqual(self.c(cid).status, Status.DEFAULTED.value)
        self.assertTrue(stock.credit_stock(self.firm, "wheat", 300, origin="test", key="seed:more", reference_kind="test",
                                           reference_id="2").ok)
        self.tick(3)                                                      # volta a cumprir: sai da inadimplência e termina
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason, c.failures), (Status.CLOSED.value, "completed_with_failures", 1))
        kinds = self.events(cid)
        self.assertLess(kinds.index("default_entered"), kinds.index("default_cured"))
        self.assertEqual(kinds.count("failed"), 1)

    def test_reaching_max_failures_breaks_the_contract_and_the_responsible_pays_the_penalty(self):
        cid = self.active_supply(terms={"product": "wheat", "quantity": 1_000, "unit_price_cents": 100}, max_failures=2,
                                 penalty_cents=30_000, ends_on=self.day0 + 5)
        seller0, buyer0, money = self.company_money(self.firm), self.company_money(self.mill), self.circulation()
        self.tick(1)
        self.assertEqual(self.c(cid).status, Status.DEFAULTED.value)
        self.tick(2)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason, c.next_due_day), (Status.BROKEN.value, "default_by_a", None))
        entries = Entry.objects.filter(transaction__key=f"contract:{cid}:penalty")
        self.assertEqual([(e.nature, e.amount) for e in entries], [("penalty", 30_000)])
        self.assertEqual(self.circulation(), money)                       # multa é transferência, não dinheiro novo (18.8)
        kinds = self.events(cid)
        self.assertEqual(kinds[-4:], ["failed", "penalty_applied", "remaining_cancelled", "broken"][-4:])
        pen = [e for e in services.contract_view(cid)["events"] if e["kind"] == "penalty_applied"][0]["data"]
        self.assertEqual((pen["responsible"], pen["to"], pen["amount_cents"], pen["paid"]), ("a", "b", 30_000, True))

    def test_max_failures_counts_consecutive_failures_and_a_success_resets_the_counter(self):
        cid = self.active_supply(terms={"product": "wheat", "quantity": 250, "unit_price_cents": 100}, max_failures=2,
                                 ends_on=self.day0 + 5, penalty_cents=1_000)
        self.tick(1)                                                      # cumpre (400 → 150)
        self.tick(2)                                                      # falha (1 seguida)
        self.assertEqual((self.c(cid).consecutive_failures, self.c(cid).status), (1, Status.DEFAULTED.value))
        self.assertTrue(stock.credit_stock(self.firm, "wheat", 300, origin="test", key="seed:r", reference_kind="test", reference_id="3").ok)
        self.tick(3)                                                      # cumpre: zera
        c = self.c(cid)
        self.assertEqual((c.consecutive_failures, c.failures, c.status), (0, 1, Status.ACTIVE.value))
        self.tick(4)                                                      # falha (1 seguida de novo): NÃO quebra, total já é 2
        c = self.c(cid)
        self.assertEqual((c.consecutive_failures, c.failures, c.status), (1, 2, Status.DEFAULTED.value))
        self.tick(5)                                                      # 2ª seguida: quebra
        self.assertEqual((self.c(cid).status, self.c(cid).end_reason), (Status.BROKEN.value, "default_by_a"))
        self.assertEqual(self.events(cid).count("failed"), 3)             # cada falha fica no histórico

    def test_without_max_failures_no_number_of_failures_breaks_the_contract(self):
        cid = self.active_supply(terms={"product": "wheat", "quantity": 1_000, "unit_price_cents": 100}, ends_on=self.day0 + 4)
        self.tick(4)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason, c.failures), (Status.CLOSED.value, "completed_with_failures", 4))

    def test_a_responsible_party_without_cash_for_the_penalty_owes_it_as_a_pending_obligation(self):
        from ledger.models import Obligation
        cid = self.active_supply(terms={"product": "wheat", "quantity": 100, "unit_price_cents": 10 ** 9}, max_failures=1,
                                 penalty_cents=10 ** 9, ends_on=self.day0 + 5)
        # o vendedor é quem cobra; o responsável (comprador) não tem R$ 10 milhões
        self.tick(1)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason), (Status.BROKEN.value, "default_by_b"))
        ob = Obligation.objects.get(key=f"contract:{cid}:penalty")
        self.assertEqual((ob.amount_due, ob.nature, ob.status), (10 ** 9, "penalty", "open"))
        self.assertFalse(Entry.objects.filter(transaction__key=f"contract:{cid}:penalty").exists())
        pen = [e for e in services.contract_view(cid)["events"] if e["kind"] == "penalty_applied"][0]["data"]
        self.assertFalse(pen["paid"])


class SupplyBreakTests(ContractBase):
    def test_a_voluntary_break_pays_the_penalty_to_the_other_party_and_marks_the_contract_broken(self):
        cid = self.active_supply(penalty_cents=40_000)
        self.tick(1)
        seller, buyer, money = self.company_money(self.firm), self.company_money(self.mill), self.circulation()
        res = services.break_contract(self.third.pk, cid, self.buyer_ref)
        self.assertTrue(res.ok, res)
        self.assertEqual((self.company_money(self.mill), self.company_money(self.firm)), (buyer - 40_000, seller + 40_000))
        self.assertEqual(self.circulation(), money)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason, c.next_due_day), (Status.BROKEN.value, "voluntary_break_by_b", None))
        self.tick(2)
        self.assertEqual(ContractExecution.objects.filter(contract_id=cid).count(), 1)         # nada mais é executado
        self.assertEqual(self.events(cid)[-4:], ["break_requested", "penalty_applied", "remaining_cancelled", "broken"])

    def test_a_break_without_cash_for_the_penalty_still_happens_and_the_unpaid_penalty_becomes_one_auditable_obligation(self):
        from ledger.models import Obligation
        cid = self.active_supply(terms={"product": "wheat", "quantity": 100, "unit_price_cents": 10 ** 9}, penalty_cents=10 ** 9)
        money = self.circulation()
        res = services.break_contract(self.third.pk, cid, self.buyer_ref)
        self.assertTrue(res.ok, res)
        c = self.c(cid)
        self.assertEqual((c.status, c.end_reason), (Status.BROKEN.value, "voluntary_break_by_b"))
        ob = Obligation.objects.get(key=f"contract:{cid}:penalty")
        self.assertEqual((ob.amount_due, ob.nature, ob.status, ob.debtor_id, ob.creditor_id),
                         (10 ** 9, "penalty", "open", self.account(("company", self.mill)), self.account(("company", self.firm))))
        self.assertFalse(Entry.objects.filter(transaction__key=f"contract:{cid}:penalty").exists())      # nada foi pago nem inventado
        self.assertEqual(self.circulation(), money)
        pen = [e for e in services.contract_view(cid)["events"] if e["kind"] == "penalty_applied"][0]["data"]
        self.assertEqual((pen["paid"], pen["cause"], pen["responsible"]), (False, "voluntary_break", "b"))
        self.assertRefused(services.break_contract(self.third.pk, cid, self.buyer_ref), "NOT_RUNNING")   # sem cobrança duplicada
        self.tick(1)
        self.assertEqual(Obligation.objects.filter(key=f"contract:{cid}:penalty").count(), 1)

    def test_the_unpaid_penalty_is_collected_later_by_the_global_settlement_without_duplicates(self):
        from ledger.models import Obligation
        cid = self.active_supply(terms={"product": "wheat", "quantity": 100, "unit_price_cents": 100_000}, penalty_cents=9_000_000)
        self.assertTrue(services.break_contract(self.third.pk, cid, self.buyer_ref).ok)                 # Moinho tem R$ 50 mil: não cobre
        cash = self.company_money(self.mill)
        self.tick(1)
        self.tick(2)
        ob = Obligation.objects.get(key=f"contract:{cid}:penalty")
        self.assertEqual((ob.status, ob.amount_paid > 0, ob.amount_paid <= ob.amount_due), ("open", True, True))
        paid = sum(e.amount for e in Entry.objects.filter(nature="penalty", transaction__key__startswith="settle:"))
        self.assertEqual(paid, ob.amount_paid)                                                          # só o que o caixa permitiu
        self.assertLessEqual(paid, cash)
        self.assertEqual(Obligation.objects.filter(key=f"contract:{cid}:penalty").count(), 1)

    def test_a_contract_without_penalty_can_be_broken_for_free_and_only_a_running_contract_can_be_broken(self):
        cid = self.active_supply(penalty_cents=0)
        self.assertTrue(services.break_contract(self.boss.pk, cid, self.seller_ref).ok)
        self.assertFalse(Entry.objects.filter(transaction__key=f"contract:{cid}:penalty").exists())
        self.assertRefused(services.break_contract(self.boss.pk, cid, self.seller_ref), "NOT_RUNNING")
        proposed = self.propose_supply()
        self.assertRefused(services.break_contract(self.boss.pk, proposed, self.seller_ref), "NOT_RUNNING")


class HistoryTests(ContractBase):
    def test_the_history_survives_the_end_and_cannot_be_changed(self):
        cid = self.active_supply()
        self.tick(3)
        view = services.contract_view(cid)
        self.assertEqual(view["status"], "closed")
        self.assertEqual(len(view["executions"]), 3)
        self.assertEqual([e["seq"] for e in view["events"]], list(range(1, len(view["events"]) + 1)))
        c = self.c(cid)
        with self.assertRaises(ContractsImmutableError):
            c.delete()
        event = ContractEvent.objects.filter(contract=c).first()
        event.data = {"x": 1}
        with self.assertRaises(ContractsImmutableError):
            event.save()
        with self.assertRaises(ContractsImmutableError):
            ContractExecution.objects.filter(contract=c).first().delete()
        c.terms = {"product": "wheat", "quantity": 1, "unit_price_cents": 1}
        with self.assertRaises(ContractsImmutableError):
            c.save()                                                      # 18.4: termos congelados

    audit_contracts_at_end = False

    def test_the_audit_detects_a_wrong_responsibility_classification_and_a_changed_delivered_quality(self):
        from contracts.audit import audit_contracts
        cid = self.active_supply(terms={"product": "wheat", "quantity": 1_000, "unit_price_cents": 100})
        self.tick(1)
        self.assertTrue(audit_contracts().ok)
        ContractExecution.objects.filter(contract_id=cid)                 # imutável: adultera por UPDATE direto, como um erro de banco
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute("UPDATE contracts_contractexecution SET responsible = 'b' WHERE contract_id = %s", [cid])
        self.assertIn("RESPONSIBILITY_MISMATCH", {f["code"] for f in audit_contracts().findings})

    def test_the_audit_detects_tampered_terms_and_a_missing_event(self):
        from contracts.audit import audit_contracts
        cid = self.active_supply()
        self.tick(1)
        self.assertTrue(audit_contracts().ok)
        Contract.objects.filter(pk=cid).update(terms={"product": "wheat", "quantity": 1, "unit_price_cents": 1})
        codes = {f["code"] for f in audit_contracts().findings}
        self.assertIn("TERMS_CHANGED", codes)
