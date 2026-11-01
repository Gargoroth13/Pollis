from core.timeline import game_ts
from legislation import authority, catalog, laws, preview, process, proposals, suggestions, voting
from legislation.audit import audit_legislation
from legislation.constants import Status
from legislation.models import Proposal
from players.tests.base import T0, PlayerTestCase

DAY = 86400
# T0 = segunda-feira 2026-10-05 12:00 (fuso do jogo). Segundas: 10-05, 10-12, 10-19, 10-26.
MON = game_ts(2026, 10, 5)
FRI_BEFORE = game_ts(2026, 10, 9, 15)          # sexta 15:00
NEXT_MON = game_ts(2026, 10, 12)


def at(month, day, hour=0, minute=0):
    return game_ts(2026, month, day, hour, minute)


class LegislationBase(PlayerTestCase):
    """Presidente, 5 Deputados, 1 Governador, 1 jogador comum; leis de teste (as reais vêm da P1.12); provedor de cargos FALSO (a P1.11 registra o real)."""

    audit_at_end = True

    def setUp(self):
        super().setUp()
        self.addCleanup(catalog.clear_catalog)
        self.addCleanup(preview.clear_estimators)
        self.addCleanup(authority.clear_providers)
        self.president_id = None
        self.seats = []
        self.governors = frozenset()
        authority.register_provider("test", authority.OfficeProvider(lambda: self.president_id, lambda: list(self.seats), lambda: self.governors))
        self.president = self.new_player("pres")
        self.deps = [self.new_player(f"dep{i}") for i in range(5)]
        self.gov = self.new_player("gov")
        self.other = self.new_player("other")
        self.president_id = self.president.pk
        self.seats = [d.pk for d in self.deps]
        self.governors = frozenset({self.gov.pk})
        catalog.register_law(catalog.LawSpec("min_wage", "Salário mínimo", (catalog.ParamSpec("value", "int", 100, 10000, 1000),), group="salaries"))
        catalog.register_law(catalog.LawSpec("wage_ceiling", "Teto salarial", (catalog.ParamSpec("value", "int", 100, 100000, 20000),), group="salaries",
                                             validators=(self._ceiling_not_below_minimum,)))
        catalog.register_law(catalog.LawSpec("sales_tax", "Imposto sobre vendas", (catalog.ParamSpec("rate", "decimal", 0, 30, 5),)))
        self.addCleanup(self._audit)

    @staticmethod
    def _ceiling_not_below_minimum(values, ctx):
        minimum = ctx.value_of("min_wage", "value")
        ok = int(values["value"]) >= int(minimum)
        return [{"key": "ceiling_not_below_minimum_wage", "ok": ok, "reason": "ceiling_ok" if ok else "ceiling_below_minimum_wage", "minimum_wage": minimum}]

    def _audit(self):
        if self.audit_at_end:
            report = audit_legislation()
            self.assertTrue(report.ok, report.findings)

    # --- atalhos --------------------------------------------------------------------------------------------------------------------------
    def go(self, ts):
        """Leva o relógio a `ts` e processa o calendário legislativo."""
        self.clk.set(ts)
        return process.advance(ts)

    def propose(self, who=None, law="min_wage", value=1200, **extra):
        who = who or self.president
        params = {"rate": value} if law == "sales_tax" else {"value": value}
        return proposals.create_proposal(who.pk, {"law": law, "params": params, **extra})

    def pid(self, res):
        self.assertTrue(res.ok, res)
        return res.detail["proposal"]

    def get(self, pid):
        return Proposal.objects.get(pk=pid)

    def vote(self, pid, who, choice):
        return voting.cast_vote(who.pk, {"proposal": pid, "choice": choice})

    def vote_all(self, pid, choices):
        for dep, c in zip(self.deps, choices):
            if c is not None:
                res = self.vote(pid, dep, c)
                self.assertTrue(res.ok, res)

    def to_voting(self, value=1200, law="min_wage", author=None):
        """Proposta enviada na sexta 15:00; processada na segunda 00:00 (votação aberta)."""
        self.clk.set(FRI_BEFORE)
        pid = self.pid(self.propose(author, law, value))
        self.go(NEXT_MON)
        self.assertEqual(self.get(pid).status, Status.VOTING.value)
        return pid
