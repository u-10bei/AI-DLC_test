"""U-06's types. None of them can hold PII (DP-07).

A Principal is an account ID and a role -- no name. Nothing here imports Staff or
Event: U-06 only ever needs identifiers, and pulling a business entity in would
carry a staff member's name into the security layer, which is exactly what
SECURITY-03 and U-01's lint contracts keep out.

Account and Session redact their secrets in __repr__, the same defence U-01 gives
Staff: a careless ``logger.info("%s", session)`` must not print a session ID.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .identifiers import SessionId, UserId

REDACTED = "<redacted>"


class Role(Enum):
    """Roles that exist in the application.

    The PoC has exactly one (Q1=A): there is no ADMIN role, which is why
    SECURITY-12's MFA requirement has no subject. Account provisioning is an
    operational task performed with OS access, outside this boundary.

    Future: STAFF (self-service declarations, A-08), ADMIN (+ MFA, U06-H5).
    """

    COORDINATOR = "COORDINATOR"


@dataclass(frozen=True, slots=True)
class Principal:
    """Who is acting. An ID and a role -- never a name."""

    user_id: UserId
    role: Role


@dataclass(frozen=True, slots=True)
class Account:
    """A login account. ``password_hash`` is an Argon2id hash, never a password."""

    user_id: UserId
    password_hash: str
    role: Role
    failed_attempts: int = 0
    locked_until: datetime | None = None

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and now < self.locked_until

    def __repr__(self) -> str:
        return (
            f"Account(user_id={self.user_id!r}, role={self.role.name}, "
            f"failed_attempts={self.failed_attempts}, locked_until={self.locked_until!r}, "
            f"password_hash={REDACTED})"
        )

    __str__ = __repr__


@dataclass(frozen=True, slots=True)
class Session:
    """An issued session. The ID is an opaque CSPRNG value (never a JWT)."""

    id: SessionId
    principal: Principal
    issued_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at

    def __repr__(self) -> str:
        return (
            f"Session(id={REDACTED}, user_id={self.principal.user_id!r}, "
            f"expires_at={self.expires_at!r})"
        )

    __str__ = __repr__


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """The outcome of an authorization check, with a reason for the audit log.

    Returned (rather than raised) so a denial can be explained and recorded. The
    normal call path is ``Authorizer.require_authorization``, which raises -- see
    DP-01: nobody should be able to forget to check this.
    """

    allowed: bool
    reason: str | None = None


__all__ = [
    "REDACTED",
    "Account",
    "AuthorizationDecision",
    "Principal",
    "Role",
    "Session",
]
