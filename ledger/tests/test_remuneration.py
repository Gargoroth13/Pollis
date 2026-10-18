import itertools
import random
from decimal import Decimal

from django.db import transaction

from core.timeline import game_ts
from ledger import obligations, remuneration, services as ledger
from ledger.constants import Nature, Policy
from ledger.models import Entry, Obligation, RemunerationCounter, RemunerationRequest
from players.tests.base import PlayerTestCase

from .base import T0, DAY, LedgerHelpers

D = Decimal
WAGE, OWNER, MIL, POL = Nature.WAGE, Nature.OWNER_SALARY, Nature.MILITARY_PAY, Nature.POLITICAL_SALARY


class PayrollTestCase(LedgerHelpers, PlayerTestCase):
    def setUp(self):
        super().setUp()
        self.ledger_setup()
        self.limits = {"W": 100, "S": 150, "T": None}
        self.political = {}
        remuneration.register_limits_provider(lambda pid, nature, at: (self.limits["W"], self.limits["S"], self.limits["T"]))
        remuneration.register_political_due_provider(lambda pid, day: self.political.get((pid, day), 0))
        self.company_payer = self.company(1)
        self.fund(self.company_payer, 1_000_000)
        self.n = 0

    @property
    def day(self):
        from ledger.money import competence_day_of
        return competence_day_of(T0)

    def submit(self, player=None, nature=WAGE, due=100, payer=None, earned_at=None, policy=Policy.PENDING, key=None,
               rate=D(0), **kw):
        self.n += 1
        return remuneration.submit_remuneration(
            key=key or f"req{self.n}", player_id=(player or self.player).pk, payer_id=(payer or self.company_payer).pk,
            nature=nature, due=due, earned_at=T0 if earned_at is None else earned_at, policy=policy,
            reference_kind="work", reference_id=self.n, tax_rate=rate, **kw)

    def counters(self, player=None, day=None):
        return RemunerationCounter.objects.get(player_id=(player or self.player).pk, competence_day=day or self.day)

    def req(self, key):
        return RemunerationRequest.objects.get(key=key)

    def liquidate(self, batch="b", **kw):
        res = remuneration.liquidate_remuneration(batch=batch, **kw)
        self.assertTrue(res.ok, res)
        return res

    def pbal(self, player=None):
        return ledger.balance_of(ledger.player_account((player or self.player).pk).pk)


class SubmitTests(PayrollTestCase):
    def test_submit_moves_no_money(self):
        self.assertTrue(self.submit().ok)
        self.assertEqual(self.pbal(), 0)
        self.assertEqual(Entry.objects.filter(nature="wage").count(), 0)

    def test_validation(self):
        self.assertEqual(self.submit(nature=Nature.SALE).code, "NATURE_INVALID")
        self.assertEqual(self.submit(due=0).code, "AMOUNT_NOT_POSITIVE")
        self.assertEqual(self.submit(due=1.5).code, "AMOUNT_NOT_IN_CENTAVOS")
        self.assertEqual(self.submit(rate=D("1.5")).code, "TAX_RATE_INVALID")
        self.assertEqual(self.submit(rate=0.1).code, "TAX_RATE_INVALID")
        self.assertEqual(self.submit(payer=type("A", (), {"pk": 999999})()).code, "ACCOUNT_NOT_FOUND")
        self.assertEqual(remuneration.submit_remuneration(
            key="k", player_id=999999, payer_id=self.company_payer.pk, nature=WAGE, due=1, earned_at=T0, policy=Policy.PENDING,
            reference_kind="w", reference_id=1).code, "ACCOUNT_OWNER_NOT_FOUND")
        self.assertEqual(remuneration.submit_remuneration(
            key="", player_id=self.player.pk, payer_id=self.company_payer.pk, nature=WAGE, due=1, earned_at=T0,
            policy=Policy.PENDING, reference_kind="w", reference_id=1).code, "REFERENCE_REQUIRED")
        pacc = ledger.player_account(self.player.pk)
        self.assertEqual(self.submit(payer=pacc).code, "SAME_ACCOUNT")

    def test_idempotent_submit_and_conflict(self):
        a = self.submit(key="k")
        n = self.n
        b = remuneration.submit_remuneration(key="k", player_id=self.player.pk, payer_id=self.company_payer.pk, nature=WAGE,
                                             due=100, earned_at=T0, policy=Policy.PENDING, reference_kind="work",
                                             reference_id=n, tax_rate=D(0))
        self.assertTrue(b.detail["already_posted"])
        self.assertEqual(a.detail["request_id"], b.detail["request_id"])
        self.assertEqual(self.submit(key="k", due=101).code, "IDEMPOTENCY_CONFLICT")

    def test_no_limits_provider_refuses_without_losing_request(self):
        remuneration.clear_providers()
        self.submit(key="k")
        res = remuneration.liquidate_remuneration(batch="b")
        self.assertEqual(res.code, "REMUNERATION_LIMITS_UNSPECIFIED")
        self.assertEqual(self.req("k").status, "submitted")
        self.assertEqual(remuneration.preview_remuneration(self.player.pk, WAGE, 10).code, "REMUNERATION_LIMITS_UNSPECIFIED")

    def test_empty_batch_is_ok(self):
        self.assertEqual(self.liquidate().detail["count"], 0)


class RecognitionTests(PayrollTestCase):
    def test_basic_payment_updates_counters_and_balance(self):
        self.submit(key="k", due=100)
        res = self.liquidate()
        self.assertEqual(res.detail["processed"][0]["outcome"], "PAID")
        self.assertEqual(self.pbal(), 100)
        c = self.counters()
        self.assertEqual((c.c_s, c.c_t, c.c_p), (100, 100, 0))
        r = self.req("k")
        self.assertEqual((r.status, r.recognized, r.paid, r.pending, r.discarded), ("recognized", 100, 100, 0, 0))
        self.assertEqual(r.position, 0)

    def test_cap_s_is_max_of_w_and_s_and_discards_excess_without_obligation(self):
        self.submit(key="a", due=100)
        self.submit(key="b", due=100, earned_at=T0 + 1)
        self.liquidate()
        self.assertEqual((self.req("a").recognized, self.req("b").recognized), (100, 50))     # cap_S = 150
        self.assertEqual(self.req("b").discarded, 50)
        self.assertEqual(Obligation.objects.count(), 0)
        self.assertEqual(self.pbal(), 150)

    def test_w_prevails_over_smaller_s(self):
        self.limits.update(W=100, S=40)
        self.submit(key="a", due=500)
        self.liquidate()
        self.assertEqual(self.req("a").recognized, 100)

    def test_t_binding_even_below_w(self):
        self.limits.update(W=100, S=40, T=70)
        self.submit(key="a", due=500)
        self.liquidate()
        self.assertEqual(self.req("a").recognized, 70)
        self.assertIn("sobra_T", self.req("a").explained["restricted_by"])

    def test_t_counts_all_remuneration_and_s_only_work(self):
        self.limits.update(W=100, S=1000, T=250)
        self.submit(key="w", due=100)
        self.submit(key="o", nature=OWNER, due=100, earned_at=T0 + 1)
        self.submit(key="m", nature=MIL, due=100, earned_at=T0 + 2)
        self.liquidate()
        self.assertEqual([self.req(k).recognized for k in ("w", "o", "m")], [100, 100, 50])
        c = self.counters()
        self.assertEqual((c.c_s, c.c_t), (250, 250))

    def test_military_excess_not_paid_not_obligation(self):
        self.limits.update(W=100, S=150, T=None)
        self.submit(key="m", nature=MIL, due=400)       # W × 4 (General); cap_S = 150
        self.liquidate()
        r = self.req("m")
        self.assertEqual((r.recognized, r.discarded, r.pending), (150, 250, 0))
        self.assertEqual(Obligation.objects.count(), 0)

    def test_no_ceiling_means_infinite(self):
        self.limits.update(W=100, S=10 ** 9, T=None)
        self.submit(key="a", due=10 ** 6)
        self.liquidate()
        self.assertEqual(self.req("a").recognized, 10 ** 6)

    def test_days_of_competence_are_independent_and_do_not_accumulate(self):
        self.submit(key="d1", due=150, earned_at=T0)
        self.submit(key="d2", due=150, earned_at=T0 + DAY)
        self.liquidate()
        self.assertEqual((self.req("d1").recognized, self.req("d2").recognized), (150, 150))
        self.assertEqual(self.counters(day=self.day).c_s, 150)
        self.assertEqual(self.counters(day=self.day + 1).c_s, 150)

    def test_competence_is_earned_day_not_liquidation_day(self):
        self.submit(key="old", due=150, earned_at=T0)
        self.clk.set(T0 + 3 * DAY) if hasattr(self.clk, "set") else self.clk.advance(3 * DAY)
        self.submit(key="new", due=150, earned_at=T0 + 3 * DAY)
        self.liquidate()
        self.assertEqual(self.counters(day=self.day).c_s, 150)
        self.assertEqual(self.counters(day=self.day + 3).c_s, 150)

    def test_law_change_does_not_recalculate_recognized(self):
        self.limits.update(S=150)
        self.submit(key="a", due=150)
        self.liquidate("b1")
        self.limits.update(W=50, S=100)             # lei muda depois
        self.submit(key="b", due=50, earned_at=T0 + 1)
        self.liquidate("b2")
        self.assertEqual(self.req("a").recognized, 150)         # permanece
        self.assertEqual(self.req("b").recognized, 0)           # novo teto 100 < já reconhecido 150
        self.assertEqual(self.counters().c_s, 150)
        self.assertEqual(self.pbal(), 150)

    def test_zero_room_marks_processed_and_does_not_retry(self):
        self.submit(key="a", due=150)
        self.submit(key="b", due=10, earned_at=T0 + 1)
        self.liquidate()
        self.assertEqual((self.req("b").status, self.req("b").recognized, self.req("b").explained["outcome"]),
                         ("recognized", 0, "NO_ROOM"))
        self.assertEqual(self.liquidate("b2").detail["count"], 0)

    def test_explained_is_structured(self):
        self.limits.update(T=120)
        self.submit(key="a", due=100, rate=D("0.1"))
        self.liquidate()
        ex = self.req("a").explained
        for k in ("factors", "formula", "restricted_by", "outcome", "position", "tax", "net", "counters_after", "policy"):
            self.assertIn(k, ex)
        f = ex["factors"]
        for k in ("due", "W", "S", "T", "C_S", "C_T", "C_P", "P_reservada", "sobra_S", "sobra_T"):
            self.assertIn(k, f)
        self.assertEqual((ex["tax"], ex["net"]), (10, 90))
        self.assertTrue(any(s["kind"] == "cap" for s in ex["formula"]["steps"]))

    def test_preview_matches_liquidation_and_writes_nothing(self):
        self.limits.update(T=120)
        self.submit(key="a", due=100)
        self.liquidate()
        before = RemunerationCounter.objects.count()
        pv = remuneration.preview_remuneration(self.player.pk, WAGE, 100)
        self.assertEqual(pv.detail["recognized"], 20)
        self.assertIn("sobra_T", pv.detail["restricted_by"])
        self.assertEqual(RemunerationCounter.objects.count(), before)
        self.assertEqual(self.counters().c_t, 100)


class PoliticalTests(PayrollTestCase):
    def setUp(self):
        super().setUp()
        self.limits.update(W=100, S=150, T=200)
        self.political[(self.player.pk, self.day)] = 80
        self.union = ledger.union_account()
        self.fund(self.union, 1_000_000)

    def pol(self, key="pol", due=80, payer=None, **kw):
        return self.submit(key=key, nature=POL, due=due, payer=payer or self.union, **kw)

    def test_political_reserve_protects_t_regardless_of_arrival(self):
        # sem a reserva, o trabalho (150) comeria o teto e o político só teria 50
        self.submit(key="w", due=150)
        self.liquidate("b1")
        self.assertEqual(self.req("w").recognized, 120)          # 200 − 0 − P_reservada(80)
        self.pol()
        self.liquidate("b2")
        self.assertEqual(self.req("pol").recognized, 80)
        self.assertEqual(self.counters().c_t, 200)

    def test_same_batch_any_submission_order_same_result(self):
        outcomes = []
        for order in (("w", "pol"), ("pol", "w")):
            sid = transaction.savepoint()
            for k in order:
                self.submit(key=k, due=150) if k == "w" else self.pol(key=k)
            self.liquidate()
            outcomes.append((self.req("w").recognized, self.req("pol").recognized, self.req("w").position, self.req("pol").position))
            transaction.savepoint_rollback(sid)
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(outcomes[0], (120, 80, 1, 0))           # político primeiro na ordem estável

    def test_consumption_without_double_subtraction(self):
        self.pol()
        self.liquidate("b1")
        c = self.counters()
        self.assertEqual((c.c_p, c.c_t, c.p_released), (80, 80, 0))
        self.submit(key="w", due=150)
        self.liquidate("b2")
        # P_reservada = 80 − 80 − 0 = 0: a parcela política NÃO é descontada duas vezes (sobra_T = 200 − 80 = 120)
        self.assertEqual(self.req("w").recognized, 120)
        self.assertEqual(self.req("w").explained["factors"]["P_reservada"], 0)

    def test_release_when_t_limits_political(self):
        self.limits.update(T=50)
        self.pol()
        self.liquidate("b1")
        c = self.counters()
        self.assertEqual((self.req("pol").recognized, c.c_p, c.p_released), (50, 50, 30))
        self.submit(key="w", due=150)
        self.liquidate("b2")
        self.assertEqual(self.req("w").recognized, 0)            # T esgotado; reserva liberada não bloqueia nada além de T
        self.assertEqual(self.req("w").explained["factors"]["P_reservada"], 0)

    def test_political_not_limited_by_cs_and_counts_in_ct(self):
        self.submit(key="w", due=150)
        self.pol()
        self.liquidate()
        c = self.counters()
        self.assertEqual((c.c_s, c.c_t, c.c_p), (120, 200, 80))

    def test_no_provider_means_no_reservation(self):
        self.political.clear()
        self.submit(key="w", due=150)
        self.liquidate()
        self.assertEqual(self.req("w").recognized, 150)

    def test_substitute_gets_no_retroactive_and_reserve_follows_occupant(self):
        other = self.new_player("substituto")
        self.political.clear()
        self.political[(other.pk, self.day)] = 80
        self.submit(player=other, key="w", due=150)
        self.liquidate()
        self.assertEqual(self.req("w").recognized, 120)           # reserva do ocupante atual
        # o primeiro jogador deixou o cargo: provedor devolve 0; nada retroativo é gerado para o substituto
        self.assertEqual(RemunerationRequest.objects.filter(player_id=other.pk, nature="political_salary").count(), 0)

    def test_political_two_requests_same_day_keep_reservation_for_second(self):
        self.political[(self.player.pk, self.day)] = 100
        self.pol(key="p1", due=40)
        self.submit(key="w", due=150, earned_at=T0 + 5)
        self.liquidate("b1")
        # p1 reconheceu 40 (reserva restante 60 continua protegendo o teto)
        self.assertEqual(self.req("w").recognized, 100)           # 200 − 40 − 60
        self.pol(key="p2", due=60, earned_at=T0 + 10)
        self.liquidate("b2")
        self.assertEqual(self.req("p2").recognized, 60)
        self.assertEqual(self.counters().c_t, 200)

    def test_political_pending_when_union_has_no_cash_then_settled(self):
        poor = self.company(77)
        self.pol(payer=poor, key="pp")
        res = self.liquidate()
        self.assertEqual(res.detail["processed"][0]["outcome"], "PENDING")
        ob = Obligation.objects.get()
        self.assertEqual((ob.amount_due, ob.nature, ob.competence_day), (80, "political_salary", self.day))
        self.assertEqual(self.counters().c_p, 80)                  # contador conta o reconhecido, não o pago
        self.assertEqual(self.pbal(), 0)
        self.fund(poor, 1000)
        obligations.settle_obligations(poor.pk, batch_key="s")
        self.assertEqual(self.pbal(), 80)
        self.assertEqual(self.counters().c_p, 80)                  # quitar não reaplica limite nem altera contadores
        self.assertEqual(RemunerationRequest.objects.get(key="pp").obligation_id, ob.pk)


class PolicyAndTaxTests(PayrollTestCase):
    def test_refuse_policy_without_cash_recognizes_nothing(self):
        poor = self.company(50)
        res = remuneration.pay_remuneration_now(
            key="r", player_id=self.player.pk, payer_id=poor.pk, nature=WAGE, due=100, earned_at=T0, policy=Policy.REFUSE,
            reference_kind="work", reference_id=1)
        self.assertFalse(res.ok)
        self.assertEqual(res.code, "INSUFFICIENT_FUNDS")
        self.assertFalse(RemunerationCounter.objects.filter(c_t__gt=0).exists())    # contador intocado: o limite vale para o próximo
        self.assertEqual(self.req("r").status, "refused")
        self.assertEqual(self.pbal(), 0)

    def test_refuse_leaves_limit_for_next_request_in_sequence(self):
        poor = self.company(50)
        self.fund(poor, 100)
        self.submit(key="a", due=150, payer=poor, policy=Policy.REFUSE)
        self.submit(key="b", due=150, earned_at=T0 + 1, policy=Policy.PENDING)
        self.liquidate()
        self.assertEqual(self.req("a").status, "refused")
        self.assertEqual(self.req("b").recognized, 150)             # o limite não foi consumido por a

    def test_pending_policy_sums_counters_but_pays_later_with_tax(self):
        poor = self.company(51)
        self.submit(key="a", due=100, payer=poor, rate=D("0.1"))
        self.liquidate()
        r = self.req("a")
        self.assertEqual((r.recognized, r.paid, r.pending, r.tax, r.net), (100, 0, 100, 10, 90))
        self.assertEqual(self.counters().c_s, 100)
        self.fund(poor, 100)
        obligations.settle_obligations(poor.pk, batch_key="s")
        self.assertEqual((self.pbal(), self.bal(ledger.union_account())), (90, 10))

    def test_income_tax_splits_gross_net_and_tax_one_transaction(self):
        self.submit(key="a", due=1001, rate=D("0.15"))
        self.limits.update(S=10_000)
        self.liquidate()
        r = self.req("a")
        self.assertEqual((r.recognized, r.tax, r.net), (1001, 150, 851))          # 150,15 → 150 (HALF_EVEN)
        self.assertEqual(self.counters().c_s, 1001)                              # contador usa o bruto (R1)
        tx = Entry.objects.filter(transaction__key="remuneration:a")
        self.assertEqual(sorted((e.nature, e.amount) for e in tx), [("tax_income", 150), ("wage", 851)])
        self.assertEqual(self.pbal(), 851)

    def test_tax_routed_to_retention_by_resolver(self):
        ret = ledger.open_retention("m", "a:1")
        ledger.register_tax_resolver("m", lambda t, at: ret.pk)
        self.submit(key="a", due=100, rate=D("0.1"), tax_territory="city:3")
        self.liquidate()
        self.assertEqual((self.bal(ret), self.bal(ledger.union_account()), self.pbal()), (10, 0, 90))

    def test_ambiguous_tax_route_aborts_whole_batch(self):
        r1, r2 = ledger.open_retention("a", "a:1"), ledger.open_retention("b", "b:1")
        ledger.register_tax_resolver("x", lambda t, at: r1.pk)
        ledger.register_tax_resolver("y", lambda t, at: r2.pk)
        self.submit(key="plain", due=100)
        self.submit(key="taxed", due=100, rate=D("0.1"), earned_at=T0 + 1)
        res = remuneration.liquidate_remuneration(batch="b")
        self.assertEqual(res.code, "TAX_ROUTE_AMBIGUOUS")
        self.assertEqual(RemunerationRequest.objects.filter(status="submitted").count(), 2)
        self.assertEqual(self.pbal(), 0)
        self.assertFalse(RemunerationCounter.objects.filter(c_t__gt=0).exists())

    def test_union_pays_own_wages_with_self_compensated_income_tax(self):
        union = ledger.union_account()
        self.fund(union, 1000)
        self.submit(key="a", due=100, payer=union, rate=D("0.1"))
        self.liquidate()
        self.assertEqual((self.pbal(), self.bal(union)), (90, 910))                # só o líquido sai
        self.assertFalse(Entry.objects.filter(from_account=union, to_account=union).exists())

    def test_pay_now_returns_processed_request_and_is_idempotent(self):
        kw = dict(key="n", player_id=self.player.pk, payer_id=self.company_payer.pk, nature=WAGE, due=100, earned_at=T0,
                  policy=Policy.PENDING, reference_kind="work", reference_id=1)
        r1 = remuneration.pay_remuneration_now(**kw)
        r2 = remuneration.pay_remuneration_now(**kw)
        self.assertTrue(r1.ok and r2.ok)
        self.assertEqual((r1.detail["paid"], r2.detail["already_posted"]), (100, True))
        self.assertEqual(self.pbal(), 100)
        self.assertEqual(self.counters().c_s, 100)

    def test_liquidate_twice_does_not_repay(self):
        self.submit(key="a", due=100)
        self.liquidate("b1")
        self.liquidate("b2")
        self.assertEqual(self.pbal(), 100)

    def test_remuneration_entries_only_via_payroll(self):
        self.submit(key="a", due=100)
        self.liquidate()
        for e in Entry.objects.filter(nature="wage"):
            self.assertTrue(e.transaction.key.startswith("remuneration:"))
        self.assertEqual(self.pay(self.company_payer, ledger.player_account(self.player.pk), 5, nature=WAGE).code,
                         "NATURE_REQUIRES_PAYROLL")


class PermutationIndependenceTests(PayrollTestCase):
    """O CONJUNTO reconhecido de um lote não depende da ordem de chegada dos pedidos (§24.12.4)."""

    def _scenario_requests(self, p2):
        self.limits.update(W=100, S=150, T=220)
        self.political[(self.player.pk, self.day)] = 80
        union = ledger.union_account()
        poor = self.company(90)
        self.fund(poor, 130)            # só cobre alguns pedidos: a falta de caixa entra na mesma sequência global
        return [
            dict(key="w1", player=self.player, nature=WAGE, due=100, earned_at=T0 + 10),
            dict(key="w2", player=self.player, nature=WAGE, due=100, earned_at=T0 + 20),
            dict(key="o1", player=self.player, nature=OWNER, due=100, earned_at=T0 + 5),
            dict(key="pol", player=self.player, nature=POL, due=80, payer=union, earned_at=T0 + 30),
            dict(key="x1", player=p2, nature=WAGE, due=120, payer=poor, earned_at=T0 + 1, policy=Policy.REFUSE),
            dict(key="x2", player=p2, nature=WAGE, due=120, payer=poor, earned_at=T0 + 2, policy=Policy.REFUSE),
            dict(key="x3", player=p2, nature=MIL, due=300, earned_at=T0 + 3, policy=Policy.PENDING, rate=D("0.1")),
            dict(key="d2", player=p2, nature=WAGE, due=100, earned_at=T0 + DAY + 1, payer=poor, policy=Policy.PENDING),
        ]

    def test_many_permutations_same_recognized_set(self):
        p2 = self.new_player("p2")
        self.fund(ledger.union_account(), 10 ** 6)
        specs = self._scenario_requests(p2)
        rng = random.Random(11)
        orders = [list(range(len(specs))), list(reversed(range(len(specs))))]
        for _ in range(18):
            o = list(range(len(specs)))
            rng.shuffle(o)
            orders.append(o)
        results = []
        for order in orders:
            sid = transaction.savepoint()
            for i in order:
                self.submit(**specs[i])
            res = remuneration.liquidate_remuneration(batch="b")
            self.assertTrue(res.ok, res)
            snapshot = {r.key: (r.status, r.recognized, r.discarded, r.paid, r.pending, r.tax, r.net, r.position)
                        for r in RemunerationRequest.objects.all()}
            counters = {(c.player_id, c.competence_day): (c.c_s, c.c_t, c.c_p, c.p_released)
                        for c in RemunerationCounter.objects.all()}
            balances = (self.pbal(), self.pbal(p2), ledger.balance_of(self.company(90).pk))
            results.append((snapshot, counters, balances))
            transaction.savepoint_rollback(sid)
        first = results[0]
        for other in results[1:]:
            self.assertEqual(first, other)
        snap = first[0]
        # sanidade do cenário: político primeiro, reserva protege, falta de caixa recusa na ordem estável
        self.assertEqual(snap["pol"][1], 80)
        self.assertEqual(snap["x1"][0], "recognized")
        self.assertEqual(snap["x2"][0], "refused")

    def test_sort_key_uses_only_request_data(self):
        a = self.submit(key="a", due=1, earned_at=T0 + 5)
        b = self.submit(key="b", due=1, earned_at=T0 + 1)
        ra, rb = self.req("a"), self.req("b")
        self.assertLess(remuneration.sort_key(rb), remuneration.sort_key(ra))

    def test_liquidating_subset_by_keys(self):
        self.submit(key="a", due=100)
        self.submit(key="b", due=100)
        res = remuneration.liquidate_remuneration(batch="b", keys=["a"])
        self.assertEqual(res.detail["count"], 1)
        self.assertEqual((self.req("a").status, self.req("b").status), ("recognized", "submitted"))
