"""
Concorrência do processo legislativo: propostas simultâneas no mesmo escopo, voto repetido, sanção × sanção automática, sanção × veto.
A restrição única parcial por escopo e as travas da proposta (`SELECT ... FOR UPDATE`, PostgreSQL) são as defesas. Em SQLite o banco serializa as
escritas; os testes `CROSS_ROW` só valem como garantia em PostgreSQL. Como em todo teste de corrida, a ausência de uma trava só é detectada parcialmente
(depende de temporização): a segunda defesa é a restrição do banco e a auditoria.
"""
import unittest
from collections import Counter

from django.db import connection
from django.test import TransactionTestCase

from accounts.models import Usuario
from core.clock import ManualClock, use_clock
from geography.balance import get_scenario
from geography.generator import generate_world
from geography.tests.base import SMALL
from ledger.tests.test_scenario_concurrency import run_together
from legislation import authority, catalog, process, proposals, voting
from legislation.audit import audit_legislation
from legislation.constants import Status
from legislation.models import Proposal, VoteRecord
from legislation.tests.base import DAY, FRI_BEFORE, NEXT_MON, at
from players.services import create_player
from players.tests.base import T0

ON_PG = connection.vendor == "postgresql"
CROSS_ROW = unittest.skipUnless(ON_PG, "ordem entre linhas: só o SELECT ... FOR UPDATE (PostgreSQL) a garante; em SQLite não há trava de linha")
ROUNDS = 12


class LegislationConcurrencyBase(TransactionTestCase):
    def setUp(self):
        generate_world(get_scenario(**SMALL))
        self.clk = ManualClock(FRI_BEFORE)
        cm = use_clock(self.clk)
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.addCleanup(authority.clear_providers)
        self.addCleanup(catalog.clear_catalog)
        self.president = create_player(Usuario.objects.create_user("pres"))
        self.deps = [create_player(Usuario.objects.create_user(f"d{i}")) for i in range(5)]
        authority.register_provider("test", authority.OfficeProvider(lambda: self.president.pk, lambda: [d.pk for d in self.deps], lambda: frozenset()))
        catalog.register_law(catalog.LawSpec("min_wage", "Salário mínimo", (catalog.ParamSpec("value", "int", 100, 10000, 1000),), group="salaries"))
        catalog.register_law(catalog.LawSpec("wage_ceiling", "Teto", (catalog.ParamSpec("value", "int", 100, 100000, 20000),), group="salaries"))

    def at_clock(self, fn):
        """O relógio de teste é uma variável de contexto: não passa para as threads da corrida; cada thread o ativa."""
        def run():
            with use_clock(self.clk):
                return fn()
        return run

    def assertClean(self):
        report = audit_legislation()
        self.assertTrue(report.ok, report.findings)

    def reset(self):
        from legislation.models import Law, LawChange, LegislativeState
        for model in (LawChange, Law, Proposal, LegislativeState):
            model.objects.all().delete()


class ProposalRaceTests(LegislationConcurrencyBase):
    def test_two_proposals_in_the_same_scope_never_both_become_active(self):
        outcomes = Counter()
        for i in range(ROUNDS):
            Proposal.objects.all().delete()
            jobs = run_together(self.at_clock(lambda: proposals.create_proposal(self.president.pk, {"law": "min_wage", "params": {"value": 1100 + i}})),
                                self.at_clock(lambda: proposals.create_proposal(self.deps[0].pk, {"law": "wage_ceiling", "params": {"value": 30000 + i}})))
            codes = sorted(j.result.code for j in jobs)
            outcomes[tuple(codes)] += 1
            self.assertEqual(Proposal.objects.filter(status="discussion").count(), 1, codes)
            self.assertClean()
        self.assertEqual(set(outcomes), {("LAW_BLOCKED", "OK")}, outcomes)

    def test_the_same_deputy_voting_twice_at_once_leaves_the_last_registered_vote(self):
        pid = self._to_voting()
        jobs = run_together(self.at_clock(lambda: voting.cast_vote(self.deps[0].pk, {"proposal": pid, "choice": "yes"})),
                            self.at_clock(lambda: voting.cast_vote(self.deps[0].pk, {"proposal": pid, "choice": "no"})))
        self.assertTrue(all(j.result is not None and j.result.ok for j in jobs), [(j.result, j.error) for j in jobs])
        self.assertEqual(VoteRecord.objects.filter(round__proposal_id=pid).count(), 2)
        self.assertClean()

    def _to_voting(self):
        pid = proposals.create_proposal(self.president.pk, {"law": "min_wage", "params": {"value": 1200}}).detail["proposal"]
        self.clk.set(NEXT_MON)
        process.advance(NEXT_MON)
        self.assertEqual(Proposal.objects.get(pk=pid).status, Status.VOTING.value)
        return pid


class DecisionRaceTests(LegislationConcurrencyBase):
    def _to_sanction(self, shift):
        """Leva uma proposta à sanção; `shift` (múltiplo de 4 semanas) afasta cada rodada da anterior sem voltar o relógio."""
        self.clk.set(FRI_BEFORE + shift)
        pid = proposals.create_proposal(self.president.pk, {"law": "min_wage", "params": {"value": 1200}}).detail["proposal"]
        self.clk.set(NEXT_MON + shift)
        process.advance(NEXT_MON + shift)
        for d in self.deps:
            voting.cast_vote(d.pk, {"proposal": pid, "choice": "yes"})
        self.clk.set(at(10, 15) + shift)
        process.advance(at(10, 15) + shift)
        self.assertEqual(Proposal.objects.get(pk=pid).status, Status.SANCTION.value)
        return pid

    @CROSS_ROW
    def test_sanction_versus_veto_by_the_president_decides_exactly_once(self):
        for i in range(ROUNDS):
            self.reset()
            shift = i * 28 * DAY
            pid = self._to_sanction(shift)
            self.clk.set(at(10, 16, 9) + shift)
            jobs = run_together(self.at_clock(lambda: voting.sanction(self.president.pk, {"proposal": pid})),
                                self.at_clock(lambda: voting.veto(self.president.pk, {"proposal": pid})))
            codes = sorted(j.result.code for j in jobs)
            self.assertEqual(codes, ["NOT_AWAITING_SANCTION", "OK"])
            self.assertIn(Proposal.objects.get(pk=pid).status, (Status.AWAITING_FORCE.value, Status.VETOED.value))
            self.assertClean()

    @CROSS_ROW
    def test_manual_sanction_versus_the_engine_at_the_deadline_never_both_decide(self):
        outcomes = Counter()
        for i in range(ROUNDS):
            self.reset()
            shift = i * 28 * DAY
            pid = self._to_sanction(shift)
            deadline = Proposal.objects.get(pk=pid).deadline_at
            self.clk.set(deadline - 1)
            jobs = run_together(self.at_clock(lambda: voting.sanction(self.president.pk, {"proposal": pid})),
                                self.at_clock(lambda: process.advance(deadline)))
            p = Proposal.objects.get(pk=pid)
            self.assertEqual(p.status, Status.AWAITING_FORCE.value)
            self.assertIn(p.decided_by_id, (self.president.pk, None))
            self.assertEqual(p.events.filter(kind__in=["sanctioned", "auto_sanctioned"]).count(), 1)
            outcomes[p.decided_by_id is None] += 1
            self.assertClean()
            del jobs
