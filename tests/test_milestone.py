"""Focused discovery, unavailable-auth boundaries, and preserved route checks.

Run: python -m unittest discover -s tests -v
No external model requests, credentials, or writes to real event/lead stores.
"""
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
from werkzeug.datastructures import MultiDict

with patch.dict(os.environ):
    os.environ.pop("OPENAI_API_KEY", None)
    import app as legacy

from activity_catalog import ACTIVITIES
from discovery import SearchPreferences, filter_activities, parse_preferences, preference_url

class FilteringTests(unittest.TestCase):
    def test_default_returns_entire_catalog(self):
        self.assertEqual(filter_activities(ACTIVITIES, SearchPreferences()), ACTIVITIES)

    def test_combined_groups_and_multiple_interests_or(self):
        p = SearchPreferences(age="3-4", kind="activity", interests=("art", "stories"), time="30", budget="10", setting="indoor", category="rainy")
        self.assertEqual({a.id for a in filter_activities(ACTIVITIES, p)}, {"little-animal-safari", "colorful-brush-play", "animal-story-time", "birthday-story-circle"})

    def test_age_overlap_includes_spanning_activity(self):
        results = filter_activities(ACTIVITIES, SearchPreferences(age="baby"))
        self.assertEqual({a.id for a in results}, {"baby-look-and-listen", "animal-story-time"})

    def test_age_overlap_inclusive_edges(self):
        a = replace(ACTIVITIES[0], age_min_months=35, age_max_months=36)
        self.assertEqual(filter_activities((a,), SearchPreferences(age="1-2")), (a,))
        self.assertEqual(filter_activities((a,), SearchPreferences(age="3-4")), (a,))

    def test_time_and_budget_are_inclusive_maximums(self):
        p = SearchPreferences(time="15", budget="0")
        self.assertEqual({a.id for a in filter_activities(ACTIVITIES,p)}, {"animal-story-time", "rainy-day-rhythm", "baby-look-and-listen"})

    def test_keyword_casefolds_title_summary_and_tags(self):
        for word in ("SAFARI", "tiny animal world", "rainy"):
            self.assertIn(ACTIVITIES[0], filter_activities(ACTIVITIES, SearchPreferences(q=word)))

    def test_no_results_never_relaxes_age(self):
        self.assertEqual(filter_activities(ACTIVITIES, SearchPreferences(age="baby", kind="outing")), ())

    def test_query_roundtrip_and_repeated_interests(self):
        p = SearchPreferences(q="animals & art", age="3-4", interests=("art","nature"), budget="0", submitted=True)
        query = parse_qs(urlsplit(preference_url(p)).query)
        args = MultiDict((key,value) for key,values in query.items() for value in values)
        self.assertEqual(parse_preferences(args),p)

    def test_unknown_values_and_private_fields_not_serialized(self):
        p = parse_preferences(MultiDict({"age":"invalid", "time":"-20", "budget":"NaN", "child_name":"Private", "birth_date":"2020-01-01", "owner_id":"secret"}))
        self.assertEqual(p,SearchPreferences())
        self.assertEqual(preference_url(p),"/#just-for-you")

    def test_duplicate_interests_deduplicated(self):
        p = parse_preferences(MultiDict([("interests","art"),("interests","art"),("interests","unknown")]))
        self.assertEqual(p.interests,("art",))

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.client = legacy.app.test_client()
        self.temp = tempfile.TemporaryDirectory()
        self.events = patch.object(legacy,"EVENT_LOG_PATH",str(Path(self.temp.name)/"events.jsonl"))
        self.leads = patch.object(legacy,"LEAD_LOG_PATH",str(Path(self.temp.name)/"leads.jsonl"))
        self.events.start(); self.leads.start()

    def tearDown(self):
        self.events.stop(); self.leads.stop(); self.temp.cleanup()

    def test_home_guest_and_submitted_copy(self):
        self.assertIn(b"Choose a few preferences",self.client.get("/").data)
        response = self.client.get("/?age=baby&kind=outing&find=1")
        self.assertIn(b"0 ideas found",response.data)
        self.assertIn(b"Based on your selected preferences",response.data)

    def test_all_activities_have_detail_pages_and_local_photos(self):
        for activity in ACTIVITIES:
            with self.subTest(activity=activity.id):
                page=self.client.get(f"/activities/{activity.slug}")
                self.assertEqual(page.status_code,200)
                self.assertIn(b"What you",page.data)
                self.assertIn(b"not professionally reviewed",page.data)
                with self.client.get(f"/static/images/{activity.image}.jpg") as image:
                    self.assertEqual(image.status_code,200)

    def test_search_escapes_html(self):
        response=self.client.get("/explore",query_string={"q":'<script>alert("x")</script>'})
        self.assertNotIn(b'<script>alert',response.data)
        self.assertIn(b'&lt;script&gt;',response.data)

    def test_auth_unavailable_no_password_collection_or_session(self):
        for route in ("/login","/get-started"):
            response=self.client.get(route)
            self.assertEqual(response.status_code,200)
            self.assertIn(b"Accounts are coming soon",response.data)
            self.assertNotIn(b'type="password"',response.data)
            self.assertNotIn("Set-Cookie",response.headers)
            self.assertEqual(self.client.post(route,data={"password":"not-a-real-password"}).status_code,405)

    def test_dashboard_denied_with_forged_auth_indicators(self):
        self.client.set_cookie("session","fake-account")
        for route in ("/dashboard", "/dashboard?authenticated=true&account_id=other", "/dashboard?preview=1"):
            self.assertEqual(self.client.get(route).status_code,401)

    def test_dev_preview_requires_debug_and_explicit_config(self):
        for debug, enabled, expected in ((False,False,404),(True,False,404),(False,True,404),(True,True,200)):
            with patch.dict(legacy.app.config,{"DEBUG":debug,"NURTURE_DEV_PREVIEW":enabled}):
                response=self.client.get("/dev/dashboard")
                self.assertEqual(response.status_code,expected)
                if expected == 200:
                    self.assertIn(b"Development fixture preview",response.data)

    def test_safe_auth_entry_ignores_external_redirect(self):
        response=self.client.get("/login?next=https://example.com")
        self.assertEqual(response.status_code,200)
        self.assertNotIn(b"https://example.com",response.data)
        self.assertNotIn("Location",response.headers)

    def test_new_public_discovery_does_not_call_legacy_model_or_log(self):
        with patch.object(legacy,"get_nurture_agent_response",side_effect=AssertionError("Unexpected model call")), patch.object(legacy,"append_jsonl",side_effect=AssertionError("Unexpected log")):
            self.assertEqual(self.client.get("/?q=animals&find=1").status_code,200)

    def test_legacy_root_post_and_advisor_and_guides_preserved(self):
        self.assertEqual(self.client.post("/",data={}).status_code,200)
        self.assertEqual(self.client.get("/legacy/advisor").status_code,200)
        self.assertEqual(self.client.get("/guides/best-toys-for-spoon-practice").status_code,200)
        self.assertEqual(self.client.get("/guides/missing").status_code,302)

    def test_legacy_events_and_affiliate_redirect_preserved(self):
        self.assertEqual(self.client.post("/event",json={"action":"test","title":"fixture"}).status_code,200)
        response=self.client.get("/go",query_string={"url":"https://www.amazon.com/dp/example","title":"fixture"})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.headers['Location'],"https://www.amazon.com/dp/example")
        self.assertEqual(self.client.get("/go?url=https://example.com").headers["Location"],"/")

    def test_unknown_activity_returns_404(self):
        self.assertEqual(self.client.get("/activities/not-here").status_code,404)

if __name__ == "__main__": unittest.main()
