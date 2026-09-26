"""Supabase-backed account and one-child-profile services.

The public site remains fully usable when Supabase is not configured. Tokens are
kept in Flask's signed, HttpOnly session cookie; profile access is authorized by
the user's Supabase JWT and database row-level security.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Protocol

import requests
from flask import session as flask_session


TOKEN_KEYS = ("nurture_access_token", "nurture_refresh_token", "nurture_user_id", "nurture_user_email")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}$")


class AccountServiceError(RuntimeError):
    """Safe account-service error suitable for showing to the user."""


@dataclass(frozen=True)
class Session:
    account_id: str
    email: str
    access_token: str


@dataclass(frozen=True)
class AuthResult:
    status: str
    message: str
    session: Session | None = None


@dataclass(frozen=True)
class ChildProfile:
    owner_id: str
    nickname: str
    age_band: str
    interests: tuple[str, ...]
    setting: str


class AuthProvider(Protocol):
    def current_session(self) -> Session | None: ...
    def sign_up(self, email: str, password: str) -> AuthResult: ...
    def sign_in(self, email: str, password: str) -> AuthResult: ...
    def sign_out(self) -> None: ...


class ProfileProvider(Protocol):
    def get(self, account: Session) -> ChildProfile | None: ...
    def save(self, account: Session, profile: ChildProfile) -> ChildProfile: ...


def validate_credentials(email: str, password: str) -> tuple[str, str]:
    email = email.strip().casefold()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise ValueError("Enter a valid email address.")
    if not 10 <= len(password) <= 128:
        raise ValueError("Use a password between 10 and 128 characters.")
    return email, password


class UnavailableAuthProvider:
    def current_session(self) -> Session | None:
        return None

    def sign_up(self, email: str, password: str) -> AuthResult:
        return AuthResult("unavailable", "Accounts are not configured yet.")

    sign_in = sign_up

    def sign_out(self) -> None:
        for key in TOKEN_KEYS:
            flask_session.pop(key, None)


class UnavailableProfileProvider:
    def get(self, account: Session) -> ChildProfile | None:
        return None

    def save(self, account: Session, profile: ChildProfile) -> ChildProfile:
        raise AccountServiceError("Profiles are not configured yet.")


class SupabaseGateway:
    def __init__(self, base_url: str, anon_key: str):
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key

    def request(self, method: str, path: str, *, token: str | None = None,
                payload: dict | None = None, params: dict | None = None,
                prefer: str | None = None) -> requests.Response:
        headers = {"apikey": self.anon_key, "Content-Type": "application/json"}
        headers["Authorization"] = f"Bearer {token or self.anon_key}"
        if prefer:
            headers["Prefer"] = prefer
        try:
            return requests.request(method, self.base_url + path, headers=headers,
                json=payload, params=params, timeout=10)
        except requests.RequestException as exc:
            raise AccountServiceError("The account service is temporarily unavailable. Please try again.") from exc


class SupabaseAuthProvider:
    def __init__(self, gateway: SupabaseGateway):
        self.gateway = gateway

    @staticmethod
    def _clear() -> None:
        for key in TOKEN_KEYS:
            flask_session.pop(key, None)

    @staticmethod
    def _store(data: dict) -> Session | None:
        user = data.get("user") or {}
        access_token = data.get("access_token")
        account_id = user.get("id")
        email = user.get("email")
        if not (access_token and account_id and email):
            return None
        flask_session["nurture_access_token"] = access_token
        flask_session["nurture_refresh_token"] = data.get("refresh_token", "")
        flask_session["nurture_user_id"] = account_id
        flask_session["nurture_user_email"] = email
        flask_session.permanent = False
        return Session(account_id, email, access_token)

    def _refresh(self) -> Session | None:
        refresh_token = flask_session.get("nurture_refresh_token")
        if not refresh_token:
            self._clear()
            return None
        response = self.gateway.request("POST", "/auth/v1/token", params={"grant_type": "refresh_token"},
            payload={"refresh_token": refresh_token})
        if response.status_code != 200:
            self._clear()
            return None
        return self._store(response.json())

    def current_session(self) -> Session | None:
        token = flask_session.get("nurture_access_token")
        if not token:
            return None
        response = self.gateway.request("GET", "/auth/v1/user", token=token)
        if response.status_code == 401:
            return self._refresh()
        if response.status_code != 200:
            return None
        user = response.json()
        account_id, email = user.get("id"), user.get("email")
        if not (account_id and email):
            self._clear()
            return None
        flask_session["nurture_user_id"] = account_id
        flask_session["nurture_user_email"] = email
        return Session(account_id, email, token)

    def sign_up(self, email: str, password: str) -> AuthResult:
        email, password = validate_credentials(email, password)
        response = self.gateway.request("POST", "/auth/v1/signup", payload={"email": email, "password": password})
        data = response.json() if response.content else {}
        if response.status_code not in (200, 201):
            return AuthResult("error", "We couldn’t create that account. Check the email or try signing in.")
        account = self._store(data)
        if account:
            return AuthResult("signed_in", "Your account is ready.", account)
        return AuthResult("verification_required", "Check your email to confirm your account, then sign in.")

    def sign_in(self, email: str, password: str) -> AuthResult:
        email, password = validate_credentials(email, password)
        response = self.gateway.request("POST", "/auth/v1/token", params={"grant_type": "password"},
            payload={"email": email, "password": password})
        if response.status_code != 200:
            return AuthResult("error", "The email or password didn’t match.")
        account = self._store(response.json())
        if not account:
            return AuthResult("error", "We couldn’t start your session. Please try again.")
        return AuthResult("signed_in", "Welcome back.", account)

    def sign_out(self) -> None:
        token = flask_session.get("nurture_access_token")
        try:
            if token:
                self.gateway.request("POST", "/auth/v1/logout", token=token)
        finally:
            self._clear()


class SupabaseProfileProvider:
    def __init__(self, gateway: SupabaseGateway):
        self.gateway = gateway

    @staticmethod
    def _from_row(row: dict) -> ChildProfile:
        return ChildProfile(row["owner_id"], row.get("nickname") or "", row["age_band"],
            tuple(row.get("interests") or ()), row.get("setting") or "")

    def get(self, account: Session) -> ChildProfile | None:
        response = self.gateway.request("GET", "/rest/v1/child_profiles", token=account.access_token,
            params={"owner_id": f"eq.{account.account_id}", "select": "owner_id,nickname,age_band,interests,setting", "limit": "1"})
        if response.status_code == 401:
            raise AccountServiceError("Your session expired. Please sign in again.")
        if response.status_code != 200:
            raise AccountServiceError("We couldn’t load your preferences. Please try again.")
        rows = response.json()
        return self._from_row(rows[0]) if rows else None

    def save(self, account: Session, profile: ChildProfile) -> ChildProfile:
        if profile.owner_id != account.account_id:
            raise AccountServiceError("That profile does not belong to this account.")
        payload = {"owner_id": account.account_id, "nickname": profile.nickname or None,
            "age_band": profile.age_band, "interests": list(profile.interests),
            "setting": profile.setting or None}
        response = self.gateway.request("POST", "/rest/v1/child_profiles", token=account.access_token,
            payload=payload, params={"on_conflict": "owner_id"}, prefer="resolution=merge-duplicates,return=representation")
        if response.status_code not in (200, 201):
            raise AccountServiceError("We couldn’t save your preferences. Please try again.")
        rows = response.json()
        return self._from_row(rows[0]) if rows else profile


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "").strip()
AUTH_ENABLED = bool(SUPABASE_URL and SUPABASE_ANON_KEY and FLASK_SECRET_KEY)

if AUTH_ENABLED:
    _gateway = SupabaseGateway(SUPABASE_URL, SUPABASE_ANON_KEY)
    AUTH: AuthProvider = SupabaseAuthProvider(_gateway)
    PROFILES: ProfileProvider = SupabaseProfileProvider(_gateway)
else:
    AUTH = UnavailableAuthProvider()
    PROFILES = UnavailableProfileProvider()

FEATURES = {"auth": AUTH_ENABLED, "profile_persistence": AUTH_ENABLED,
    "kits_commerce": False, "ai": False}
