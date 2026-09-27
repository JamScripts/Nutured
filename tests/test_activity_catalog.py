"""Tests for database-backed activity loading and safe fixture fallback."""
import unittest

from activity_catalog import (
    ACTIVITIES,
    FixtureCatalog,
    SupabaseCatalog,
    activity_from_row,
)


SAMPLE_ROW = {
    "id": "test-activity",
    "slug": "test-activity",
    "title": "Test Activity",
    "summary": "A test activity.",
    "image": "hero",
    "image_alt": "Test image",
    "age_min_months": 24,
    "age_max_months": 35,
    "kind": "activity",
    "tags": ["play", "rainy"],
    "interests": ["building"],
    "duration": 15,
    "setting": "indoor",
    "cost": 0,
    "cost_basis": "supplies",
    "materials": ["Large blocks"],
    "steps": ["Build something together."],
    "supervision": "Supervise throughout.",
    "currency": "USD",
    "review_status": "reviewed test fixture",
}


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self.data = data

    def json(self):
        return self.data


class FakeGateway:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return self.response


class ActivityCatalogTests(unittest.TestCase):
    def test_row_converts_lists_to_immutable_activity_tuples(self):
        result = activity_from_row(SAMPLE_ROW)

        self.assertEqual(result.id, "test-activity")
        self.assertEqual(result.tags, ("play", "rainy"))
        self.assertEqual(result.interests, ("building",))
        self.assertEqual(result.materials, ("Large blocks",))
        self.assertEqual(result.steps, ("Build something together.",))

    def test_supabase_catalog_loads_approved_rows(self):
        gateway = FakeGateway(FakeResponse(data=[SAMPLE_ROW]))

        results = SupabaseCatalog(gateway).activities()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "test-activity")

        method, path, kwargs = gateway.calls[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "/rest/v1/activities")
        self.assertEqual(kwargs["params"]["status"], "eq.approved")

    def test_empty_database_uses_fixture_fallback_during_migration(self):
        gateway = FakeGateway(FakeResponse(data=[]))

        results = SupabaseCatalog(gateway).activities()

        self.assertEqual(results, ACTIVITIES)

    def test_database_error_uses_fixture_fallback(self):
        gateway = FakeGateway(FakeResponse(status_code=503, data={}))

        results = SupabaseCatalog(
            gateway,
            fallback=FixtureCatalog(),
        ).activities()

        self.assertEqual(results, ACTIVITIES)

    def test_invalid_database_record_uses_fixture_fallback(self):
        gateway = FakeGateway(FakeResponse(data=[{"id": "incomplete"}]))

        results = SupabaseCatalog(gateway).activities()

        self.assertEqual(results, ACTIVITIES)


if __name__ == "__main__":
    unittest.main()
