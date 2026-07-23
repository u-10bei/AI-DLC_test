"""Ports U-06 defines but does not implement (DP-06).

``SessionStorePort`` is the important one. U-06 depends on U-01 alone and its lint
contract forbids sqlalchemy, so U-06 *cannot* persist a session itself even if
someone tried. U-07 injects the database-backed implementation (U06-H2), writing
to U-03's sessions table (U03-H3). This is the same shape the architecture
already chose for SEC-05/MU-02, where U-07 injects the sanitiser into U-03.

``PasswordHasherPort`` is implemented inside U-06 (hasher.py) -- hashing needs no
database, so nothing is gained by pushing it out.
"""

from __future__ import annotations

from typing import Protocol

from .entities import Account, Session
from .identifiers import SessionId, UserId


class SessionStorePort(Protocol):
    """Account and session persistence. Implementation injected by U-07."""

    def find_account(self, user_id: UserId) -> Account | None: ...

    def save_account(self, account: Account) -> None:
        """Persist failure counters and lock state."""
        ...

    def save_session(self, session: Session) -> None: ...

    def find_session(self, session_id: SessionId) -> Session | None: ...

    def delete_session(self, session_id: SessionId) -> None:
        """Logout. Revocation must take effect immediately."""
        ...


class PasswordHasherPort(Protocol):
    """Adaptive password hashing (SECURITY-12)."""

    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool:
        """False on mismatch -- never raises for a wrong password."""
        ...


__all__ = ["PasswordHasherPort", "SessionStorePort"]
