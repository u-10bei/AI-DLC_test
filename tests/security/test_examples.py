"""Example-based tests for U-06: the gates, the lock, the audit log."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from security import (
    AppendOnlyFileAuditLog,
    AuditService,
    AuthenticationFailedError,
    AuthorizationDeniedError,
    Authorizer,
    IpAllowlist,
    IpNotAllowedError,
    Principal,
    RateLimiter,
    RateLimitExceededError,
    Role,
    SecurityConfig,
    sanitize_csv_cell,
)
from security.authorization import RUN_OPTIMIZATION
from security.identifiers import SessionId, UserId
from security.rate_limit import GENERAL, LOGIN

from .support import NOW, PASSWORD, USER, build_authenticator, make_config

# --- SEC-01 authentication (US-01, MU-03) -----------------------------------


def test_login_then_authenticate(tmp_path: Path) -> None:
    auth, _store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    session = auth.login(USER, PASSWORD, NOW)
    assert auth.authenticate(session.id, NOW).user_id == USER


def test_expired_session_is_denied(tmp_path: Path) -> None:
    auth, _store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    session = auth.login(USER, PASSWORD, NOW)
    with pytest.raises(AuthenticationFailedError):
        auth.authenticate(session.id, NOW + timedelta(seconds=3601))


def test_logout_revokes_immediately(tmp_path: Path) -> None:
    """This is why sessions are opaque server-side values, not JWTs."""
    auth, _store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    session = auth.login(USER, PASSWORD, NOW)
    auth.logout(session.id, NOW)
    with pytest.raises(AuthenticationFailedError):
        auth.authenticate(session.id, NOW)


def test_unknown_session_is_denied(tmp_path: Path) -> None:
    auth, _store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    with pytest.raises(AuthenticationFailedError):
        auth.authenticate(SessionId("never-issued"), NOW)


def test_unknown_user_and_wrong_password_are_indistinguishable(tmp_path: Path) -> None:
    """BR-SEC04: the response must not reveal whether the account exists."""
    auth, _store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    with pytest.raises(AuthenticationFailedError) as unknown:
        auth.login(UserId("NOBODY"), PASSWORD, NOW)
    with pytest.raises(AuthenticationFailedError) as wrong:
        auth.login(USER, "not-the-password", NOW)
    assert str(unknown.value) == str(wrong.value)


def test_account_locks_after_threshold_and_stays_locked_for_correct_password(
    tmp_path: Path,
) -> None:
    """MU-03: brute force is stopped, and the lock is not bypassed by finally
    guessing right."""
    auth, _store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    for _ in range(3):  # lock_threshold=3
        with pytest.raises(AuthenticationFailedError):
            auth.login(USER, "wrong", NOW)
    with pytest.raises(AuthenticationFailedError):
        auth.login(USER, PASSWORD, NOW)  # correct password, still denied


def test_lock_expires(tmp_path: Path) -> None:
    auth, _store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    for _ in range(3):
        with pytest.raises(AuthenticationFailedError):
            auth.login(USER, "wrong", NOW)
    later = NOW + timedelta(seconds=901)  # lock_duration=900
    assert auth.login(USER, PASSWORD, later).principal.user_id == USER


# --- SEC-03 IP allowlist (US-02, NFR-S10.2) ---------------------------------


def test_ip_allowlist_permits_only_the_configured_range() -> None:
    allowlist = IpAllowlist(make_config())
    assert allowlist.is_allowed("203.0.113.5") is True
    assert allowlist.is_allowed("198.51.100.1") is False


def test_unparseable_ip_is_denied() -> None:
    assert IpAllowlist(make_config()).is_allowed("not-an-ip") is False


def test_empty_allowlist_denies_everything() -> None:
    """A missing configuration must fail closed, not open (SECURITY-15)."""
    assert IpAllowlist(SecurityConfig()).is_allowed("203.0.113.5") is False


def test_ip_check_raises(tmp_path: Path) -> None:
    with pytest.raises(IpNotAllowedError):
        IpAllowlist(make_config()).check("198.51.100.1")


# --- SEC-04 rate limit (NFR-S09, MU-03) -------------------------------------


def test_login_rate_limit_is_stricter_than_general() -> None:
    limiter = RateLimiter(make_config())
    for _ in range(5):  # login_rate_limit_per_minute=5
        limiter.check("203.0.113.5", LOGIN, NOW)
    with pytest.raises(RateLimitExceededError):
        limiter.check("203.0.113.5", LOGIN, NOW)
    # the general bucket is independent and far larger
    limiter.check("203.0.113.5", GENERAL, NOW)


def test_rate_limit_window_resets() -> None:
    limiter = RateLimiter(make_config())
    for _ in range(5):
        limiter.check("203.0.113.5", LOGIN, NOW)
    limiter.check("203.0.113.5", LOGIN, NOW + timedelta(seconds=60))


# --- SEC-02 authorization (MU-01) -------------------------------------------


def _authorizer(tmp_path: Path) -> Authorizer:
    return Authorizer(AuditService(AppendOnlyFileAuditLog(tmp_path / "audit.jsonl")))


def test_coordinator_may_run_optimization(tmp_path: Path) -> None:
    principal = Principal(user_id=USER, role=Role.COORDINATOR)
    _authorizer(tmp_path).require_authorization(principal, RUN_OPTIMIZATION, NOW)


def test_unknown_action_is_denied(tmp_path: Path) -> None:
    """Deny by default: an action nobody granted is refused."""
    principal = Principal(user_id=USER, role=Role.COORDINATOR)
    with pytest.raises(AuthorizationDeniedError):
        _authorizer(tmp_path).require_authorization(principal, "DELETE_EVERYTHING", NOW)


# --- SEC-05 sanitiser (MU-02) -----------------------------------------------


def test_formula_injection_is_neutralised() -> None:
    assert sanitize_csv_cell("=SUM(A1)") == "'=SUM(A1)"
    assert sanitize_csv_cell("+1+1") == "'+1+1"
    assert sanitize_csv_cell("-2") == "'-2"
    assert sanitize_csv_cell("@import") == "'@import"


def test_ordinary_values_are_untouched() -> None:
    assert sanitize_csv_cell("山田") == "山田"
    assert sanitize_csv_cell("") == ""


# --- audit (US-03, US-04, SECURITY-03) --------------------------------------


def test_audit_log_is_json_lines_without_secrets(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    auth, _store, _hasher = build_authenticator(path)
    auth.login(USER, PASSWORD, NOW)
    with pytest.raises(AuthenticationFailedError):
        auth.login(USER, "wrong", NOW)

    content = path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    assert len(lines) == 2
    assert PASSWORD not in content  # never log a password
    assert '"action": "LOGIN_SUCCESS"' in lines[0]
    assert '"action": "AUTH_FAILURE"' in lines[1]


def test_secrets_are_redacted_in_repr(tmp_path: Path) -> None:
    auth, store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    session = auth.login(USER, PASSWORD, NOW)
    account = store.accounts[USER]
    assert "<redacted>" in repr(session)
    assert str(session.id) not in repr(session)
    assert "<redacted>" in repr(account)
    assert account.password_hash not in repr(account)
