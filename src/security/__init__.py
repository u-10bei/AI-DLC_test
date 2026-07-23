"""U-06 security — where the SECURITY extension is actually implemented.

Authentication, authorization, network control, rate limiting, input sanitisation
and audit. Depends on U-01 alone.

Two structural guarantees, rather than conventions:

  * **U-06 cannot persist sessions itself.** The lint contract forbids sqlalchemy,
    so SessionStorePort must be injected by U-07 (DP-06). The design cannot rot.
  * **PII cannot reach the audit log.** AuditEvent has no field that could hold a
    name or a residence district, and U-06 never imports a business entity (DP-07).
    reason_category in particular has nowhere to go (U01-H22).

Every gate raises on denial, so forgetting to check one fails closed (DP-01).
"""

from __future__ import annotations

from .audit import AuditAction, AuditEvent, AuditLogPort, AuditService
from .audit_adapter import AppendOnlyFileAuditLog
from .authentication import Authenticator
from .authorization import Authorizer
from .config import SecurityConfig
from .entities import Account, AuthorizationDecision, Principal, Role, Session
from .exceptions import (
    AuthenticationFailedError,
    AuthorizationDeniedError,
    IpNotAllowedError,
    RateLimitExceededError,
    SecurityError,
)
from .hasher import Argon2PasswordHasher
from .identifiers import SessionId, UserId
from .network import IpAllowlist
from .ports import PasswordHasherPort, SessionStorePort
from .rate_limit import RateLimiter
from .sanitizer import sanitize_csv_cell

__all__ = [
    "Account",
    "AppendOnlyFileAuditLog",
    "Argon2PasswordHasher",
    "AuditAction",
    "AuditEvent",
    "AuditLogPort",
    "AuditService",
    "AuthenticationFailedError",
    "Authenticator",
    "AuthorizationDecision",
    "AuthorizationDeniedError",
    "Authorizer",
    "IpAllowlist",
    "IpNotAllowedError",
    "PasswordHasherPort",
    "Principal",
    "RateLimitExceededError",
    "RateLimiter",
    "Role",
    "SecurityConfig",
    "SecurityError",
    "Session",
    "SessionId",
    "SessionStorePort",
    "UserId",
    "sanitize_csv_cell",
]
