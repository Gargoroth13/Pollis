"""
Concorrência do Inventário. Em PostgreSQL a posse é travada com `SELECT ... FOR UPDATE` (jogador → posses em ordem de
player_id → contas do ledger em ordem de id: protocolo em `services.py`); em SQLite o banco serializa as escritas. Os testes
verificam a PROPRIEDADE (nunca posse negativa, um só vencedor pela última unidade, conservação de itens e de dinheiro, sem
deadlock, auditoria limpa), que vale nos dois.
"""
import itertools

from django.test import TransactionTestCase

from accounts.models import Usuario
from catalog.loader import sync_catalog
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from inventory import services
from inventory.audit import audit_inventory
from inventory.constants import Operation
from inventory.models import InventoryMovement, Shipment
from ledger import services as ledger
from ledger.audit import audit_ledger, ledger_metrics
from ledger.models import Entry
from ledger.tests.base import fund_account, install_test_role
from ledger.tests.test_scenario_concurrency import Job, run_together
from players.services import create_player

_seq = itertools.count(1)


class ConcurrencyBase(TransactionTestCase):
    def setUp(self):
        install_test_role(self)
        generate_world(get_scenario(**SMALL))
        sync_catalog()
        self.a, self.b, self.c = (create_player(Usuario.objects.create_user(f"c{n}")) for n in (1, 2, 3))
        for p in (self.a, self.b, self.c):
            fund_account(ledger.player_account(p.pk), 1_000_000)

    def give(self, player, key, quantity):
        res = services.credit(player.pk, key, quantity, operation=Operation.PURCHASE, origin="retail:t",
                              key=f"g{next(_seq)}", reference_kind="t", reference_id=1)
        self.assertTrue(res.ok, res)

    def qty(self, player, key):
        return services.quantity_of(player.pk, key)

    def assertClean(self):
        report, ledger_report = audit_inventory(), audit_ledger()
        self.assertTrue(report.ok, report.findings)
        self.assertTrue(ledger_report.ok, ledger_report.findings)

class InventoryConcurrencyTests(ConcurrencyBase):
    def test_two_sends_of_the_last_unit_have_exactly_one_winner(self):
        for round_ in range(6):
            key = ("hamburger", "pasta", "chocolate", "juice", "soda", "ice_cream")[round_]
            self.give(self.a, key, 1)
            first, second = run_together(lambda: services.send_item(self.a.pk, self.b.pk, key, 1),
                                         lambda: services.send_item(self.a.pk, self.c.pk, key, 1))
            outcomes = sorted((first.result.code, second.result.code))
            self.assertEqual(outcomes, ["INSUFFICIENT_QUANTITY", "OK"], outcomes)
            self.assertEqual((self.qty(self.a, key), self.qty(self.b, key) + self.qty(self.c, key)), (0, 1))
        self.assertEqual(Shipment.objects.count(), 6)
        self.assertEqual(Entry.objects.filter(nature="mail_fee").count(), 6)
        self.assertClean()

    def test_a_send_and_a_consumption_of_the_last_unit_have_exactly_one_winner(self):
        for round_ in range(4):
            key = ("bread", "pasta", "juice", "soda")[round_]
            self.give(self.a, key, 1)
            send, eat = run_together(lambda: services.send_item(self.a.pk, self.b.pk, key, 1),
                                     lambda: services.consume(self.a.pk, key))
            self.assertEqual(sorted((send.result.ok, eat.result.ok)), [False, True], (send.result, eat.result))
            self.assertEqual(self.qty(self.a, key), 0)
            self.assertEqual(self.qty(self.b, key), 1 if send.result.ok else 0)
        self.assertClean()

    def test_crossing_sends_between_two_players_never_deadlock_and_conserve_items_and_money(self):
        for round_ in range(5):
            self.give(self.a, "hamburger", 3)
            self.give(self.b, "pasta", 3)
        units = {k: self.qty(self.a, k) + self.qty(self.b, k) for k in ("hamburger", "pasta")}
        money = ledger_metrics()["in_circulation"]
        for _ in range(5):
            jobs = run_together(lambda: services.send_item(self.a.pk, self.b.pk, "hamburger", 1),
                                lambda: services.send_item(self.b.pk, self.a.pk, "pasta", 1),
                                lambda: services.send_item(self.a.pk, self.b.pk, "hamburger", 1),
                                lambda: services.send_item(self.b.pk, self.a.pk, "pasta", 1))
            self.assertTrue(all(j.result.ok for j in jobs), [j.result for j in jobs])
        self.assertEqual({k: self.qty(self.a, k) + self.qty(self.b, k) for k in units}, units)
        self.assertEqual(ledger_metrics()["in_circulation"], money)
        self.assertEqual(Shipment.objects.count(), 20)
        self.assertClean()

    def test_the_same_idempotency_key_from_many_threads_applies_once(self):
        def call():
            return services.credit(self.a.pk, "wheat", 5, operation=Operation.PURCHASE, origin="retail:t", key="dup",
                                   reference_kind="t", reference_id=1)
        jobs = run_together(call, call, call, call)
        self.assertTrue(all(j.result.ok for j in jobs), [j.result for j in jobs])
        self.assertEqual((self.qty(self.a, "wheat"), InventoryMovement.objects.filter(key="dup").count()), (5, 1))
        self.assertClean()

    def test_concurrent_sales_never_take_the_holding_below_zero(self):
        self.give(self.a, "wheat", 3)
        calls = [lambda n=n: services.debit(self.a.pk, "wheat", 2, operation=Operation.SALE, destination="market:1",
                                            key=f"sale{n}", reference_kind="l", reference_id=n) for n in range(4)]
        jobs = run_together(*calls)
        wins = [j for j in jobs if j.result.ok]
        self.assertEqual((len(wins), self.qty(self.a, "wheat")), (1, 1))
        self.assertTrue(all(j.result.code == "INSUFFICIENT_QUANTITY" for j in jobs if not j.result.ok))
        self.assertClean()


class AutoConsumptionConcurrencyTests(ConcurrencyBase):
    """Auto-consumo (04 §16) sob concorrência: o hook roda sob o bloqueio do jogador e segue o mesmo protocolo."""

    def hungry(self, player, nutrition=5):
        from players.models import Player
        Player.objects.filter(pk=player.pk).update(nutrition=nutrition)

    def automatic(self):
        return InventoryMovement.objects.filter(reference_kind="auto_consumption")

    def test_simultaneous_accesses_of_a_hungry_player_consume_exactly_once(self):
        from inventory import auto
        from players import services as player_services
        for round_ in range(5):
            self.give(self.a, "chocolate", 2)
            self.assertTrue(auto.configure(self.a.pk, True, None).ok)
            self.hungry(self.a, 5)
            before = self.automatic().count()
            run_together(*[lambda: player_services.sync_player(self.a.pk) for _ in range(4)])
            self.assertEqual(self.automatic().count(), before + 1)                 # as outras já o encontram alimentado
        self.assertClean()

    def test_an_access_and_a_send_of_the_last_unit_have_exactly_one_winner_and_stay_consistent(self):
        from inventory import auto
        from players import services as player_services
        self.assertTrue(auto.configure(self.a.pk, True, "juice").ok)
        for round_ in range(6):
            self.give(self.a, "juice", 1)
            self.hungry(self.a, 5)
            ate_before, received_before = self.automatic().filter(player=self.a).count(), self.qty(self.b, "juice")
            _access, send = run_together(lambda: player_services.sync_player(self.a.pk),
                                         lambda: services.send_item(self.a.pk, self.b.pk, "juice", 1))
            ate = self.automatic().filter(player=self.a).count() - ate_before
            received = self.qty(self.b, "juice") - received_before
            self.assertEqual(self.qty(self.a, "juice"), 0)
            self.assertEqual(ate + received, 1, (ate, received))                    # a última unidade vai para UM destino só
            self.assertEqual(send.result.ok, received == 1, send.result)
            self.assertTrue(send.result.ok or send.result.code == "INSUFFICIENT_QUANTITY", send.result)
        self.assertClean()

    def test_automatic_consumption_crossed_with_sends_in_both_directions_never_deadlocks(self):
        from inventory import auto
        from players import services as player_services
        self.assertTrue(auto.configure(self.a.pk, True, None).ok)
        self.assertTrue(auto.configure(self.b.pk, True, None).ok)
        for round_ in range(4):
            self.give(self.a, "chocolate", 3)
            self.give(self.b, "chocolate", 3)
            self.hungry(self.a, 5)
            self.hungry(self.b, 5)
            jobs = run_together(lambda: services.send_item(self.a.pk, self.b.pk, "chocolate", 1),
                                lambda: services.send_item(self.b.pk, self.a.pk, "chocolate", 1),
                                lambda: player_services.sync_player(self.a.pk),
                                lambda: player_services.sync_player(self.b.pk))
            self.assertTrue(all(j.result is not None for j in jobs))
        total = sum(self.qty(p, "chocolate") for p in (self.a, self.b)) + sum(-m.delta for m in
                                                                              InventoryMovement.objects.filter(operation="consumption"))
        self.assertEqual(total, 24)                                                 # 4 rodadas × 2 jogadores × 3 unidades
        self.assertClean()
