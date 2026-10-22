"""
Concorrência da Transparência de Mercado: a mesma venda registrada por várias threads vira UMA linha (idempotência pela chave do
pagamento) e vários fechamentos simultâneos do mesmo dia gravam o dia UMA vez. Vale em PostgreSQL e em SQLite (o banco serializa).
"""
from django.test import TransactionTestCase

from accounts.models import Usuario
from catalog.loader import sync_catalog
from companies import services
from companies.models import Company
from core.models import WorldClock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger import services as ledger
from ledger.audit import audit_ledger
from ledger.constants import Nature
from ledger.tests.base import fund_account, install_test_role
from ledger.tests.test_scenario_concurrency import run_together
from market import recording, rollup
from market.audit import audit_market
from market.models import DailyProductStat, MarketTransaction, RollupMark
from players.services import create_player

REAL = 100


class MarketConcurrencyTests(TransactionTestCase):
    def setUp(self):
        install_test_role(self)
        generate_world(get_scenario(**SMALL))
        sync_catalog()
        WorldClock.load()
        self.buyer, self.seller = (create_player(Usuario.objects.create_user(f"m{n}")) for n in (1, 2))
        for p in (self.buyer, self.seller):
            fund_account(ledger.player_account(p.pk), 100_000 * REAL)
        self.company = services.found_company(self.seller.pk, "industrial", "Moinho", 0).detail["company"]

    def pay(self, key, total=10_000):
        res = ledger.transfer(ledger.player_account(self.buyer.pk).pk, ledger.player_account(self.seller.pk).pk, total, Nature.SALE,
                              key=key, reference_kind="test", reference_id=key)
        self.assertTrue(res.ok, res)

    def call(self, key, **over):
        args = dict(product_key="flour", quantity=10, unit_price_cents=1_000, buyer_kind="player", buyer_id=self.buyer.pk,
                    seller_kind="player", seller_id=self.seller.pk, channel="player_market", ledger_key=key)
        args.update(over)
        return recording.record_sale(**args)

    def assertClean(self):
        for report in (audit_market(), audit_ledger()):
            self.assertTrue(report.ok, report.findings)

    def test_the_same_payment_recorded_by_many_threads_becomes_one_transaction(self):
        self.pay("race:1")
        jobs = run_together(*[lambda: self.call("race:1") for _ in range(6)])
        self.assertTrue(all(j.result.ok for j in jobs), [j.result for j in jobs])
        self.assertEqual(MarketTransaction.objects.count(), 1)
        self.assertEqual(sum(1 for j in jobs if not j.result.detail.get("already_applied")), 1)
        self.assertClean()

    def test_a_conflicting_content_for_the_same_payment_loses_the_race_without_duplicating(self):
        self.pay("race:2")
        jobs = run_together(*[lambda q=q: self.call("race:2", quantity=q, unit_price_cents=10_000 // q) for q in (10, 5, 2, 1)] +
                            [lambda: self.call("race:2")])
        wins = [j for j in jobs if j.result.ok and not j.result.detail.get("already_applied")]
        self.assertEqual(len(wins), 1)
        self.assertTrue(all(j.result.ok or j.result.code in {"IDEMPOTENCY_CONFLICT", "PAYMENT_NOT_FOUND"} for j in jobs))
        self.assertEqual(MarketTransaction.objects.count(), 1)
        self.assertClean()

    def test_distinct_payments_recorded_together_all_enter_exactly_once(self):
        for n in range(5):
            self.pay(f"many:{n}")
        jobs = run_together(*[lambda n=n: self.call(f"many:{n}") for n in range(5)])
        self.assertTrue(all(j.result.ok for j in jobs), [j.result for j in jobs])
        self.assertEqual(MarketTransaction.objects.count(), 5)
        self.assertClean()

    def test_simultaneous_day_closing_stores_each_day_once_with_the_same_numbers(self):
        self.pay("day:1")
        self.assertTrue(self.call("day:1").ok)
        today = rollup.competence_day_of(MarketTransaction.objects.get().at)
        jobs = run_together(*[lambda: rollup.close_day(today) for _ in range(5)])
        self.assertEqual(sorted(j.result for j in jobs), [False] * 4 + [True])
        self.assertEqual(RollupMark.objects.filter(day=today).count(), 1)
        self.assertEqual(DailyProductStat.objects.filter(day=today).count(), 1)
        row = DailyProductStat.objects.get(day=today)
        self.assertEqual((row.transactions, row.volume, row.value_cents), (1, 10, 10_000))

    def test_ensure_closed_racing_with_itself_fills_every_day_once(self):
        self.pay("day:2")
        self.assertTrue(self.call("day:2").ok)
        first = rollup.competence_day_of(MarketTransaction.objects.get().at)
        jobs = run_together(*[lambda: rollup.ensure_closed(first + 4) for _ in range(4)])
        closed = [d for j in jobs for d in j.result]
        self.assertEqual(len(closed), len(set(closed)))                                # nenhum dia é "fechado" por duas threads
        self.assertEqual(sorted(RollupMark.objects.values_list("day", flat=True)), list(range(first, first + 5)))   # e nenhum ficou sem fechar
        self.assertEqual(RollupMark.objects.count(), 5)
        self.assertEqual(DailyProductStat.objects.count(), 1)
