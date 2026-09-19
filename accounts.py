"""Provider boundary: no account provider exists in the current application."""
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Session:
    account_id: str

class AuthProvider(Protocol):
    def current_session(self) -> Session | None: ...

class UnavailableAuthProvider:
    def current_session(self) -> Session | None:
        return None

AUTH = UnavailableAuthProvider()
FEATURES = {"auth": False, "profile_persistence": False, "kits_commerce": False, "ai": False}
# Availability is about the new public experience. Legacy advisor code is kept
# separately; presence of an OpenAI key never enables this milestone's agent.
