from legislation import authority, catalog, laws, preview, proposals
from legislation.constants import EventKind, Status
from legislation.models import Law, Proposal, ProposalEvent
from legislation.tests.base import DAY, FRI_BEFORE, NEXT_MON, LegislationBase, at
from players import registry


class CreateTests(LegislationBase):
    def test_the_president_and_a_deputy_can_propose(self):
        a = self.propose(self.president, "min_wage", 1200)
        b = self.propose(self.deps[0], "sales_tax", 8)
        self.assertTrue(a.ok and b.ok, (a, b))
        p = self.get(a.detail["proposal"])
        self.assertEqual((p.status, p.version, p.author_id, p.params), (Status.DISCUSSION.value, 1, self.president.pk, {"value": 1200}))
        self.assertEqual(self.get(b.detail["proposal"]).params, {"rate": "8"})        # decimal canônico (string)

    def test_governors_mayors_and_ordinary_players_cannot_formalize(self):
        for who in (self.gov, self.other):
            self.assertEqual(self.propose(who).code, "NOT_A_PROPOSER")
        self.assertEqual(Proposal.objects.count(), 0)

    def test_no_provider_means_nobody_proposes(self):
        authority.clear_providers()
        self.assertEqual(self.propose().code, "NOT_A_PROPOSER")

    def test_conflicting_providers_fail_instead_of_choosing(self):
        authority.register_provider("other", authority.OfficeProvider(lambda: self.other.pk, lambda: [], lambda: frozenset()))
        self.assertEqual(self.propose().code, "OFFICE_CONFLICT")

    def test_unknown_law_and_invalid_targets(self):
        self.assertEqual(proposals.create_proposal(self.president.pk, {"law": "ghost", "params": {"value": 1}}).code, "UNKNOWN_LAW")
        self.assertEqual(proposals.create_proposal(self.president.pk, {"params": {"value": 1}}).code, "INVALID_PARAMS")
        self.assertEqual(proposals.create_proposal(self.president.pk, {"law": "min_wage"}).code, "INVALID_PARAMS")
        self.assertEqual(proposals.create_proposal(self.president.pk, {"law": "min_wage", "params": {"value": 1200, "extra": 1}}).code, "INVALID_PARAMS")
        self.assertEqual(proposals.create_proposal(self.president.pk, {"law": "min_wage", "params": {"value": 1200}, "description": 5}).code, "INVALID_DESCRIPTION")
        self.assertEqual(proposals.create_proposal(self.president.pk, "x").code, "INVALID_PARAMS")
        self.assertEqual(proposals.create_proposal(10 ** 9, {"law": "min_wage", "params": {"value": 1200}}).code, "PLAYER_NOT_FOUND")

    def test_parameter_limits_are_inclusive_and_types_are_strict(self):
        self.assertEqual(self.propose(value=99).code, "PARAM_OUT_OF_RANGE")
        self.assertEqual(self.propose(value=10001).code, "PARAM_OUT_OF_RANGE")
        self.assertTrue(self.propose(value=100).ok)
        for bad in (True, 1200.5, "abc", None, 12.0):
            self.assertEqual(self.propose(who=self.deps[0], law="min_wage", value=bad).code, "INVALID_PARAM_VALUE", bad)
        res = self.propose(law="sales_tax", value="30.0")
        self.assertTrue(res.ok, res)
        self.assertEqual(self.get(res.detail["proposal"]).params, {"rate": "30"})

    def test_sales_tax_range_is_checked_when_nothing_blocks(self):
        self.assertEqual(self.propose(law="sales_tax", value="30.01").code, "PARAM_OUT_OF_RANGE")
        self.assertEqual(self.propose(law="sales_tax", value="-0.01").code, "PARAM_OUT_OF_RANGE")

    def test_same_value_as_the_current_one_is_not_a_change(self):
        self.assertEqual(self.propose(value=1000).code, "NO_CHANGE")          # padrão do catálogo

    def test_revoking_requires_a_law_in_force(self):
        self.assertEqual(proposals.create_proposal(self.president.pk, {"law": "min_wage", "revoke": True}).code, "LAW_NOT_IN_FORCE")
        self.assertEqual(proposals.create_proposal(self.president.pk, {"law": "min_wage", "revoke": True, "params": {"value": 1}}).code, "INVALID_PARAMS")

    def test_description_limit(self):
        self.assertEqual(proposals.create_proposal(self.president.pk, {"law": "min_wage", "params": {"value": 1200}, "description": "x" * 1001}).code,
                         "INVALID_DESCRIPTION")
        self.assertTrue(proposals.create_proposal(self.president.pk, {"law": "min_wage", "params": {"value": 1200}, "description": "x" * 1000}).ok)

    def test_creation_records_version_event_and_window(self):
        self.clk.set(FRI_BEFORE)
        res = self.propose()
        p = self.get(res.detail["proposal"])
        self.assertEqual((p.created_at, p.discussion_ends_at, p.deadline_at), (FRI_BEFORE, NEXT_MON, NEXT_MON))
        self.assertEqual(res.detail["vote_window"], NEXT_MON)
        self.assertEqual([e.kind for e in p.events.all()], [EventKind.CREATED.value])
        self.assertEqual(p.versions.count(), 1)


class ConflictTests(LegislationBase):
    def test_a_second_proposal_for_the_same_law_is_blocked_by_any_active_stage(self):
        first = self.pid(self.propose())
        res = self.propose(who=self.deps[1], value=1500)
        self.assertEqual((res.code, res.detail["blocking_proposal"]), ("LAW_BLOCKED", first))

    def test_coupled_group_blocks_every_parameter_of_the_group(self):
        self.pid(self.propose(law="min_wage", value=1200))
        res = self.propose(law="wage_ceiling", value=30000)
        self.assertEqual(res.code, "LAW_BLOCKED")
        self.assertEqual(res.detail["scope"], "group:salaries")
        self.assertTrue(self.propose(law="sales_tax", value=8).ok)       # outro grupo: livre

    def test_withdrawing_frees_the_scope_immediately(self):
        first = self.pid(self.propose())
        self.assertTrue(proposals.withdraw_proposal(self.president.pk, {"proposal": first}).ok)
        self.assertTrue(self.propose(value=1500).ok)

    def test_database_refuses_two_active_proposals_in_one_scope(self):
        from django.db import IntegrityError, transaction
        first = self.get(self.pid(self.propose()))
        with self.assertRaises(IntegrityError), transaction.atomic():
            Proposal.objects.create(author_id=1, law_key="min_wage", scope=first.scope, kind="change", params={"value": 5}, created_at=1, discussion_ends_at=2)


class CoherenceTests(LegislationBase):
    def test_ceiling_below_the_minimum_wage_is_refused_with_the_failed_checks(self):
        res = self.propose(law="wage_ceiling", value=500)
        self.assertEqual(res.code, "VALIDATION_FAILED")
        self.assertEqual(res.detail["failed"][0]["key"], "ceiling_not_below_minimum_wage")
        self.assertEqual(res.detail["failed"][0]["minimum_wage"], 1000)

    def test_constitutional_floor_cannot_be_reduced_by_a_common_law(self):
        catalog.register_law(catalog.LawSpec("housing_floor", "Piso de moradia", (catalog.ParamSpec("pct", "int", 0, 100, 10),)))
        catalog.register_constitutional_floor("housing_floor", "pct", 8)
        res = proposals.create_proposal(self.president.pk, {"law": "housing_floor", "params": {"pct": 7}})
        self.assertEqual(res.code, "BELOW_CONSTITUTIONAL_FLOOR")
        self.assertTrue(proposals.create_proposal(self.president.pk, {"law": "housing_floor", "params": {"pct": 8}}).ok)

    def test_floor_for_unknown_parameter_is_rejected(self):
        with self.assertRaises(ValueError):
            catalog.register_constitutional_floor("min_wage", "nope", 1)

    def test_invalid_catalog_entries_are_rejected(self):
        with self.assertRaises(ValueError):
            catalog.ParamSpec("x", "int", 10, 5, 7)
        with self.assertRaises(ValueError):
            catalog.register_law(catalog.LawSpec("min_wage", "dup", (catalog.ParamSpec("v", "int", 0, 1, 0),)))
        with self.assertRaises(ValueError):
            catalog.register_law(catalog.LawSpec("empty", "empty", ()))


class EditAndWithdrawTests(LegislationBase):
    def setUp(self):
        super().setUp()
        self.clk.set(FRI_BEFORE - 2 * DAY)         # quarta 15:00
        self.pid_ = self.pid(self.propose())

    def edit(self, who=None, **target):
        return proposals.edit_proposal((who or self.president).pk, {"proposal": self.pid_, **target})

    def test_author_edits_parameters_creating_versions(self):
        self.assertTrue(self.edit(params={"value": 1300}).ok)
        self.assertTrue(self.edit(params={"value": 1400}, description="nova").ok)
        p = self.get(self.pid_)
        self.assertEqual((p.version, p.params, p.description), (3, {"value": 1400}, "nova"))
        self.assertEqual([(v.number, v.params["value"]) for v in p.versions.all()], [(1, 1200), (2, 1300), (3, 1400)])
        self.assertEqual(ProposalEvent.objects.filter(proposal=p, kind="edited").count(), 2)

    def test_edit_keeps_the_discussion_period(self):
        before = self.get(self.pid_).discussion_ends_at
        self.edit(params={"value": 1300})
        self.assertEqual(self.get(self.pid_).discussion_ends_at, before)

    def test_only_the_author_edits_or_withdraws(self):
        self.assertEqual(self.edit(who=self.deps[0], params={"value": 1300}).code, "NOT_AUTHOR")
        self.assertEqual(proposals.withdraw_proposal(self.deps[0].pk, {"proposal": self.pid_}).code, "NOT_AUTHOR")

    def test_edit_validations(self):
        self.assertEqual(self.edit(params={"value": 5}).code, "PARAM_OUT_OF_RANGE")
        self.assertEqual(self.edit(params={"value": 1200}).code, "NOTHING_CHANGED")
        self.assertEqual(self.edit(params={"value": 1000}).code, "NO_CHANGE")
        self.assertEqual(self.edit().code, "NOTHING_CHANGED")
        self.assertEqual(proposals.edit_proposal(self.president.pk, {"proposal": 10 ** 9}).code, "PROPOSAL_NOT_FOUND")
        self.assertEqual(proposals.edit_proposal(self.president.pk, {"params": {}}).code, "INVALID_PARAMS")

    def test_the_description_alone_can_change(self):
        self.assertTrue(self.edit(description="só texto").ok)
        self.assertEqual(self.get(self.pid_).version, 2)

    def test_after_the_window_the_proposal_is_frozen_even_before_the_engine_runs(self):
        self.clk.set(NEXT_MON)                       # janela aberta, motor ainda não processou
        self.assertEqual(self.get(self.pid_).status, Status.DISCUSSION.value)
        self.assertEqual(self.edit(params={"value": 1300}).code, "VOTING_STARTED")
        self.assertEqual(proposals.withdraw_proposal(self.president.pk, {"proposal": self.pid_}).code, "VOTING_STARTED")

    def test_after_voting_starts_nothing_changes(self):
        self.go(NEXT_MON)
        self.assertEqual(self.edit(params={"value": 1300}).code, "NOT_IN_DISCUSSION")
        self.assertEqual(proposals.withdraw_proposal(self.president.pk, {"proposal": self.pid_}).code, "NOT_IN_DISCUSSION")

    def test_withdrawn_proposal_keeps_its_history(self):
        res = proposals.withdraw_proposal(self.president.pk, {"proposal": self.pid_})
        self.assertTrue(res.ok)
        p = self.get(self.pid_)
        self.assertEqual((p.status, p.deadline_at, p.closed_at), (Status.WITHDRAWN.value, None, self.clk.now()))
        self.assertEqual(proposals.withdraw_proposal(self.president.pk, {"proposal": self.pid_}).code, "NOT_IN_DISCUSSION")

    def test_withdrawn_proposal_never_votes(self):
        proposals.withdraw_proposal(self.president.pk, {"proposal": self.pid_})
        self.go(NEXT_MON)
        self.assertEqual(self.get(self.pid_).status, Status.WITHDRAWN.value)
        self.assertEqual(self.get(self.pid_).rounds.count(), 0)

    def test_the_author_who_left_office_keeps_the_proposal_alive(self):
        self.president_id = None                      # perdeu o cargo (07 §07.20)
        self.go(NEXT_MON)
        p = self.get(self.pid_)
        self.assertEqual((p.status, p.author_id), (Status.VOTING.value, self.president.pk))


class ActionRegistryTests(LegislationBase):
    def test_actions_are_registered_and_use_the_same_refusals(self):
        for action in ("propose_law", "edit_proposal", "withdraw_proposal", "cast_vote", "sanction_proposal", "veto_proposal", "suggest_law",
                       "adopt_suggestion", "dismiss_suggestion"):
            self.assertIsNotNone(registry.get_descriptor(action), action)
        check = registry.check_action(self.other.pk, "propose_law", {"law": "min_wage", "params": {"value": 1200}})
        self.assertEqual((check.available, check.code), (False, "NOT_A_PROPOSER"))
        res = registry.execute_action(self.president.pk, "propose_law", {"law": "min_wage", "params": {"value": 1200}})
        self.assertTrue(res.ok, res)
        again = registry.check_action(self.deps[0].pk, "propose_law", {"law": "min_wage", "params": {"value": 1300}})
        self.assertEqual((again.available, again.code), (False, "LAW_BLOCKED"))

    def test_propose_preview_shows_direct_effects_estimates_and_validations(self):
        preview.register_estimator("sales_tax", lambda spec, cur, new: [{"key": "estimated_revenue_change_pct", "value": "12"}])
        res = registry.check_action(self.president.pk, "propose_law", {"law": "sales_tax", "params": {"rate": 8}})
        self.assertTrue(res.available, res)
        view = preview.preview("sales_tax", {"rate": "8"})
        self.assertEqual(view["direct_effects"], [{"param": "rate", "from": "5", "to": "8", "changed": True}])
        self.assertEqual(view["estimated_effects"], [{"key": "estimated_revenue_change_pct", "value": "12", "is_estimate": True}])
        self.assertEqual(view["estimates_note"], "estimates_are_not_guarantees")
        self.assertTrue(view["valid"])
        self.assertEqual(preview.preview("min_wage", {"value": 1200})["estimated_effects"], [])      # sem estimador, nada inventado


class CooldownTests(LegislationBase):
    def reject_one(self, value):
        pid = self.to_voting(value)
        self.vote_all(pid, ["yes", "yes", "no", "no", "no"])
        self.go(self.get(pid).deadline_at)
        self.assertEqual(self.get(pid).status, Status.REJECTED.value)
        return pid

    def test_resubmitting_a_rejected_proposal_waits_for_the_cooldown(self):
        self.reject_one(1200)
        end = Proposal.objects.first().closed_at
        self.clk.set(end + 3 * DAY - 1)
        for value in (1200, 1300):
            self.assertEqual(self.propose(value=value).code, "COOLDOWN_ACTIVE", value)
        self.clk.set(end + 3 * DAY)
        self.assertEqual(self.propose(value=1200).code, "COOLDOWN_ACTIVE")         # igual: ainda no cooldown cheio
        self.assertTrue(self.propose(value=1300).ok)                                # alterado: cooldown reduzido venceu

    def test_full_cooldown_expires(self):
        self.reject_one(1200)
        end = Proposal.objects.first().closed_at
        self.clk.set(end + 7 * DAY)
        self.assertTrue(self.propose(value=1200).ok)

    def test_cooldown_is_per_law(self):
        self.reject_one(1200)
        self.assertTrue(self.propose(law="sales_tax", value=8).ok)
