"""Stateful test of the session and lock lifecycles (PBT-06).

U-06's Functional Design assessed this as required, and it is: "a session is
denied after logout or expiry" and "a locked account is denied even with the right
password" are claims about a state MACHINE, not about single calls. Example tests
check the transitions someone thought of; this checks random sequences of them.

The invariant is the one that matters: at every step, authenticate() succeeds if
and only if the model says the session is still valid. A session that outlives its
logout would be caught here.
"""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from security import AuthenticationFailedError
from security.identifiers import SessionId

from .support import PASSWORD, USER, build_authenticator, make_config

_LOCK_THRESHOLD = 3
_LOCK_SECONDS = 900
_TTL_SECONDS = 3600


class SessionAndLockLifecycle(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        directory = Path(tempfile.mkdtemp())
        config = make_config(
            lock_threshold=_LOCK_THRESHOLD,
            lock_duration_seconds=_LOCK_SECONDS,
            session_ttl_seconds=_TTL_SECONDS,
        )
        self.auth, _store, _hasher = build_authenticator(directory / "audit.jsonl", config)
        self.now = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)

        # model
        self.session_id: SessionId | None = None
        self.session_valid = False
        self.session_expires_at: datetime | None = None
        self.failures = 0
        self.locked_until: datetime | None = None

    def _locked(self) -> bool:
        return self.locked_until is not None and self.now < self.locked_until

    @rule()
    def login_correct(self) -> None:
        if self._locked():
            with pytest.raises(AuthenticationFailedError):
                self.auth.login(USER, PASSWORD, self.now)
            return
        session = self.auth.login(USER, PASSWORD, self.now)
        self.session_id = session.id
        self.session_valid = True
        self.session_expires_at = self.now + timedelta(seconds=_TTL_SECONDS)
        self.failures = 0
        self.locked_until = None

    @rule()
    def login_wrong(self) -> None:
        was_locked = self._locked()
        with pytest.raises(AuthenticationFailedError):
            self.auth.login(USER, "definitely-not-the-password", self.now)
        if was_locked:
            return  # a locked account does not accumulate further failures
        self.failures += 1
        if self.failures >= _LOCK_THRESHOLD:
            self.locked_until = self.now + timedelta(seconds=_LOCK_SECONDS)

    @rule()
    def logout(self) -> None:
        if self.session_id is None:
            return
        self.auth.logout(self.session_id, self.now)
        self.session_valid = False

    @rule(seconds=st.integers(min_value=1, max_value=5000))
    def advance_time(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)
        if self.session_expires_at is not None and self.now >= self.session_expires_at:
            self.session_valid = False

    @invariant()
    def session_state_matches_model(self) -> None:
        if self.session_id is None:
            return
        if self.session_valid:
            assert self.auth.authenticate(self.session_id, self.now).user_id == USER
        else:
            with pytest.raises(AuthenticationFailedError):
                self.auth.authenticate(self.session_id, self.now)


SessionAndLockLifecycle.TestCase.settings = settings(
    max_examples=20, stateful_step_count=15, deadline=None
)
TestSessionAndLockLifecycle = SessionAndLockLifecycle.TestCase
