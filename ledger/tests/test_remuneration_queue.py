"""
Fila de pagamento do pagador com obrigações (design/24 §24.9 "competência mais antiga primeiro"; A-04, GD 2026-11-27): uma
remuneração `PENDING` NOVA não passa na frente de obrigação mais antiga do mesmo pagador. Primeiro quita-se o que o caixa permite,
na ordem; só o que sobrar paga o pedido novo; se ainda restar dívida mais antiga, o pedido novo vira obrigação atrás das demais.
"""
from decimal import Decimal

from ledger import obligations
from ledger.constants import Nature, ObligationStatus, Policy
from ledger.models import Obligation, RemunerationRequest

from .test_remuneration import PayrollTestCase, T0, D

WAGE = Nature.WAGE


class QueueTests(PayrollTestCase):
    def setUp(self):
        super().setUp()
        self.limits.update({"W": 100_000, "S": 100_000})
        self.debtor = self.company(7)                                    # pagador sem caixa até o teste financiá-lo
        self.older = self.player
        self.newer = self.make_player("queue_newer")

    def make_player(self, name):
        from accounts.models import Usuario
        from players.services import create_player
        return create_player(Usuario.objects.create_user(name))

    def pay_new(self, player, due, key):
        return remuneration.pay_remuneration_now(
            key=key, player_id=player.pk, payer_id=self.debtor.pk, nature=WAGE, due=due, earned_at=T0, policy=Policy.PENDING,
            reference_kind="work", reference_id=key, tax_rate=D(0))

    def test_a_new_request_pays_older_obligations_first_and_only_the_leftover_goes_to_the_new_one(self):
        first = self.pay_new(self.older, 100, "q-old")
        self.assertEqual((first.detail["paid"], first.detail["pending"]), (0, 100))       # sem caixa: obrigação
        self.fund(self.debtor, 150)
        second = self.pay_new(self.newer, 100, "q-new")
        old = Obligation.objects.get(reference_id="q-old")
        self.assertEqual((old.status, old.amount_paid), (ObligationStatus.PAID.value, 100))
        # sobraram 50 depois da fila, mas o pedido novo (100) não cabe: o pagamento é tudo ou nada na hora, o resto fica pendente
        self.assertEqual((second.detail["paid"], second.detail["pending"]), (0, 100))
        self.assertEqual(self.pbal(self.older), 100)

    def test_with_cash_for_only_the_older_one_the_new_one_becomes_an_obligation_behind_it(self):
        self.pay_new(self.older, 100, "q-old")
        self.fund(self.debtor, 100)
        second = self.pay_new(self.newer, 100, "q-new")
        old = Obligation.objects.get(reference_id="q-old")
        new = Obligation.objects.get(reference_id="q-new")
        self.assertEqual(old.status, ObligationStatus.PAID.value)
        self.assertEqual((new.status, new.amount_paid, second.detail["paid"], second.detail["pending"]),
                         (ObligationStatus.OPEN.value, 0, 0, 100))
        self.assertEqual(self.pbal(self.older), 100)
        self.assertEqual(self.pbal(self.newer), 0)
        self.assertEqual(second.detail["explained"]["queue"], {"older_settled": 100, "older_still_open": False})

    def test_with_cash_for_everyone_both_are_paid_and_nothing_stays_open(self):
        self.pay_new(self.older, 100, "q-old")
        self.fund(self.debtor, 500)
        second = self.pay_new(self.newer, 100, "q-new")
        self.assertEqual((second.detail["paid"], second.detail["pending"]), (100, 0))
        self.assertEqual(Obligation.objects.filter(status=ObligationStatus.OPEN.value).count(), 0)
        self.assertEqual((self.pbal(self.older), self.pbal(self.newer)), (100, 100))

    def test_partial_payment_keeps_the_older_in_front_and_total_money_is_conserved(self):
        self.pay_new(self.older, 100, "q-old")
        self.fund(self.debtor, 40)
        total_before = self.total_supply()
        second = self.pay_new(self.newer, 100, "q-new")
        old = Obligation.objects.get(reference_id="q-old")
        self.assertEqual((old.status, old.amount_paid), (ObligationStatus.OPEN.value, 40))   # o caixa foi para a mais antiga
        self.assertEqual((second.detail["paid"], second.detail["pending"]), (0, 100))
        self.assertEqual(self.total_supply(), total_before)
        self.assertEqual(self.pbal(self.older), 40)

    def test_a_payer_without_older_debt_pays_on_the_spot_as_before_and_other_policies_are_untouched(self):
        self.fund(self.debtor, 500)
        res = self.pay_new(self.older, 100, "q-free")
        self.assertEqual((res.detail["paid"], res.detail["pending"]), (100, 0))
        self.assertNotIn("queue", res.detail["explained"])

    def test_a_request_of_an_earlier_competence_day_is_not_blocked_by_a_newer_debt(self):
        later = T0 + 5 * 86_400
        remuneration.pay_remuneration_now(
            key="q-late", player_id=self.older.pk, payer_id=self.debtor.pk, nature=WAGE, due=100, earned_at=later,
            policy=Policy.PENDING, reference_kind="work", reference_id="q-late", tax_rate=D(0))
        self.fund(self.debtor, 500)
        res = self.pay_new(self.newer, 100, "q-early")                                  # competência ANTERIOR à da dívida aberta
        self.assertEqual((res.detail["paid"], res.detail["pending"]), (100, 0))

    def test_repeating_the_same_request_does_not_settle_twice(self):
        self.pay_new(self.older, 100, "q-old")
        self.fund(self.debtor, 300)
        self.pay_new(self.newer, 100, "q-new")
        total = self.total_supply()
        again = self.pay_new(self.newer, 100, "q-new")
        self.assertTrue(again.detail["already_posted"])
        self.assertEqual(self.total_supply(), total)
        self.assertEqual(self.pbal(self.older), 100)


from ledger import remuneration  # noqa: E402  (usado nos testes acima)
