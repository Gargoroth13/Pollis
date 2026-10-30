from legislation import laws, voting
from legislation.constants import EventKind, RoundStatus, Status
from legislation.models import Interregnum, LegislativeState
from legislation.tests.base import DAY, FRI_BEFORE, NEXT_MON, LegislationBase, at

VOTE_END = at(10, 15)
SANCTION_END = at(10, 18)
FORCE = at(10, 19)


class InterregnumTests(LegislationBase):
    def lose_chamber(self, when):
        self.seats = []
        self.go(when)
        self.assertIsNotNone(LegislativeState.load().interregnum_since)

    def restore_chamber(self, when):
        self.seats = [d.pk for d in self.deps]
        self.go(when)
        self.assertIsNone(LegislativeState.load().interregnum_since)

    def test_discussion_is_extended_by_the_time_without_a_chamber(self):
        self.clk.set(FRI_BEFORE)
        pid = self.pid(self.propose())
        self.lose_chamber(at(10, 10, 12))                       # sábado 12:00
        self.go(NEXT_MON)                                        # a janela passa sem Câmara: nada abre
        self.assertEqual(self.get(pid).status, Status.DISCUSSION.value)
        self.restore_chamber(at(10, 14, 10))
        p = self.get(pid)
        shift = at(10, 14, 10) - at(10, 10, 12)
        self.assertEqual(p.discussion_ends_at, NEXT_MON + shift)
        self.assertEqual(p.deadline_at, at(10, 19))              # próxima segunda depois da discussão prorrogada
        self.assertIn(EventKind.DEADLINES_SHIFTED.value, [e.kind for e in p.events.all()])
        self.go(at(10, 19))
        self.assertEqual(self.get(pid).status, Status.VOTING.value)
        self.assertEqual(Interregnum.objects.get().ended_at, at(10, 14, 10))

    def test_a_window_that_coincides_with_the_loss_of_the_chamber_does_not_open_a_vote_without_seats(self):
        self.clk.set(FRI_BEFORE)
        pid = self.pid(self.propose())
        self.seats = []
        self.go(NEXT_MON)                                        # a Câmara some antes de o motor ver a janela
        p = self.get(pid)
        self.assertEqual((p.status, p.round_no), (Status.DISCUSSION.value, 0))
        self.assertEqual(LegislativeState.load().interregnum_since, NEXT_MON)
        self.restore_chamber(at(10, 13))
        self.assertEqual(self.get(pid).deadline_at, at(10, 19))

    def test_proposals_created_during_the_interregnum_are_only_extended_from_creation(self):
        self.lose_chamber(at(10, 5, 13))                          # segunda 13:00, sem Câmara
        self.clk.set(at(10, 6, 9))
        pid = self.pid(self.propose())                           # propor é permitido (07 §07.3), mas nada corre
        created_ends = self.get(pid).discussion_ends_at
        self.restore_chamber(at(10, 7, 9))
        self.assertEqual(self.get(pid).discussion_ends_at, created_ends + (at(10, 7, 9) - at(10, 6, 9)))

    def test_a_vote_in_progress_is_voided_and_restarted_with_three_full_days(self):
        pid = self.to_voting()
        self.vote_all(pid, ["yes", "yes", "yes", None, None])
        self.lose_chamber(at(10, 13, 8))
        self.go(VOTE_END)                                        # o prazo original passa sem Câmara: nada é apurado
        self.assertEqual(self.get(pid).status, Status.VOTING.value)
        self.restore_chamber(at(10, 20, 9))
        p = self.get(pid)
        old, new = list(p.rounds.all())
        self.assertEqual((old.status, old.void_reason.startswith("interregnum"), old.tally), (RoundStatus.VOIDED.value, True, None))
        self.assertEqual((new.status, new.started_at, new.ends_at, p.deadline_at), (RoundStatus.OPEN.value, at(10, 20, 9), at(10, 23, 9), at(10, 23, 9)))
        self.assertEqual(self.vote(pid, self.deps[3], "yes").ok, True)
        self.assertEqual(new.records.count(), 1)                 # a votação anterior NÃO é aproveitada
        self.vote_all(pid, ["yes", "yes", None, None, None])
        self.go(at(10, 23, 9))
        self.assertEqual(self.get(pid).status, Status.SANCTION.value)
        self.assertEqual(self.get(pid).rounds.get(number=2).tally["yes"], 3)         # só os votos da nova votação

    def test_stages_awaiting_sanction_veto_or_override_return_to_a_full_vote(self):
        a = self.to_voting()
        self.vote_all(a, ["yes"] * 5)
        self.go(VOTE_END)
        self.assertEqual(self.get(a).status, Status.SANCTION.value)
        self.lose_chamber(at(10, 16, 9))
        self.restore_chamber(at(10, 17, 9))
        p = self.get(a)
        self.assertEqual((p.status, p.round_no), (Status.VOTING.value, 2))
        self.assertEqual(p.rounds.get(number=2).ends_at, at(10, 20, 9))
        self.assertIn(EventKind.RETURNED_TO_VOTE.value, [e.kind for e in p.events.all()])

    def test_vetoed_proposals_also_return_to_a_full_vote(self):
        a = self.to_voting()
        self.vote_all(a, ["yes"] * 5)
        self.go(VOTE_END)
        self.clk.set(at(10, 16, 9))
        voting.veto(self.president.pk, {"proposal": a})
        self.lose_chamber(at(10, 17, 9))
        self.restore_chamber(at(10, 18, 9))
        self.assertEqual(self.get(a).status, Status.VOTING.value)

    def test_sanctioned_laws_awaiting_only_the_date_follow_the_normal_calendar(self):
        a = self.to_voting()
        self.vote_all(a, ["yes"] * 5)
        self.go(VOTE_END)
        self.clk.set(at(10, 16, 9))
        voting.sanction(self.president.pk, {"proposal": a})
        self.lose_chamber(at(10, 17, 9))
        self.go(FORCE)                                           # sem Câmara, mas a lei sancionada entra em vigor
        self.assertEqual(self.get(a).status, Status.ENACTED.value)
        self.assertEqual(laws.value("min_wage", "value"), 1200)
        self.restore_chamber(at(10, 21, 9))
        self.assertEqual(self.get(a).status, Status.ENACTED.value)

    def test_an_active_chamber_never_opens_an_interregnum(self):
        self.go(at(10, 7))
        self.assertFalse(Interregnum.objects.exists())

    def test_two_interregna_are_recorded_separately(self):
        self.lose_chamber(at(10, 6))
        self.restore_chamber(at(10, 7))
        self.lose_chamber(at(10, 8))
        self.restore_chamber(at(10, 9))
        self.assertEqual([(i.started_at, i.ended_at) for i in Interregnum.objects.all()], [(at(10, 6), at(10, 7)), (at(10, 8), at(10, 9))])


class PresidentChangeTests(LegislationBase):
    def awaiting_sanction(self):
        pid = self.to_voting()
        self.vote_all(pid, ["yes"] * 5)
        self.go(VOTE_END)
        self.assertEqual(self.get(pid).status, Status.SANCTION.value)
        self.assertEqual(self.get(pid).president_id, self.president.pk)
        return pid

    def test_president_change_returns_the_proposal_to_a_complete_new_vote(self):
        pid = self.awaiting_sanction()
        successor = self.new_player("successor")
        self.president_id = successor.pk
        self.go(at(10, 16, 9))
        p = self.get(pid)
        self.assertEqual((p.status, p.round_no, p.president_id), (Status.VOTING.value, 2, None))
        old = p.rounds.get(number=1)
        self.assertEqual(old.status, RoundStatus.CLOSED.value)           # a votação já apurada fica como está; a nova é completa
        self.assertEqual(p.rounds.get(number=2).ends_at, at(10, 19, 9))
        self.assertEqual(voting.sanction(self.president.pk, {"proposal": pid}).code, "NOT_AWAITING_SANCTION")
        self.vote_all(pid, ["yes"] * 5)
        self.go(at(10, 19, 9))
        p = self.get(pid)
        self.assertEqual((p.status, p.president_id, p.deadline_at), (Status.SANCTION.value, successor.pk, at(10, 22, 9)))
        self.clk.set(at(10, 20))
        self.assertTrue(voting.sanction(successor.pk, {"proposal": pid}).ok)

    def test_former_president_cannot_sanction_after_losing_office(self):
        pid = self.awaiting_sanction()
        self.president_id = self.other.pk
        self.assertEqual(voting.sanction(self.president.pk, {"proposal": pid}).code, "NOT_PRESIDENT")

    def test_deposition_keeps_proposals_and_laws(self):
        a = self.to_voting()
        self.vote_all(a, ["yes"] * 5)
        self.go(FORCE)
        self.assertEqual(laws.value("min_wage", "value"), 1200)
        b = self.pid(self.propose(law="sales_tax", value=9))
        self.president_id = None                                        # deposto
        self.go(at(10, 20))
        self.assertEqual(laws.value("min_wage", "value"), 1200)          # a lei vigente não é revogada
        self.assertEqual(self.get(b).status, Status.DISCUSSION.value)    # a proposta continua registrada

    def test_vacant_presidency_pauses_the_sanction_clock_until_there_is_a_president(self):
        pid = self.to_voting()
        self.president_id = None
        self.vote_all(pid, ["yes"] * 5)
        self.go(VOTE_END)
        p = self.get(pid)
        self.assertEqual((p.status, p.president_id, p.deadline_at), (Status.SANCTION.value, None, None))
        self.go(at(10, 30))                                             # sem Presidente nada é sancionado automaticamente
        self.assertEqual(self.get(pid).status, Status.SANCTION.value)
        newcomer = self.new_player("new_president")
        self.president_id = newcomer.pk
        self.go(at(10, 31, 9))
        p = self.get(pid)
        self.assertEqual((p.president_id, p.deadline_at), (newcomer.pk, at(11, 3, 9)))
        self.clk.set(at(11, 1))
        self.assertTrue(voting.veto(newcomer.pk, {"proposal": pid}).ok)

    def test_president_vacancy_after_the_proposal_was_sent_returns_it_to_the_chamber(self):
        pid = self.awaiting_sanction()
        self.president_id = None
        self.go(at(10, 16, 9))
        self.assertEqual(self.get(pid).status, Status.VOTING.value)
        self.assertIn("president_vacant", [e.data.get("reason") for e in self.get(pid).events.all()])
