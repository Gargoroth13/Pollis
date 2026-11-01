"""Empresas (12.5), política (12.6) e conflitos (12.7): o que cada sistema de origem envia e o que o 12 publica."""
from decimal import Decimal as D

from companies.constants import CompanyType
from companies.tests.base import CompanyTestCase
from history import news, texts
from history.constants import Office, Priority, Status
from history.models import NewsItem
from players.tests.base import T0, PlayerTestCase

from .base import AuditMixin


class FoundingMilestoneTests(AuditMixin, CompanyTestCase):
    def milestones(self):
        return list(NewsItem.objects.filter(category="milestone", template_key="milestone.first_company").order_by("pk"))

    def test_the_first_company_of_a_type_is_a_milestone_with_its_name_and_a_reference(self):
        company_id = self.found(self.player, "industrial", "Atlas")
        from companies.models import Company
        company = Company.objects.get(pk=company_id)
        (m,) = self.milestones()
        self.assertEqual(m.headline, texts.render("milestone.first_company", {"company": "Atlas", "type_phrase": "Industrial"}, m.dedupe_key)[1])
        self.assertIn("Atlas", m.headline + m.body)
        self.assertIn("Industrial", m.headline + m.body)
        self.assertEqual((m.ref_kind, m.ref_id, m.at, m.priority), ("company", str(company.pk), company.founded_at, int(Priority.MILESTONE)))

    def test_the_second_company_of_the_same_type_is_not_a_milestone_but_another_type_is(self):
        self.found(self.player, "retail", "L1")
        self.found(self.other, "retail", "L2")
        self.assertEqual(len(self.milestones()), 1)
        self.found(self.player, "services", "S1")
        self.assertEqual(sorted(m.data["type"] for m in self.milestones()), ["retail", "services"])

    def test_every_company_type_has_a_milestone_text(self):
        self.assertEqual(set(texts.COMPANY_TYPE_PHRASE), {t.value for t in CompanyType})

    def test_a_refused_founding_publishes_nothing(self):
        from companies import services
        self.assertFalse(services.found_company(self.player.pk, "nao_existe", "X", 0).ok)
        self.assertFalse(services.found_company(self.player.pk, "financial", "", 0).ok)
        self.assertEqual(self.milestones(), [])

    def test_unknown_type_is_a_programming_error_not_silence(self):
        with self.assertRaises(ValueError):
            news.company_founded(1, "X", "alien", T0)


class BankruptcyTests(AuditMixin, PlayerTestCase):
    def test_a_5_star_company_gets_a_global_news_without_an_invented_reason(self):
        res = news.company_bankrupt(7, "Industrial Atlas", 5, T0)
        self.assertEqual(res.status, Status.PUBLISHED)
        n = res.item
        self.assertIn("Industrial Atlas", n.headline + n.body)
        self.assertIn("5★", n.body)
        self.assertEqual((n.category, n.priority, n.ref_kind, n.ref_id), ("economy", int(Priority.BANKRUPTCY), "company", "7"))

    def test_below_5_stars_has_no_global_news_and_6_stars_has(self):
        self.assertEqual(news.company_bankrupt(1, "A", 4, T0).status, Status.NOT_NEWSWORTHY)
        self.assertEqual(NewsItem.objects.count(), 0)
        self.assertTrue(news.company_bankrupt(2, "B", 6, T0).ok)

    def test_a_company_goes_bankrupt_once(self):
        news.company_bankrupt(3, "C", 5, T0)
        self.assertEqual(news.company_bankrupt(3, "C", 5, T0 + 10).status, Status.DUPLICATE)
        self.assertEqual(NewsItem.objects.count(), 1)

    def test_invalid_stars(self):
        for bad in (-1, "5", True, None):
            with self.assertRaises(ValueError):
                news.company_bankrupt(1, "A", bad, T0)


class ElectionTests(AuditMixin, PlayerTestCase):
    def test_the_winner_and_the_real_percentage_are_in_the_text(self):
        res = news.election_concluded(Office.PRESIDENT, 1, "João", 534, 1000, T0)
        n = res.item
        self.assertIn("João", n.headline + n.body)
        self.assertIn("53,4%", n.body + n.headline)
        self.assertEqual((n.category, n.priority), ("politics", int(Priority.ELECTION)))
        self.assertEqual(D(n.data["pct"]), D("53.4"))

    def test_percentage_edges(self):
        self.assertEqual(news.election_pct(1, 1), D(100))
        self.assertEqual(news.election_pct(0, 5), D(0))
        self.assertEqual(news.election_pct(1, 3), D("33.333333"))
        for votes, total in ((1, 0), (6, 5), (-1, 5)):
            with self.assertRaises(ValueError):
                news.election_pct(votes, total)

    def test_58_2_percent_mayor_with_jurisdiction(self):
        n = news.election_concluded(Office.MAYOR, "m1", "João", 582, 1000, T0, jurisdiction="Nova Polis").item
        self.assertIn("Nova Polis", n.headline)
        self.assertIn("58,2%", n.headline + n.body)

    def test_the_first_election_of_each_office_is_a_milestone_exactly_once(self):
        news.election_concluded(Office.PRESIDENT, 1, "A", 6, 10, T0)
        news.election_concluded(Office.PRESIDENT, 2, "B", 6, 10, T0 + 100)
        news.election_concluded(Office.GOVERNOR, "g1", "C", 6, 10, T0 + 200)
        news.chamber_elected("c1", 5, T0 + 300)
        news.chamber_elected("c2", 5, T0 + 400)
        marks = NewsItem.objects.filter(category="milestone")
        self.assertEqual(sorted(m.dedupe_key for m in marks), ["milestone:first_election:chamber", "milestone:first_election:governor",
                                                              "milestone:first_election:president"])
        self.assertEqual(NewsItem.objects.filter(template_key="politics.election_winner").count(), 3)    # cada resultado é notícia

    def test_republishing_the_same_election_is_idempotent(self):
        news.election_concluded(Office.PRESIDENT, 1, "A", 6, 10, T0)
        self.assertEqual(news.election_concluded(Office.PRESIDENT, 1, "A", 6, 10, T0).status, Status.DUPLICATE)
        self.assertEqual(NewsItem.objects.count(), 2)

    def test_the_chamber_has_its_own_function(self):
        with self.assertRaises(ValueError):
            news.election_concluded(Office.CHAMBER, 1, "A", 6, 10, T0)

    def test_deposition_is_the_top_priority(self):
        n = news.government_change("d1", "Ana", "Bruno", T0).item
        self.assertEqual((n.priority, n.category), (int(Priority.GOVERNMENT_CHANGE), "politics"))
        self.assertIn("Bruno", n.headline + n.body)


class ConflictTests(AuditMixin, PlayerTestCase):
    def test_start_and_result_are_news_with_a_conflict_category(self):
        a = news.conflict_started("a1", "Milícia Aurora", "o governo", T0).item
        b = news.conflict_result("a1", "Milícia Aurora", "o governo", True, T0 + 3600).item
        c = news.conflict_result("a2", "Milícia Aurora", "o governo", False, T0 + 7200).item
        self.assertEqual({a.category, b.category, c.category}, {"conflict"})
        self.assertIn("inicia ação", a.headline)
        self.assertIn("vence", b.headline)
        self.assertIn("derrotada", c.headline)
        self.assertEqual(a.priority, int(Priority.CONFLICT))

    def test_the_api_has_no_entry_point_for_individual_movements(self):
        public = {n for n in dir(news) if n.startswith("conflict_")}
        self.assertEqual(public, {"conflict_started", "conflict_result"})        # 12.7: movimentação individual não vira notícia

    def test_repeating_the_same_action_events_does_not_spam(self):
        news.conflict_started("a1", "F", "T", T0)
        news.conflict_started("a1", "F", "T", T0 + 5)
        self.assertEqual(NewsItem.objects.count(), 1)
