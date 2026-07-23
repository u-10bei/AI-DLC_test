"""Test support for U-06.

The in-memory SessionStorePort here is a legitimate test double, not a mock of the
thing under test: the port is *designed* to be injected (U-06 cannot persist
anything itself), so supplying an in-memory implementation is exactly how the unit
is meant to be assembled. The hasher, by contrast, is the REAL Argon2 - verify(hash(p))
is one of the properties being tested, so mocking it would test nothing.

Argon2 cost factors are deliberately tiny here: production defaults are OWASP's and
would make property tests take minutes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from security import (
    Account,
    AppendOnlyFileAuditLog,
    Argon2PasswordHasher,
    AuditService,
    Authenticator,
    Role,
    SecurityConfig,
    Session,
)
from security.identifiers import SessionId, UserId

NOW = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)
USER = UserId("C001")
PASSWORD = "s3cret-password"  # noqa: S105
ALLOWED_CIDR = "203.0.113.0/24"


def make_config(**overrides: object) -> SecurityConfig:
    """Config with tiny Argon2 costs so tests run in milliseconds."""
    base: dict[str, object] = {
        "ip_allowlist": (ALLOWED_CIDR,),
        "argon2_memory_kib": 8,
        "argon2_time_cost": 1,
        "argon2_parallelism": 1,
        "lock_threshold": 3,
        "session_ttl_seconds": 3600,
    }
    base.update(overrides)
    return SecurityConfig(**base)  # type: ignore[arg-type]


class InMemorySessionStore:
    """SessionStorePort test double (the port exists to be injected)."""

    def __init__(self) -> None:
        self.accounts: dict[UserId, Account] = {}
        self.sessions: dict[SessionId, Session] = {}

    def find_account(self, user_id: UserId) -> Account | None:
        return self.accounts.get(user_id)

    def save_account(self, account: Account) -> None:
        self.accounts[account.user_id] = account

    def save_session(self, session: Session) -> None:
        self.sessions[session.id] = session

    def find_session(self, session_id: SessionId) -> Session | None:
        return self.sessions.get(session_id)

    def delete_session(self, session_id: SessionId) -> None:
        self.sessions.pop(session_id, None)


def build_authenticator(
    audit_path: Path, config: SecurityConfig | None = None
) -> tuple[Authenticator, InMemorySessionStore, Argon2PasswordHasher]:
    settings = config if config is not None else make_config()
    hasher = Argon2PasswordHasher(settings)
    store = InMemorySessionStore()
    store.save_account(
        Account(user_id=USER, password_hash=hasher.hash(PASSWORD), role=Role.COORDINATOR)
    )
    audit = AuditService(AppendOnlyFileAuditLog(audit_path))
    return Authenticator(store, hasher, audit, settings), store, hasher


__all__ = [
    "ALLOWED_CIDR",
    "NOW",
    "PASSWORD",
    "USER",
    "InMemorySessionStore",
    "build_authenticator",
    "make_config",
]
