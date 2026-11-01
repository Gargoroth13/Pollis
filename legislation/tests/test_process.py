from legislation import authority, laws, process, proposals, voting
from legislation.constants import EventKind, RoundStatus, Status
from legislation.models import Interregnum, Law, LawChange, Proposal, VoteRecord, VoteRound
from legislation.tests.base import DAY, FRI_BEFORE, NEXT_MON, LegislationBase, at

VOTE_END = at(10, 15)           # quinta 00:00
SANCTION_END = at(10, 18)       # domingo 00:00
FORCE = at(10, 19)              # segunda seguinte


class WindowTests(LegislationBase):
    def test_friday_proposal_enters_the_vote_on_monday_with_a_frozen_composition(self):
        self.clk.set(FRI_BEFORE)
        pid = self.pid(self.propose())
        self.go(NEXT_MON - 1)
        self.assertEqual(self.get(pid).status, Status.DISCUSSION.value)         # a votação só começa na segunda
        self.go(NEXT_MON)
        p = self.get(pid)
        rnd = p.rounds.get()
        self.assertEqual((p.status, rnd.started_at, rnd.ends_at, rnd.seats_count), (Status.VOTING.value, NEXT_MON, VOTE_END, 5))
        self.assertEqual(rnd.seats, [d.pk for d in self.deps])

    def test_saturday_proposal_waits_for_the_next_window(self):
        self.clk.set(at(10, 10, 0, 1))
        pid = self.pid(self.propose())
        self.go(NEXT_MON)
        self.assertEqual(self.get(pid).status, Status.DISCUSSION.value)
        self.go(at(10, 19))
        self.assertEqual(self.get(pid).status, Status.VOTING.value)
        self.assertEqual(self.get(pid).rounds.get().started_at, at(10, 19))

    def test_late_engine_run_uses_logical_times(self):
        self.clk.set(FRI_BEFORE)
        pid = self.pid(self.propose())
        self.go(at(10, 14, 9))                                          # o motor só roda na quarta 09:00
        rnd = self.get(pid).rounds.get()
        self.assertEqual((rnd.started_at, rnd.ends_at), (NEXT_MON, VOTE_END))
        self.vote_all(pid, ["yes", "yes", "yes", None, None])           # ainda dentro do prazo
        self.go(at(10, 16, 9))
        p = self.get(pid)
        self.assertEqual((p.status, p.deadline_at), (Status.SANCTION.value, SANCTION_END))      # prazo da sanção vem do fim LÓGICO da votação

    def test_advance_is_idempotent(self):
        self.to_voting()
        before = (Proposal.objects.values_list("status", "deadline_at", "round_no"), VoteRound.objects.count())
        self.assertEqual(process.advance(NEXT_MON), 0)
        self.assertEqual(process.advance(NEXT_MON), 0)
        self.assertEqual(before[1], VoteRound.objects.count())

    def test_the_weekly_tick_handler_drives_the_engine(self):
        from core import ticks
        self.clk.set(FRI_BEFORE)
        pid = self.pid(self.propose())
        self.clk.set(NEXT_MON + 600)
        res = ticks.process_ticks(ticks.WORLD, FRI_BEFORE, NEXT_MON + 600)
        self.assertGreater(res.ticks_processed, 0)
        self.assertEqual(self.get(pid).status, Status.VOTING.value)


class ChamberVoteTests(LegislationBase):
    def setUp(self):
        super().setUp()
        self.pid_ = self.to_voting()

    def close(self):
        self.go(VOTE_END)
        return self.get(self.pid_)

    def test_absolute_majority_of_all_seats_approves(self):
        self.vote_all(self.pid_, ["yes", "yes", "yes", "no", None])
        p = self.close()
        self.assertEqual(p.status, Status.SANCTION.value)
        tally = p.rounds.get().tally
        self.assertEqual((tally["yes"], tally["no"], tally["absent"], tally["required_yes"], tally["approved"]), (3, 1, 1, 3, True))

    def test_two_yes_of_five_is_rejected_even_if_nobody_else_voted(self):
        self.vote_all(self.pid_, ["yes", "yes", None, None, None])
        self.assertEqual(self.close().status, Status.REJECTED.value)

    def test_abstentions_and_absences_never_count_as_yes(self):
        self.vote_all(self.pid_, ["yes", "yes", "no", "abstain", "abstain"])
        p = self.close()
        self.assertEqual(p.status, Status.REJECTED.value)
        self.assertEqual(p.rounds.get().tally["abstain"], 2)

    def test_majority_is_over_all_seats_not_over_those_who_voted(self):
        # 4 cadeiras: 2 sim de 4 NÃO é maioria absoluta (precisa de 3), mesmo sendo toda a maioria de quem votou
        self.seats = self.seats[:4]
        pid = self.to_voting_again()
        self.vote_all(pid, ["yes", "yes", None, None, None])
        self.go(self.get(pid).deadline_at)
        self.assertEqual(self.get(pid).status, Status.REJECTED.value)

    def to_voting_again(self):
        self.go(at(10, 15))
        self.go(at(10, 18))
        self.go(at(10, 19))
        pid = self.pid(self.propose(law="sales_tax", value=9))
        self.go(at(10, 26))
        return pid

    def test_a_deputy_can_change_the_vote_and_only_the_last_counts(self):
        self.vote(self.pid_, self.deps[0], "no")
        self.vote(self.pid_, self.deps[0], "yes")
        self.vote_all(self.pid_, [None, "yes", "yes", None, None])
        p = self.close()
        self.assertEqual(p.status, Status.SANCTION.value)
        self.assertEqual(VoteRecord.objects.filter(round__proposal=p, deputy_id=self.deps[0].pk).count(), 2)       # histórico preserva a mudança
        self.assertEqual(p.rounds.get().tally["yes"], 3)

    def test_votes_are_nominal_and_public(self):
        from legislation import views
        self.vote_all(self.pid_, ["yes", "no", "abstain", None, None])
        view = views.proposal_view(self.pid_)["rounds"][0]
        self.assertEqual(view["votes"], {str(self.deps[0].pk): "yes", str(self.deps[1].pk): "no", str(self.deps[2].pk): "abstain"})
        self.assertEqual(len(view["vote_history"]), 3)

    def test_only_deputies_of_the_frozen_composition_vote(self):
        self.assertEqual(self.vote(self.pid_, self.other, "yes").code, "NOT_A_VOTER")
        self.assertEqual(self.vote(self.pid_, self.president, "yes").code, "NOT_A_VOTER")
        newcomer = self.new_player("newcomer")
        self.seats.append(newcomer.pk)                                   # eleito depois do congelamento: não vota nesta votação
        self.assertEqual(self.vote(self.pid_, newcomer, "yes").code, "NOT_A_VOTER")
        p = self.close()
        self.assertEqual(p.rounds.get().seats_count, 5)                  # o quórum não muda retroativamente

    def test_a_deputy_who_lost_the_seat_cannot_vote_but_a_vote_already_cast_counts(self):
        self.vote(self.pid_, self.deps[0], "yes")
        self.seats.remove(self.deps[0].pk)
        self.assertEqual(self.vote(self.pid_, self.deps[0], "no").code, "NOT_A_DEPUTY")
        self.assertEqual(self.vote(self.pid_, self.deps[1], "yes").ok, True)
        self.assertEqual(self.get(self.pid_).rounds.get().tally, None)
        self.vote(self.pid_, self.deps[2], "yes")
        self.assertEqual(self.close().status, Status.SANCTION.value)

    def test_voting_is_closed_at_the_deadline_even_before_the_engine_runs(self):
        self.clk.set(VOTE_END - 1)
        self.assertTrue(self.vote(self.pid_, self.deps[0], "yes").ok)
        self.clk.set(VOTE_END)
        self.assertEqual(self.vote(self.pid_, self.deps[1], "yes").code, "VOTE_CLOSED")
        self.assertEqual(self.get(self.pid_).status, Status.VOTING.value)

    def test_vote_refusals(self):
        self.assertEqual(voting.cast_vote(self.deps[0].pk, {"proposal": self.pid_, "choice": "maybe"}).code, "INVALID_CHOICE")
        self.assertEqual(voting.cast_vote(self.deps[0].pk, {"proposal": 10 ** 9, "choice": "yes"}).code, "PROPOSAL_NOT_FOUND")
        self.assertEqual(voting.cast_vote(self.deps[0].pk, {"proposal": self.pid_}).code, "INVALID_PARAMS")
        self.assertEqual(voting.cast_vote(10 ** 9, {"proposal": self.pid_, "choice": "yes"}).code, "PLAYER_NOT_FOUND")
        other = self.pid(self.propose(law="sales_tax", value=8))
        self.assertEqual(self.vote(other, self.deps[0], "yes").code, "NOT_VOTING")

    def test_rejection_records_everything_and_does_not_change_the_law(self):
        self.vote_all(self.pid_, ["no"] * 5)
        p = self.close()
        self.assertEqual((p.status, p.closed_at, p.deadline_at), (Status.REJECTED.value, VOTE_END, None))
        self.assertEqual(laws.value("min_wage", "value"), 1000)
        self.go(FORCE + 7 * DAY)
        self.assertEqual(laws.value("min_wage", "value"), 1000)
        self.assertFalse(Law.objects.exists())


class SanctionVetoTests(LegislationBase):
    def setUp(self):
        super().setUp()
        self.pid_ = self.to_voting()
        self.vote_all(self.pid_, ["yes"] * 5)
        self.go(VOTE_END)
        self.assertEqual(self.get(self.pid_).status, Status.SANCTION.value)

    def sanction(self, who=None):
        return voting.sanction((who or self.president).pk, {"proposal": self.pid_})

    def veto(self, who=None, **extra):
        return voting.veto((who or self.president).pk, {"proposal": self.pid_, **extra})

    def test_president_sanctions_within_the_deadline_and_the_law_starts_on_the_next_monday(self):
        self.clk.set(at(10, 16, 10))
        res = self.sanction()
        self.assertTrue(res.ok, res)
        p = self.get(self.pid_)
        self.assertEqual((p.status, p.force_at, p.decided_by_id), (Status.AWAITING_FORCE.value, FORCE, self.president.pk))
        self.go(FORCE - 1)
        self.assertEqual(laws.value("min_wage", "value"), 1000)           # aprovada ≠ em vigor (07 §07.16)
        self.go(FORCE)
        self.assertEqual(laws.value("min_wage", "value"), 1200)
        self.assertEqual(self.get(self.pid_).status, Status.ENACTED.value)

    def test_inaction_is_an_automatic_sanction(self):
        self.go(SANCTION_END - 1)
        self.assertEqual(self.get(self.pid_).status, Status.SANCTION.value)
        self.go(SANCTION_END)
        p = self.get(self.pid_)
        self.assertEqual((p.status, p.decided_by_id, p.force_at), (Status.AWAITING_FORCE.value, None, FORCE))
        self.assertIn(EventKind.AUTO_SANCTIONED.value, [e.kind for e in p.events.all()])
        self.go(FORCE)
        self.assertEqual(laws.value("min_wage", "value"), 1200)

    def test_a_decision_exactly_on_a_weekly_tick_enters_force_on_the_following_one(self):
        # "no próximo weekly tick": estritamente depois (o prazo foi esticado por uma votação reaberta, por isso cobre uma segunda-feira)
        from legislation.models import Proposal
        Proposal.objects.filter(pk=self.pid_).update(deadline_at=at(10, 28))
        self.clk.set(at(10, 26))
        self.assertTrue(self.sanction().ok)
        self.assertEqual(self.get(self.pid_).force_at, at(11, 2))

    def test_decision_after_the_deadline_is_refused(self):
        self.clk.set(SANCTION_END)
        self.assertEqual(self.sanction().code, "SANCTION_DEADLINE_PASSED")
        self.assertEqual(self.veto().code, "SANCTION_DEADLINE_PASSED")

    def test_only_the_president_decides(self):
        for who in (self.other, self.deps[0], self.gov):
            self.assertEqual(self.sanction(who).code, "NOT_PRESIDENT")
            self.assertEqual(self.veto(who).code, "NOT_PRESIDENT")

    def test_veto_records_responsible_time_and_justification(self):
        self.clk.set(at(10, 16, 10))
        res = self.veto(justification="inflação")
        self.assertTrue(res.ok, res)
        p = self.get(self.pid_)
        self.assertEqual((p.status, p.decided_by_id, p.decided_at, p.veto_justification, p.deadline_at),
                         (Status.VETOED.value, self.president.pk, at(10, 16, 10), "inflação", FORCE))
        self.assertEqual(self.veto().code, "NOT_AWAITING_SANCTION")

    def test_veto_justification_limit(self):
        self.assertEqual(self.veto(justification="x" * 1001).code, "INVALID_JUSTIFICATION")
        self.assertEqual(self.veto(justification=3).code, "INVALID_JUSTIFICATION")

    def override_window(self):
        self.clk.set(at(10, 16, 10))
        self.veto()
        self.go(FORCE)
        p = self.get(self.pid_)
        self.assertEqual(p.status, Status.OVERRIDE_VOTING.value)
        return p.rounds.get(kind="override")

    def test_override_needs_two_thirds_of_all_seats_and_never_returns_to_the_president(self):
        rnd = self.override_window()
        self.assertEqual((rnd.started_at, rnd.ends_at, rnd.seats_count), (FORCE, at(10, 22), 5))
        self.vote_all(self.pid_, ["yes", "yes", "yes", "yes", "no"])       # 4 de 5 ≥ 2/3 (4)
        self.go(at(10, 22))
        p = self.get(self.pid_)
        self.assertEqual((p.status, p.force_at), (Status.AWAITING_FORCE.value, at(10, 26)))
        self.assertEqual(p.rounds.get(kind="override").tally["required_yes"], 4)
        self.go(at(10, 26))
        self.assertEqual(laws.value("min_wage", "value"), 1200)
        self.assertEqual(self.get(self.pid_).status, Status.ENACTED.value)

    def test_three_of_five_is_not_enough_to_override(self):
        self.override_window()
        self.vote_all(self.pid_, ["yes", "yes", "yes", "no", None])
        self.go(at(10, 22))
        p = self.get(self.pid_)
        self.assertEqual((p.status, p.closed_at), (Status.VETO_SUSTAINED.value, at(10, 22)))
        self.go(at(10, 26))
        self.assertEqual(laws.value("min_wage", "value"), 1000)

    def test_two_thirds_threshold_edge_cases(self):
        for seats, need in ((1, 1), (2, 2), (3, 2), (4, 3), (5, 4), (6, 4), (7, 5), (9, 6)):
            self.assertEqual(voting.required_votes(voting.RoundKind.OVERRIDE, seats), need, seats)
        for seats, need in ((1, 1), (2, 2), (3, 2), (4, 3), (5, 3), (6, 4)):
            self.assertEqual(voting.required_votes(voting.RoundKind.MAIN, seats), need, seats)

    def test_the_override_uses_the_composition_frozen_when_it_opens(self):
        self.clk.set(at(10, 16, 10))
        self.veto()
        extra = self.new_player("extra")
        self.seats.append(extra.pk)                                      # Câmara cresceu antes da janela de derrubada
        self.go(FORCE)
        self.assertEqual(self.get(self.pid_).rounds.get(kind="override").seats_count, 6)


class EnactmentTests(LegislationBase):
    def enact(self, law="min_wage", value=1200, start=None):
        """Leva uma proposta até a sanção automática e o vigor; devolve o instante do vigor."""
        pid = self.pid(self.propose(law=law, value=value))
        p = self.get(pid)
        self.go(p.deadline_at)
        self.vote_all(pid, ["yes"] * 5)
        self.go(self.get(pid).deadline_at)
        self.go(self.get(pid).deadline_at)
        self.go(self.get(pid).deadline_at)
        self.assertEqual(self.get(pid).status, Status.ENACTED.value)
        return pid

    def test_operations_before_the_force_date_keep_the_old_rule(self):
        pid = self.to_voting()
        self.vote_all(pid, ["yes"] * 5)
        self.go(SANCTION_END)
        # entre a sanção automática e o vigor: a regra antiga ainda vale; a lei é consultada pelo valor vigente
        self.assertEqual(laws.value("min_wage", "value"), 1000)
        self.go(FORCE)
        self.assertEqual(laws.value("min_wage", "value"), 1200)
        change = LawChange.objects.get()
        self.assertEqual((change.old_params, change.new_params, change.at), ({"value": 1000}, {"value": 1200}, FORCE))

    def test_changing_a_law_needs_a_new_proposal_and_the_old_value_stays_meanwhile(self):
        first = self.to_voting()
        self.vote_all(first, ["yes"] * 5)
        self.go(FORCE)
        self.assertEqual(laws.value("min_wage", "value"), 1200)
        pid = self.pid(self.propose(value=1500))
        self.assertEqual(self.get(pid).status, Status.DISCUSSION.value)
        self.assertEqual(laws.value("min_wage", "value"), 1200)           # a antiga continua valendo enquanto a nova tramita
        self.assertEqual(laws.current_values("min_wage"), {"value": 1200})

    def test_the_scope_stays_blocked_until_the_force_date_passes(self):
        pid = self.to_voting()
        self.vote_all(pid, ["yes"] * 5)
        self.go(SANCTION_END)
        self.assertEqual(self.propose(value=1500).code, "LAW_BLOCKED")    # aguardando vigor ainda é ativa (07 §07.17)
        self.go(FORCE)
        self.assertTrue(self.propose(value=1500).ok)

    def test_revocation_uses_the_full_process_and_keeps_history(self):
        pid = self.to_voting()
        self.vote_all(pid, ["yes"] * 5)
        self.go(FORCE)
        self.assertTrue(laws.in_force("min_wage"))
        res = proposals.create_proposal(self.president.pk, {"law": "min_wage", "revoke": True, "description": "revogar"})
        rid = self.pid(res)
        self.go(self.get(rid).deadline_at)
        self.vote_all(rid, ["yes"] * 5)
        for _ in range(3):
            self.go(self.get(rid).deadline_at)
        self.assertEqual(self.get(rid).status, Status.ENACTED.value)
        self.assertFalse(laws.in_force("min_wage"))
        self.assertEqual(laws.value("min_wage", "value"), 1000)           # volta ao padrão do catálogo
        law = Law.objects.get(key="min_wage")
        self.assertEqual((law.status, law.revoked_at), ("revoked", self.get(rid).force_at))
        self.assertEqual([c.kind for c in LawChange.objects.filter(law_key="min_wage")], ["change", "revoke"])
        from legislation import views
        self.assertEqual(len(views.law_view("min_wage")["history"]), 2)        # histórico consultável depois da revogação
        self.assertEqual(self.get(pid).status, Status.ENACTED.value)

    def test_enacting_again_after_a_revocation_reactivates_the_law(self):
        pid = self.to_voting()
        self.vote_all(pid, ["yes"] * 5)
        self.go(FORCE)
        rid = self.pid(proposals.create_proposal(self.president.pk, {"law": "min_wage", "revoke": True}))
        self.go(self.get(rid).deadline_at)
        self.vote_all(rid, ["yes"] * 5)
        for _ in range(3):
            self.go(self.get(rid).deadline_at)
        nid = self.pid(self.propose(value=1700))
        self.go(self.get(nid).deadline_at)
        self.vote_all(nid, ["yes"] * 5)
        for _ in range(3):
            self.go(self.get(nid).deadline_at)
        self.assertEqual(laws.value("min_wage", "value"), 1700)
        self.assertEqual(Law.objects.get(key="min_wage").status, "in_force")
        self.assertIsNone(Law.objects.get(key="min_wage").revoked_at)

    def test_laws_in_different_scopes_enter_force_on_the_same_tick(self):
        self.clk.set(FRI_BEFORE)
        a, b = self.pid(self.propose(law="min_wage", value=1200)), self.pid(self.propose(who=self.deps[0], law="sales_tax", value=9))
        self.go(NEXT_MON)
        self.vote_all(a, ["yes"] * 5)
        self.vote_all(b, ["yes"] * 5)
        self.go(FORCE)
        self.assertEqual((laws.value("min_wage", "value"), laws.value("sales_tax", "rate")), (1200, "9"))

    def test_coherence_is_checked_against_the_current_minimum_wage(self):
        pid = self.to_voting()
        self.vote_all(pid, ["yes"] * 5)
        self.go(FORCE)
        self.assertEqual(self.propose(law="wage_ceiling", value=1100).code, "VALIDATION_FAILED")      # teto < novo mínimo (1200)
        self.assertTrue(self.propose(law="wage_ceiling", value=1200).ok)
