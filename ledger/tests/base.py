import itertools
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from core.clock import ManualClock, use_clock
from core.timeline import game_ts
from ledger import remuneration, services as ledger
from ledger.audit import audit_ledger
from ledger.constants import GRANT_ROLE_KINDS, OPERATIONAL_KINDS, AccountKind, Nature
from ledger.models import LedgerScenario

T0 = game_ts(2026, 10, 5, 12)
DAY = 86400
D = Decimal
_scenario_seq = itertools.count(1)
# Papel SÓ dos testes: dá dinheiro a qualquer conta operacional (ex.: empresas, que o design 24 §24.11 não lista como papel de
# dotação). O mapa de produção (`GRANT_ROLE_KINDS`) continua fechado; o patch dura até depois da auditoria final do teste.
TEST_ROLE = "test_any"


def install_test_role(testcase):
    patcher = mock.patch.dict(GRANT_ROLE_KINDS, {TEST_ROLE: frozenset(OPERATIONAL_KINDS)})
    patcher.start()
    testcase.addCleanup(patcher.stop)


def fund_account(account, amount):
    """Dinheiro entra só por dotação de cenário (única fonte de emissão): cenário ativo, linha explícita, valor exato."""
    name = f"t{next(_scenario_seq)}"
    previously_active = list(LedgerScenario.objects.filter(active=True).values_list("pk", flat=True))
    ledger.create_scenario(name, {TEST_ROLE: amount})
    assert ledger.activate_scenario(name, [TEST_ROLE]).ok
    try:
        res = ledger.grant_scenario_allocation(name, account.pk, amount, role=TEST_ROLE)
    finally:       # o cenário ativo de antes (se havia) volta como estava
        LedgerScenario.objects.filter(name=name).update(active=False)
        LedgerScenario.objects.filter(pk__in=previously_active).update(active=True)
    assert res.ok, res
    return res


class LedgerHelpers:
    """Auxiliares comuns; a auditoria roda no fim de TODO teste (o ledger tem de estar íntegro ao final de qualquer cenário)."""

    audit_at_end = True

    def ledger_setup(self):
        install_test_role(self)             # registrado ANTES da auditoria final: seu cleanup roda depois dela
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
        return fund_account(account, amount)

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
