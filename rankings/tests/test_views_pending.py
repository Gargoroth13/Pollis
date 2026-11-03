"""Página pública (14.8), categorias pendentes sem dados inventados, escopo do Bot Test e auditoria (14.9)."""
import json

from rankings import audit, live, records
from rankings.constants import CATEGORIES, HISTORICAL, LIVE, Cat, Status
from rankings.models import ActivityStreak, RankingHistorico

from .base import DAY, HOUR, T0, RankingsTestCase


class PendingCategoriesTests(RankingsTestCase):
    def test_pending_and_out_of_scope_live_rankings_return_no_data(self):
        for c in LIVE:
            if c.status != Status.ACTIVE:
                r = live.live_ranking(c.key)
                self.assertFalse(r["available"], c.key)
                self.assertEqual((r["entries"], r["status"]), ([], c.status.value))
                self.assertTrue(r["depends_on"])

    def test_out_of_scope_political_influence_never_has_entries_even_with_activity(self):
        self.fund(self.acct(), 10)
        self.assertEqual(live.live_ranking(Cat.POLITICAL_INFLUENCE)["entries"], [])
        self.assertEqual(live.live_ranking(Cat.POLITICAL_INFLUENCE)["status"], "out_of_scope")

    def test_wrong_group_or_unknown_is_an_error(self):
        with self.assertRaises(ValueError):
            live.live_ranking(Cat.NET_WORTH_RECORD)
        with self.assertRaises(ValueError):
            live.historical_ranking(Cat.NET_WORTH)
        with self.assertRaises(ValueError):
            live.live_ranking("nope")

    def test_historical_pending_shows_no_record_until_one_exists(self):
        self.assertIsNone(live.historical_ranking(Cat.COMPANY_RECORD)["record"])
        self.assertFalse(live.historical_ranking(Cat.COMPANY_RECORD)["available"])
        r = live.historical_ranking(Cat.PRESIDENT_VOTE_RECORD)
        self.assertEqual((r["record"], r["available"]), (None, False))
        records.record_presidential_result(self.player.pk, "E1", 7_000, 10_000, T0)
        r = live.historical_ranking(Cat.PRESIDENT_VOTE_RECORD)
        self.assertEqual((r["record"]["display"], r["record"]["name"]), ("70,0000%", "p1"))

    def test_company_names_come_from_a_registered_namer(self):
        live.register_entity_namer("company", lambda i: f"Acme {i}")
        self.assertEqual(live.entity_name("company", 4), "Acme 4")
        live.clear_entity_namers()
        self.assertEqual(live.entity_name("company", 4), "company #4")


class PageTests(RankingsTestCase):
    def test_page_separates_live_and_historical_and_lists_all_categories(self):
        r = self.client.get("/rankings/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertLess(html.index('id="live"'), html.index('id="historical"'))
        for c in CATEGORIES:
            self.assertIn(f'id="{c.key.value}"', html)
        self.assertIn("agora", html)
        self.assertIn("já alcançado", html)

    def test_page_shows_values_and_pending_notices(self):
        self.fund(self.acct(), 12_345)
        html = self.client.get("/rankings/").content.decode()
        self.assertIn("R$ 123,45", html)
        self.assertIn("Indisponível nesta versão", html)

    def test_json_data_and_category_endpoints(self):
        self.fund(self.acct(), 500)
        d = self.client.get("/rankings/data/").json()
        self.assertEqual([c["number"] for c in d["live"]], list(range(1, 12)))
        self.assertEqual([c["number"] for c in d["historical"]], [12, 13, 14, 15])
        nw = self.client.get("/rankings/net_worth/").json()
        self.assertEqual(nw["entries"][0]["value"], 500)
        self.assertEqual(self.client.get("/rankings/net_worth_record/").json()["group"], "historical")
        self.assertEqual(self.client.get("/rankings/inexistente/").status_code, 404)

    def test_limit_parameter(self):
        for n in ("a", "b", "c"):
            self.fund(self.acct(self.make_player(n)), 1)
        self.assertEqual(len(self.client.get("/rankings/net_worth/?limit=2").json()["entries"]), 2)
        self.assertEqual(self.client.get("/rankings/net_worth/?limit=0").status_code, 404)
        self.assertEqual(self.client.get("/rankings/net_worth/?limit=x").status_code, 404)
        self.assertEqual(len(self.client.get("/rankings/net_worth/?limit=100000").json()["entries"]), 4)

    def test_page_is_public_and_read_only(self):
        self.assertEqual(self.client.post("/rankings/").status_code, 405)

    def test_reading_the_page_does_not_write_anything(self):
        self.fund(self.acct(), 500)
        self.client.get("/rankings/")
        self.assertFalse(RankingHistorico.objects.exists())
        self.assertFalse(ActivityStreak.objects.exists())


class AuditTests(RankingsTestCase):
    def test_clean_state(self):
        self.assertTrue(audit.audit_rankings()["ok"])

    def test_consistent_records_pass(self):
        from rankings import activity
        self.clk.advance(days=1)
        activity.record_action(self.player.pk, T0)
        activity.record_action(self.player.pk, T0 + DAY)
        self.fund(self.acct(), 1_000)
        records.check_net_worth_record(self.player.pk)
        records.record_presidential_result(self.player.pk, "E1", 1, 2, T0)
        rep = audit.audit_rankings()
        self.assertTrue(rep["ok"], rep)
        self.assertEqual((rep["stats"]["streaks"], rep["stats"]["records"]), (1, 3))

    def test_reports_records_behind_the_source(self):
        from rankings import activity
        activity.record_action(self.player.pk, T0)
        activity.record_action(self.player.pk, T0 + DAY)
        RankingHistorico.objects.all().delete()           # recorde perdido
        self.fund(self.acct(), 1_000)
        codes = sorted((f["code"], f["category"]) for f in audit.audit_rankings()["findings"])
        self.assertEqual(codes, [("RECORD_BEHIND_SOURCE", "active_time_record"), ("RECORD_BEHIND_SOURCE", "net_worth_record")])

    def test_reports_metadata_mismatch(self):
        records.record_presidential_result(self.player.pk, "E1", 1, 2, T0)
        RankingHistorico.objects.filter(category="president_vote_record").update(value=1)
        f = audit.audit_rankings()["findings"]
        self.assertEqual([x["code"] for x in f], ["RECORD_METADATA_MISMATCH"])

    def test_reports_unknown_category_and_bad_entity(self):
        RankingHistorico.objects.create(category="bogus", entity_type="player", entity_id=1, value=1, recorded_at=T0, updated_at=T0)
        RankingHistorico.objects.create(category="net_worth_record", entity_type="alien", entity_id=1, value=1,
                                        recorded_at=T0, updated_at=T0)
        codes = {f["code"] for f in audit.audit_rankings()["findings"]}
        self.assertTrue({"RECORD_UNKNOWN_CATEGORY", "RECORD_BAD_ENTITY_TYPE"} <= codes)

    def test_management_command(self):
        from io import StringIO
        from django.core.management import call_command
        from django.core.management.base import CommandError
        out = StringIO()
        call_command("audit_rankings", "--json", stdout=out)
        self.assertTrue(json.loads(out.getvalue())["ok"])
        RankingHistorico.objects.create(category="bogus", entity_type="player", entity_id=1, value=1, recorded_at=T0, updated_at=T0)
        with self.assertRaises(CommandError):
            call_command("audit_rankings", stdout=StringIO())
