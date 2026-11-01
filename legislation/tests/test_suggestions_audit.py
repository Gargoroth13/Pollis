from legislation import suggestions, views
from legislation.audit import audit_legislation
from legislation.constants import Status
from legislation.models import LawChange, Proposal, ProposalVersion, Suggestion, VoteRecord, VoteRound
from legislation.tests.base import FRI_BEFORE, LegislationBase, at


class SuggestionTests(LegislationBase):
    def suggest(self, who=None, **extra):
        return suggestions.suggest_law((who or self.gov).pk, {"law": "min_wage", "params": {"value": 1300}, **extra})

    def test_governor_suggests_and_the_president_formalizes_becoming_the_author(self):
        res = self.suggest(description="pedido do Estado")
        self.assertTrue(res.ok, res)
        self.assertEqual(Proposal.objects.count(), 0)                    # sugestão não é proposta
        out = suggestions.adopt_suggestion(self.president.pk, {"suggestion": res.detail["suggestion"]})
        self.assertTrue(out.ok, out)
        p = self.get(out.detail["proposal"])
        self.assertEqual((p.author_id, p.params, p.description), (self.president.pk, {"value": 1300}, "pedido do Estado"))
        s = Suggestion.objects.get()
        self.assertEqual((s.status, s.proposal_id, s.decided_by_id), ("adopted", p.pk, self.president.pk))

    def test_only_governors_and_mayors_suggest(self):
        for who in (self.other, self.deps[0], self.president):
            self.assertEqual(self.suggest(who).code, "NOT_A_SUGGESTER")

    def test_suggestions_are_validated_like_proposals(self):
        self.assertEqual(suggestions.suggest_law(self.gov.pk, {"law": "min_wage", "params": {"value": 5}}).code, "PARAM_OUT_OF_RANGE")
        self.assertEqual(suggestions.suggest_law(self.gov.pk, {"law": "ghost", "params": {}}).code, "UNKNOWN_LAW")
        self.assertEqual(suggestions.suggest_law(self.gov.pk, {"law": "wage_ceiling", "params": {"value": 500}}).code, "VALIDATION_FAILED")

    def test_only_the_president_decides_once(self):
        sid = self.suggest().detail["suggestion"]
        self.assertEqual(suggestions.adopt_suggestion(self.deps[0].pk, {"suggestion": sid}).code, "NOT_PRESIDENT")
        self.assertTrue(suggestions.dismiss_suggestion(self.president.pk, {"suggestion": sid}).ok)
        self.assertEqual(suggestions.adopt_suggestion(self.president.pk, {"suggestion": sid}).code, "SUGGESTION_DECIDED")
        self.assertEqual(suggestions.dismiss_suggestion(self.president.pk, {"suggestion": 10 ** 9}).code, "SUGGESTION_NOT_FOUND")

    def test_adoption_is_refused_with_the_proposal_rules_and_stays_pending(self):
        sid = self.suggest().detail["suggestion"]
        self.pid(self.propose(who=self.deps[0], value=1500))             # já há proposta do mesmo grupo
        res = suggestions.adopt_suggestion(self.president.pk, {"suggestion": sid})
        self.assertEqual(res.code, "LAW_BLOCKED")
        self.assertEqual(Suggestion.objects.get().status, "pending")
        self.assertEqual(len(views.suggestions_view()), 1)


class AuditTests(LegislationBase):
    audit_at_end = False

    def finished(self):
        pid = self.to_voting()
        self.vote_all(pid, ["yes", "yes", "yes", "no", None])
        for _ in range(4):
            self.go(self.get(pid).deadline_at or at(10, 19))
        return pid

    def codes(self):
        return sorted({f["code"] for f in audit_legislation().findings})

    def test_a_clean_history_audits_ok(self):
        self.finished()
        report = audit_legislation()
        self.assertTrue(report.ok, report.findings)
        self.assertEqual((report.stats["proposals"], report.stats["rounds"]), (1, 1))

    def test_tampered_vote_count_is_detected(self):
        pid = self.finished()
        VoteRecord.objects.filter(round__proposal_id=pid, choice="no").update(choice="yes")
        self.assertIn("TALLY_MISMATCH", self.codes())

    def test_vote_outside_the_frozen_composition_is_detected(self):
        pid = self.to_voting()
        VoteRecord.objects.create(round=VoteRound.objects.get(proposal_id=pid), deputy_id=self.other.pk, choice="yes", at=at(10, 13))
        self.assertIn("VOTE_OUTSIDE_COMPOSITION", self.codes())

    def test_vote_after_the_deadline_is_detected(self):
        pid = self.to_voting()
        VoteRecord.objects.create(round=VoteRound.objects.get(proposal_id=pid), deputy_id=self.deps[0].pk, choice="yes", at=at(10, 16))
        self.assertIn("VOTE_OUTSIDE_WINDOW", self.codes())

    def test_enacted_without_change_and_law_mismatch_are_detected(self):
        pid = self.finished()
        self.assertEqual(self.get(pid).status, Status.ENACTED.value)
        LawChange.objects.all().delete()
        self.assertIn("ENACTED_PROPOSAL_CHANGE_MISMATCH", self.codes())

    def test_law_value_changed_directly_is_detected(self):
        self.finished()
        from legislation.models import Law
        Law.objects.update(params={"value": 9999})
        self.assertIn("LAW_STATE_MISMATCH", self.codes())

    def test_version_gap_and_state_tampering_are_detected(self):
        pid = self.to_voting()
        ProposalVersion.objects.filter(proposal_id=pid).update(number=3)
        Proposal.objects.filter(pk=pid).update(status="sanction")
        found = self.codes()
        self.assertIn("VERSIONS_NOT_CONTIGUOUS", found)
        self.assertIn("OPEN_ROUND_MISMATCH", found)
        self.assertIn("STAGE_WITHOUT_APPROVED_VOTE", found)

    def test_force_date_not_on_a_weekly_tick_is_detected(self):
        pid = self.to_voting()
        self.vote_all(pid, ["yes"] * 5)
        self.go(at(10, 18))
        Proposal.objects.filter(pk=pid).update(force_at=at(10, 20), deadline_at=at(10, 20))
        self.assertIn("FORCE_AT_INVALID", self.codes())

    def test_terminal_state_with_deadline_is_detected(self):
        pid = self.to_voting()
        self.vote_all(pid, ["no"] * 5)
        self.go(at(10, 15))
        Proposal.objects.filter(pk=pid).update(deadline_at=at(10, 20))
        self.assertIn("TERMINAL_STATE_FIELDS", self.codes())

    def test_management_command_fails_on_violations(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from io import StringIO
        pid = self.to_voting()
        call_command("audit_legislation", stdout=StringIO())
        Proposal.objects.filter(pk=pid).update(scope="weird")
        with self.assertRaises(CommandError):
            call_command("audit_legislation", stdout=StringIO())


class ViewTests(LegislationBase):
    def test_proposal_view_exposes_everything_the_design_makes_public(self):
        self.clk.set(FRI_BEFORE)
        pid = self.pid(self.propose(description="d"))
        self.go(at(10, 12))
        self.vote_all(pid, ["yes", "no", None, None, None])
        view = views.proposal_view(pid)
        self.assertEqual((view["author"], view["status"], view["version"], view["description"]), (self.president.pk, "voting", 1, "d"))
        self.assertEqual(view["versions"][0]["params"], {"value": 1200})
        self.assertEqual(view["rounds"][0]["votes"][str(self.deps[0].pk)], "yes")
        self.assertEqual(view["preview"]["direct_effects"][0]["to"], 1200)
        self.assertIn("created", [e["kind"] for e in view["events"]])
        self.assertIsNone(views.proposal_view(10 ** 9))
        self.assertEqual([p["proposal"] for p in views.list_proposals(status="voting")], [pid])
        self.assertEqual(views.list_proposals(law="sales_tax"), [])
        self.assertIsNone(views.law_view("ghost"))
        self.assertEqual(views.law_view("min_wage")["in_force"], False)
        self.assertEqual(views.calendar_view(at(10, 12))["next_weekly_tick"], at(10, 19))
