"""
Recorde de patrimônio ligado às operações centrais do ledger (decisão do GD, 2026-11-03): toda alteração relevante do
patrimônio atualiza o recorde DEPOIS da operação financeira completa, inclusive operações automáticas, sem depender de ação do
jogador nem de varredura; e a atualização nunca se perde em silêncio.
"""
from decimal import Decimal
from unittest import mock

from django.db import transaction

from ledger import hooks as ledger_hooks, obligations, remuneration, services as ledger
from ledger.constants import Nature, Policy
from ledger.models import Entry, Obligation
from rankings import audit, live, records
from rankings.constants import Cat
from rankings.models import NetWorthCandidate, RankingHistorico

from .base import DAY, HOUR, T0, RankingsTestCase

D = Decimal


class LedgerLinkedRecordTests(RankingsTestCase):
    def rec(self):
        return RankingHistorico.objects.get(category=Cat.NET_WORTH_RECORD.value)

    def no_rec(self):
        return not RankingHistorico.objects.filter(category=Cat.NET_WORTH_RECORD.value).exists()

    def owe(self, debtor, creditor, amount, key, nature=Nature.WAGE):
        res = obligations.open_obligation(debtor.pk, creditor.pk, amount, nature, key=key, reference_kind="t", reference_id=key)
        self.assertTrue(res.ok, res)
        return Obligation.objects.get(pk=res.detail["obligation_id"])

    # --- alteração de saldo por operação automática, sem ação do jogador -----------------------------------------------

    def test_automatic_transfer_into_a_player_updates_the_record_without_any_player_action(self):
        self.fund(self.company(1), 50_000)
        self.assertTrue(self.pay(self.company(1), self.acct(), 12_000).ok)       # ex.: compra de uma empresa: o jogador só recebe
        r = self.rec()
        self.assertEqual((r.entity_id, r.value, r.recorded_at), (self.player.pk, 12_000, T0))

    def test_automatic_payroll_liquidation_updates_the_record_of_the_beneficiary(self):
        remuneration.register_limits_provider(lambda pid, nature, at: (10_000_000, 10_000_000, None))
        remuneration.register_political_due_provider(lambda pid, day: 0)
        self.fund(self.company(1), 100_000)
        self.assertTrue(remuneration.submit_remuneration(
            key="r1", player_id=self.player.pk, payer_id=self.company(1).pk, nature=Nature.WAGE, due=10_000, earned_at=T0,
            policy=Policy.PENDING, reference_kind="work", reference_id=1, tax_rate=D("0.1")).ok)
        self.assertTrue(self.no_rec())
        self.assertTrue(remuneration.liquidate_remuneration(batch="b").ok)
        self.assertEqual(self.rec().value, 9_000)                                # líquido de imposto, estado final do lote

    def test_scenario_grant_to_a_new_player_counts(self):
        self.fund(self.acct(), 4_321)
        self.assertEqual(self.rec().value, 4_321)

    def test_refused_and_replayed_operations_do_not_touch_the_record(self):
        self.fund(self.acct(), 1_000)
        a = self.acct()
        self.assertEqual(self.pay(a, self.company(1), 5_000).code, "INSUFFICIENT_FUNDS")
        before = list(RankingHistorico.objects.values())
        calls = []
        ledger_hooks.register_operation_hook("probe", lambda ids, at: calls.append(ids))
        self.addCleanup(ledger_hooks.unregister_operation_hook, "probe")
        res = ledger.transfer(a.pk, self.company(1).pk, 100, Nature.SALE, key="k", reference_kind="t", reference_id="1")
        self.assertTrue(res.ok)
        again = ledger.transfer(a.pk, self.company(1).pk, 100, Nature.SALE, key="k", reference_kind="t", reference_id="1")
        self.assertTrue(again.detail["already_posted"])
        self.assertEqual(len(calls), 1)                                         # a repetição idempotente não dispara de novo
        self.assertEqual(list(RankingHistorico.objects.values()), before)

    # --- obrigações: abertura, pagamento parcial, quitação e cancelamento ----------------------------------------------

    def test_opening_an_obligation_updates_the_creditor_through_the_receivable(self):
        self.owe(self.company(1), self.acct(), 8_000, "o1")                    # nenhum dinheiro se move
        self.assertEqual(self.rec().value, 8_000)
        self.assertEqual(self.rec().metadata["receivables"], 8_000)

    def test_opening_an_obligation_as_debtor_cannot_create_a_record(self):
        self.fund(self.acct(), 1_000)
        v = self.rec().value
        self.owe(self.acct(), self.company(1), 400, "o1")                      # patrimônio cai
        self.assertEqual(self.rec().value, v)

    def test_partial_payment_is_evaluated_on_the_final_state_not_in_the_middle_of_the_operation(self):
        """A quitação posta a transação (saldo do credor sobe) e SÓ DEPOIS reduz o crédito a receber. Avaliar no meio contaria
        o dinheiro e o crédito juntos (pico falso): o gancho roda uma vez, no fim da operação."""
        poor = self.company(3)
        self.owe(poor, self.acct(), 10_000, "o1")
        self.assertEqual(self.rec().value, 10_000)
        self.fund(poor, 4_000)
        res = obligations.settle_obligations(poor.pk, batch_key="s1")
        self.assertTrue(res.ok, res)
        paid = res.detail["total_gross"]
        self.assertEqual(paid, 4_000)
        nw = live.net_worth_of(self.player.pk)
        self.assertEqual(nw["value"], 10_000)                                  # sem imposto: dinheiro substitui o crédito
        self.assertEqual(self.rec().value, 10_000)                             # e o recorde não ficou em 14.000 (pico falso)

    def test_partial_payment_with_withholding_never_records_a_transient_peak(self):
        remuneration.register_limits_provider(lambda pid, nature, at: (10_000_000, 10_000_000, None))
        remuneration.register_political_due_provider(lambda pid, day: 0)
        poor = self.company(3)
        self.assertTrue(remuneration.submit_remuneration(
            key="r1", player_id=self.player.pk, payer_id=poor.pk, nature=Nature.WAGE, due=10_000, earned_at=T0,
            policy=Policy.PENDING, reference_kind="work", reference_id=1, tax_rate=D("0.1")).ok)
        self.assertTrue(remuneration.liquidate_remuneration(batch="b").ok)      # vira obrigação de 10.000 (sem caixa)
        self.assertEqual(self.rec().value, 10_000)
        self.fund(poor, 6_000)
        self.assertTrue(obligations.settle_obligations(poor.pk, batch_key="s1").ok)
        nw = live.net_worth_of(self.player.pk)
        self.assertLess(nw["value"], 10_000)                                   # o imposto retido reduz o patrimônio
        self.assertEqual(self.rec().value, 10_000)

    def test_full_settlement_and_cancellation_keep_the_historical_peak(self):
        poor = self.company(3)
        ob = self.owe(poor, self.acct(), 10_000, "o1")
        ob2 = self.owe(poor, self.acct(), 5_000, "o2")
        self.assertEqual(self.rec().value, 15_000)
        self.assertTrue(obligations.cancel_obligation(ob2.pk, "erro").ok)       # o crédito some: patrimônio cai
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 10_000)
        self.assertEqual(self.rec().value, 15_000)
        self.fund(poor, 10_000)
        self.assertTrue(obligations.settle_obligations(poor.pk, batch_key="s1").ok)
        ob.refresh_from_db()
        self.assertEqual(ob.status, "paid")
        self.assertEqual(self.rec().value, 15_000)

    def test_creditor_record_updates_when_a_debtor_pays_more_than_before(self):
        """Quitação que não altera o patrimônio do credor não cria recorde; abertura posterior maior sim."""
        poor = self.company(3)
        self.owe(poor, self.acct(), 1_000, "o1")
        self.owe(poor, self.acct(), 2_000, "o2")
        self.assertEqual(self.rec().value, 3_000)

    # --- pico revertido antes da varredura diária --------------------------------------------------------------------

    def test_peak_reverted_before_the_daily_sweep_is_still_recorded(self):
        a = self.acct()
        self.fund(a, 20_000)                                                    # pico
        self.assertTrue(self.pay(a, self.company(1), 19_500).ok)               # revertido logo depois
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 500)
        self.assertEqual(records.sweep_net_worth_record().reason, "NOT_GREATER")       # a varredura só vê 500: não perdeu o pico
        self.assertEqual(self.rec().value, 20_000)

    def test_peak_through_a_receivable_that_is_later_cancelled_is_recorded(self):
        ob = self.owe(self.company(1), self.acct(), 30_000, "o1")
        self.assertTrue(obligations.cancel_obligation(ob.pk, "motivo").ok)
        self.assertEqual(live.net_worth_of(self.player.pk)["value"], 0)
        self.assertEqual(self.rec().value, 30_000)

    # --- atomicidade ----------------------------------------------------------------------------------------------------

    def test_record_is_rolled_back_with_the_operation_when_the_outer_transaction_fails(self):
        self.fund(self.company(1), 50_000)
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.assertTrue(self.pay(self.company(1), self.acct(), 9_000).ok)
                self.assertEqual(self.rec().value, 9_000)                       # visível dentro da transação
                raise RuntimeError("desfaz tudo")
        self.assertTrue(self.no_rec())                                          # o pico nunca existiu
        self.assertEqual(ledger.balance_of(self.acct().pk), 0)

    def test_failure_writing_the_record_creates_a_durable_candidate_and_the_money_operation_still_commits(self):
        self.fund(self.company(1), 50_000)
        with mock.patch.object(records, "offer_value_record", side_effect=RuntimeError("falha de gravação")):
            with self.assertLogs("rankings.records", level="ERROR"):
                self.assertTrue(self.pay(self.company(1), self.acct(), 7_000).ok)
        self.assertEqual(ledger.balance_of(self.acct().pk), 7_000)             # a operação financeira valeu
        self.assertTrue(self.no_rec())
        cand = NetWorthCandidate.objects.get()
        self.assertEqual((cand.player_id, cand.value, cand.at), (self.player.pk, 7_000, T0))
        self.assertIn("falha de gravação", cand.last_error)
        self.assertFalse(audit.audit_rankings()["ok"])                          # a pendência é visível na auditoria
        self.assertIn("NET_WORTH_CANDIDATES_PENDING", [f["code"] for f in audit.audit_rankings()["findings"]])
        self.assertEqual(records.drain_net_worth_candidates(), 1)               # o retry aplica com o valor e o instante originais
        r = self.rec()
        self.assertEqual((r.value, r.recorded_at), (7_000, T0))
        self.assertFalse(NetWorthCandidate.objects.exists())
        self.assertTrue(audit.audit_rankings()["ok"])

    def test_candidate_after_the_peak_reverted_still_restores_the_peak(self):
        a = self.acct()
        with mock.patch.object(records, "offer_value_record", side_effect=RuntimeError("x")):
            with self.assertLogs("rankings.records", level="ERROR"):
                self.fund(a, 20_000)
        self.assertTrue(self.pay(a, self.company(1), 19_000).ok)               # já revertido quando o retry rodar
        records.sweep_net_worth_record()                                        # drena primeiro
        self.assertEqual(self.rec().value, 20_000)

    def test_drain_failure_keeps_the_candidate_and_counts_attempts(self):
        NetWorthCandidate.objects.create(player_id=self.player.pk, value=900, at=T0, metadata={})
        with mock.patch.object(records, "offer_value_record", side_effect=RuntimeError("ainda falhando")):
            with self.assertLogs("rankings.records", level="ERROR"):
                self.assertEqual(records.drain_net_worth_candidates(), 0)
        c = NetWorthCandidate.objects.get()
        self.assertEqual(c.attempts, 1)
        self.assertEqual(records.drain_net_worth_candidates(), 1)

    def test_drain_applies_candidates_in_chronological_order_with_earliest_tie(self):
        NetWorthCandidate.objects.create(player_id=2, value=500, at=T0 + HOUR, metadata={})
        NetWorthCandidate.objects.create(player_id=1, value=500, at=T0, metadata={})
        records.drain_net_worth_candidates()
        self.assertEqual((self.rec().entity_id, self.rec().recorded_at), (1, T0))

    def test_if_not_even_the_candidate_can_be_saved_the_whole_operation_is_undone(self):
        self.fund(self.company(1), 50_000)
        with mock.patch.object(records, "offer_value_record", side_effect=RuntimeError("a")), \
                mock.patch.object(NetWorthCandidate.objects, "create", side_effect=RuntimeError("b")):
            with self.assertLogs("rankings.records", level="ERROR"):
                with self.assertRaises(RuntimeError):
                    with transaction.atomic():
                        self.pay(self.company(1), self.acct(), 3_000)
        self.assertEqual(ledger.balance_of(self.acct().pk), 0)                  # nada se perde: a operação inteira foi desfeita
        self.assertFalse(Entry.objects.filter(to_account=self.acct(), nature="sale").exists())
