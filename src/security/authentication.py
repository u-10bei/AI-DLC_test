"""SEC-01 Authenticator (US-01, MU-03, DP-01/02).

Two things here are easy to get wrong and are handled deliberately:

1. **Timing.** A generic error message does not hide whether an account exists if
   the code returns immediately when it does not. Argon2 is intentionally slow, so
   the difference is glaring. Every failure path therefore runs a verify -- against
   a dummy hash when there is no account or the account is locked (DP-02).

2. **What the caller learns.** login() raises the same generic
   AuthenticationFailedError for unknown user, wrong password and locked account
   (BR-SEC04). The real reason goes to the audit log. There is no AccountLockedError
   to accidentally surface: not distinguishing is structural, not a habit.

``now`` is a parameter, never ``datetime.now()``, so expiry and lock windows are
deterministic under test.
"""

from __future__ import annotations

import secrets
from dataclasses import replace
from datetime import datetime, timedelta

from .audit import AuditAction, AuditEvent, AuditService
from .config import SecurityConfig
from .entities import Account, Principal, Session
from .exceptions import AuthenticationFailedError
from .identifiers import SessionId, UserId
from .ports import PasswordHasherPort, SessionStorePort

#: Hashed once at construction so every "no such account" path pays the same cost
#: as a real verify (DP-02, U06-H11). Not a secret -- its only job is to take time.
_DUMMY_PASSWORD = "dummy-password-for-timing-uniformity"  # noqa: S105

_SESSION_ID_BYTES = 32  # 256 bits of CSPRNG entropy


class Authenticator:
    def __init__(
        self,
        store: SessionStorePort,
        hasher: PasswordHasherPort,
        audit: AuditService,
        config: SecurityConfig | None = None,
    ) -> None:
        self._store = store
        self._hasher = hasher
        self._audit = audit
        self._config = config if config is not None else SecurityConfig()
        self._dummy_hash = hasher.hash(_DUMMY_PASSWORD)

    # --- login ---------------------------------------------------------------

    def login(self, user_id: UserId, password: str, now: datetime) -> Session:
        """Authenticate and issue a session, or raise a generic failure."""
        account = self._store.find_account(user_id)

        if account is None:
            self._hasher.verify(self._dummy_hash, password)  # equalise timing (DP-02)
            self._record_failure_event(user_id, now, "unknown account")
            raise AuthenticationFailedError(user_id=user_id)

        if account.is_locked(now):
            self._hasher.verify(self._dummy_hash, password)  # equalise timing (DP-02)
            self._record_failure_event(user_id, now, "account locked")
            raise AuthenticationFailedError(user_id=user_id)

        if not self._hasher.verify(account.password_hash, password):
            self._store.save_account(self._after_failure(account, now))
            self._record_failure_event(user_id, now, "bad password")
            raise AuthenticationFailedError(user_id=user_id)

        self._store.save_account(replace(account, failed_attempts=0, locked_until=None))
        session = Session(
            id=SessionId(secrets.token_urlsafe(_SESSION_ID_BYTES)),
            principal=Principal(user_id=account.user_id, role=account.role),
            issued_at=now,
            expires_at=now + timedelta(seconds=self._config.session_ttl_seconds),
        )
        self._store.save_session(session)
        self._audit.record(
            AuditEvent(timestamp=now, action=AuditAction.LOGIN_SUCCESS, actor=user_id)
        )
        return session

    # --- session validation --------------------------------------------------

    def authenticate(self, session_id: SessionId, now: datetime) -> Principal:
        """Resolve a session to a Principal, or deny (US-01, deny by default)."""
        session = self._store.find_session(session_id)
        if session is None or session.is_expired(now):
            raise AuthenticationFailedError()
        return session.principal

    def logout(self, session_id: SessionId, now: datetime) -> None:
        """Revoke a session immediately (this is why sessions are not JWTs)."""
        session = self._store.find_session(session_id)
        self._store.delete_session(session_id)
        actor = session.principal.user_id if session is not None else None
        self._audit.record(AuditEvent(timestamp=now, action=AuditAction.LOGOUT, actor=actor))

    # --- internals -----------------------------------------------------------

    def _after_failure(self, account: Account, now: datetime) -> Account:
        attempts = account.failed_attempts + 1
        if attempts >= self._config.lock_threshold:
            return replace(
                account,
                failed_attempts=attempts,
                locked_until=now + timedelta(seconds=self._config.lock_duration_seconds),
            )
        return replace(account, failed_attempts=attempts)

    def _record_failure_event(self, user_id: UserId, now: datetime, detail: str) -> None:
        self._audit.record(
            AuditEvent(
                timestamp=now,
                action=AuditAction.AUTH_FAILURE,
                actor=user_id,
                detail=detail,  # the real reason lives here, not in the response
            )
        )


__all__ = ["Authenticator"]
