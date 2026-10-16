import itertools
from decimal import Decimal

from django.test import TestCase

from core.clock import ManualClock, use_clock
from core.timeline import game_ts
from ledger import remuneration, services as ledger
from ledger.audit import audit_ledger
from ledger.constants import AccountKind, Nature

T0 = game_ts(2026, 10, 5, 12)
DAY = 86400
D = Decimal
_scenario_seq = itertools.count(1)


class LedgerHelpers:
    """Auxiliares comuns; a auditoria roda no fim de TODO teste (o ledger tem de estar íntegro ao final de qualquer cenário)."""

    audit_at_end = True

    def ledger_setup(self):
        self.addCleanup(ledger.clear_tax_resolvers)
        self.addCleanup(remuneration.clear_providers)
        self._n = 0
        if self.audit_at_end:
            self.addCleanup(self._audit)

    def _audit(self):
        report = audit_ledger()
        self.assertTrue(report.ok, report.findings)

    # --- helpers ---
    def company(self, n):
        return ledger.get_or_create_account(AccountKind.COMPANY, n)

    def fund(self, account, amount):
        """Dinheiro entra só por dotação de cenário (única fonte de emissão)."""
        name = f"t{next(_scenario_seq)}"
        ledger.create_scenario(name, {"x": 0})
        res = ledger.grant_scenario_allocation(name, account.pk, amount, role="x")
        assert res.ok, res
        return res

    def pay(self, a, b, amount, nature=Nature.SALE, key=None, **kw):
        self._n += 1
        return ledger.transfer(a.pk, b.pk, amount, nature, key=key or f"k{self._n}-{id(a)}-{id(b)}",
                               reference_kind="test", reference_id=str(self._n), **kw)

    def bal(self, account):
        return ledger.balance_of(account.pk)

    def total_supply(self):
        from ledger.audit import ledger_metrics
        m = ledger_metrics()
        return m["emitted_total"], m["in_circulation"], m["retained"], m["sink_destroyed"]


class LedgerTestCase(LedgerHelpers, TestCase):
    """Relógio manual; contas de EMPRESA sem depender de outros sistemas."""

    def setUp(self):
        self.clk = ManualClock(T0)
        cm = use_clock(self.clk)
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.ledger_setup()
