"""Focused tests for authentication, profile ownership, and personalization."""
import re
import unittest
from unittest.mock import patch

import app as legacy
import public_site
from accounts import (AccountServiceError, AuthResult, ChildProfile, Session,
    SupabaseProfileProvider, validate_credentials)


ACCOUNT = Session("account-1", "parent@example.com", "access-token")


class FakeAuth:
    def __init__(self, account=ACCOUNT):
        self.account = account
        self.calls = []

    def current_session(self):
        return self.account

    def sign_up(self, email, password):
        self.calls.append(("signup", email))
        return AuthResult("signed_in", "ready", self.account)

    def sign_in(self, email, password):
        self.calls.append(("signin", email))
        return AuthResult("signed_in", "welcome", self.account)

    def sign_out(self):
        self.calls.append(("signout", ""))


class FakeProfiles:
    def __init__(self, profile=None):
        self.profile = profile
        self.saved = []

    def get(self, account):
        return self.profile

    def save(self, account, profile):
        self.saved.append(profile)
        self.profile = profile
        return profile


class CredentialsTests(unittest.TestCase):
    def test_credentials_are_normalized_and_password_has_bounds(self):
        self.assertEqual(validate_credentials(" Parent@Example.COM ", "long-enough-password")[0],
            "parent@example.com")
        for email, password in (("bad-email", "long-enough-password"),
                                ("parent@example.com", "short"),
                                ("parent@example.com", "x" * 129)):
            with self.subTest(email=email, length=len(password)):
                with self.assertRaises(ValueError):
                    validate_credentials(email, password)

    def test_profile_provider_rejects_cross_account_write_before_network(self):
        class NoNetwork:
            def request(self, *args, **kwargs):
                raise AssertionError("network should not be called")
        provider = SupabaseProfileProvider(NoNetwork())
        other = ChildProfile("account-2", "", "3-4", (), "")
        with self.assertRaises(AccountServiceError):
            provider.save(ACCOUNT, other)


class AccountRouteTests(unittest.TestCase):
    def setUp(self):
        legacy.app.config.update(TESTING=True, SECRET_KEY="test-secret", SESSION_COOKIE_SECURE=False)
        self.client = legacy.app.test_client()
        self.auth = FakeAuth()
        self.profiles = FakeProfiles()
        self.patches = (
            patch.object(public_site, "AUTH", self.auth),
            patch.object(public_site, "PROFILES", self.profiles),
            patch.dict(public_site.FEATURES, {"auth": True, "profile_persistence": True}),
        )
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def csrf(self, path):
        page = self.client.get(path)
        match = re.search(rb'name="csrf_token" value="([^"]+)"', page.data)
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def test_login_requires_csrf_and_uses_provider(self):
        bad = self.client.post("/login", data={"email": "parent@example.com",
            "password": "long-enough-password"})
        self.assertEqual(bad.status_code, 400)
        token = self.csrf("/login")
        response = self.client.post("/login", data={"csrf_token": token,
            "email": "Parent@Example.com", "password": "long-enough-password"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], "/dashboard")
        self.assertEqual(self.auth.calls[-1], ("signin", "Parent@Example.com"))

    def test_profile_uses_authenticated_owner_and_whitelists_choices(self):
        token = self.csrf("/profile")
        response = self.client.post("/profile", data={"csrf_token": token,
            "owner_id": "account-2", "nickname": "Lulu", "age_band": "3-4",
            "interests": ["art", "unknown", "nature"], "setting": "indoor"})
        self.assertEqual(response.status_code, 303)
        saved = self.profiles.saved[-1]
        self.assertEqual(saved.owner_id, ACCOUNT.account_id)
        self.assertEqual(saved.interests, ("art", "nature"))

    def test_dashboard_uses_saved_preferences_without_relaxing_them(self):
        self.profiles.profile = ChildProfile(ACCOUNT.account_id, "Lulu", "baby",
            ("stories",), "indoor")
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Ideas for Lulu", response.data)
        self.assertIn(b"Look, Listen, Connect", response.data)
        self.assertIn(b"Stories &amp; Animal Sounds", response.data)
        self.assertNotIn(b"A Gentle Zoo Day", response.data)


if __name__ == "__main__":
    unittest.main()
