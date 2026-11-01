"""Leis (12.6, 12.14): só leis marcadas `newsworthy` no catálogo geram notícia; aprovação, veto, derrubada e vigor, cada um uma vez."""
from dataclasses import replace

from history.models import NewsItem
from legislation import catalog, proposals, voting
from legislation.tests.base import FRI_BEFORE, LegislationBase, at

from .base import AuditMixin

VOTE_END = at(10, 15)
FORCE = at(10, 19)
OVERRIDE_START = at(10, 19)
OVERRIDE_END = at(10, 22)
FORCE_AFTER_OVERRIDE = at(10, 26)


class LawNewsBase(AuditMixin, LegislationBase):
    newsworthy = True

    def setUp(self):
        super().setUp()
        spec = catalog.get("min_wage")
        catalog.clear_catalog()
        for s in (spec, catalog.LawSpec("sales_tax", "Imposto sobre vendas", (catalog.ParamSpec("rate", "decimal", 0, 30, 5),))):
            catalog.register_law(replace(s, newsworthy=self.newsworthy) if s.key == "min_wage" else s)

    def kinds(self):
        return [n.template_key for n in NewsItem.objects.filter(category="politics").order_by("at", "pk")]

    def approve(self, pid, yes=5):
        self.vote_all(pid, ["yes"] * yes + [None] * (5 - yes))
        self.go(VOTE_END)


class NewsworthyLawTests(LawNewsBase):
    def test_approval_then_sanction_then_force_publishes_approval_and_force_only(self):
        pid = self.to_voting()
        self.approve(pid, 3)
        self.assertEqual(self.kinds(), ["politics.law_approved"])
        n = NewsItem.objects.get()
        self.assertIn("Salário mínimo", n.headline)
        self.assertIn("3 votos", n.body)
        self.assertIn("5 cadeiras", n.body)
        self.assertEqual((n.ref_kind, n.ref_id, n.at), ("law", "min_wage", VOTE_END))
        self.assertTrue(voting.sanction(self.president.pk, {"proposal": pid}).ok)
        self.assertEqual(self.kinds(), ["politics.law_approved"])            # sanção não está na lista do 12
        self.go(FORCE)
        self.assertEqual(self.kinds(), ["politics.law_approved", "politics.law_in_force"])

    def test_veto_and_override_and_force_each_publish_once(self):
        pid = self.to_voting()
        self.approve(pid, 5)
        self.assertTrue(voting.veto(self.president.pk, {"proposal": pid, "justification": "x"}).ok)
        self.assertEqual(self.kinds(), ["politics.law_approved", "politics.law_vetoed"])
        self.go(OVERRIDE_START)
        self.vote_all(pid, ["yes"] * 4 + [None])
        self.go(OVERRIDE_END)
        self.assertEqual(self.kinds()[-1], "politics.veto_overridden")
        self.go(FORCE_AFTER_OVERRIDE)
        self.assertEqual(self.kinds(), ["politics.law_approved", "politics.law_vetoed", "politics.veto_overridden", "politics.law_in_force"])
        over = NewsItem.objects.get(template_key="politics.veto_overridden")
        self.assertIn("4 votos", over.body)
        self.go(FORCE_AFTER_OVERRIDE + 600)
        self.assertEqual(NewsItem.objects.count(), 4)                       # reprocessar não duplica

    def test_a_sustained_veto_and_a_rejected_vote_publish_nothing_more(self):
        pid = self.to_voting()
        self.approve(pid, 3)
        voting.veto(self.president.pk, {"proposal": pid})
        self.go(OVERRIDE_START)
        self.vote_all(pid, ["yes"] * 3 + [None] * 2)                         # 3/5 < 2/3
        self.go(OVERRIDE_END)
        self.assertEqual(self.kinds(), ["politics.law_approved", "politics.law_vetoed"])

    def test_a_rejected_proposal_publishes_nothing(self):
        pid = self.to_voting()
        self.vote_all(pid, ["no", "no", "yes", None, None])
        self.go(VOTE_END)
        self.assertEqual(self.get(pid).status, "rejected")
        self.assertEqual(NewsItem.objects.count(), 0)

    def test_automatic_sanction_path_publishes_approval_and_force(self):
        pid = self.to_voting()
        self.approve(pid, 3)
        self.go(at(10, 18))                                                 # prazo da sanção vence: sanção automática
        self.go(FORCE)
        self.assertEqual(self.kinds(), ["politics.law_approved", "politics.law_in_force"])

    def test_a_revocation_has_its_own_wording(self):
        pid = self.to_voting()
        self.approve(pid, 3)
        voting.sanction(self.president.pk, {"proposal": pid})
        self.go(FORCE)                                                      # a lei passa a vigorar
        self.assertEqual(self.get(pid).status, "enacted")
        self.clk.set(at(10, 19, 12))
        rid = self.pid(proposals.create_proposal(self.president.pk, {"law": "min_wage", "revoke": True}))
        self.go(at(10, 26))                                                 # discussão termina; votação abre na segunda
        self.vote_all(rid, ["yes"] * 3 + [None] * 2)
        self.go(at(10, 29))
        voting.sanction(self.president.pk, {"proposal": rid})
        self.go(at(11, 2))
        approved = NewsItem.objects.filter(template_key="politics.law_approved").order_by("-pk").first()
        self.assertIn("revogação", approved.headline)
        forced = NewsItem.objects.filter(template_key="politics.law_in_force").order_by("-pk").first()
        self.assertIn("revogada", forced.body)

    def test_news_text_never_invents_importance_or_reasons(self):
        pid = self.to_voting()
        self.approve(pid, 3)
        n = NewsItem.objects.get()
        for word in ("importante", "histórica", "polêmica", "devido a"):
            self.assertNotIn(word, (n.headline + n.body).lower())


class NotNewsworthyLawTests(LawNewsBase):
    newsworthy = False

    def test_a_law_not_marked_in_the_catalog_never_generates_news_through_the_whole_flow(self):
        pid = self.to_voting()
        self.approve(pid, 5)
        voting.veto(self.president.pk, {"proposal": pid})
        self.go(OVERRIDE_START)
        self.vote_all(pid, ["yes"] * 4 + [None])
        self.go(OVERRIDE_END)
        self.go(FORCE_AFTER_OVERRIDE)
        self.assertEqual(self.get(pid).status, "enacted")
        self.assertEqual(NewsItem.objects.count(), 0)


class ChangingNewsworthyTests(AuditMixin, LegislationBase):
    def test_the_default_of_the_catalog_is_not_newsworthy(self):
        self.assertFalse(catalog.get("min_wage").newsworthy)
