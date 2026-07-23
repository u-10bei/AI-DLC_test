"""Property-based tests for U-06 (P-SEC01..09).

The hasher is the REAL Argon2 (with tiny cost factors): verify(hash(p)) is the
property, so a mock would be testing itself.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from security import (
    Argon2PasswordHasher,
    AuthenticationFailedError,
    IpAllowlist,
    RateLimiter,
    RateLimitExceededError,
    SecurityConfig,
    sanitize_csv_cell,
)
from security.audit import AuditAction, AuditEvent
from security.identifiers import SessionId, UserId
from security.rate_limit import LOGIN
from security.sanitizer import DANGEROUS_PREFIXES

from .support import NOW, PASSWORD, USER, build_authenticator, make_config

_SETTINGS = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

_passwords = st.text(min_size=1, max_size=40)
_cells = st.text(max_size=40)


# --- P-SEC08: hashing round-trip --------------------------------------------


@settings(max_examples=25, deadline=None)
@given(_passwords)
def test_hash_verify_round_trip(password: str) -> None:
    hasher = Argon2PasswordHasher(make_config())
    digest = hasher.hash(password)
    assert hasher.verify(digest, password) is True
    assert digest != password  # never stored in the clear


@settings(max_examples=25, deadline=None)
@given(_passwords, _passwords)
def test_wrong_password_never_verifies(password: str, other: str) -> None:
    hasher = Argon2PasswordHasher(make_config())
    digest = hasher.hash(password)
    if other != password:
        assert hasher.verify(digest, other) is False


# --- P-SEC05 / P-SEC06: sanitiser -------------------------------------------


@given(_cells)
def test_sanitised_cell_never_starts_with_a_formula_character(cell: str) -> None:
    """P-SEC05: whatever goes in, the result cannot be read as a formula."""
    assert sanitize_csv_cell(cell)[:1] not in DANGEROUS_PREFIXES


@given(_cells)
def test_safe_cells_are_unchanged(cell: str) -> None:
    """P-SEC06: the sanitiser is a fixed point on values that were never dangerous."""
    if cell[:1] not in DANGEROUS_PREFIXES:
        assert sanitize_csv_cell(cell) == cell


# --- P-SEC02: IP allowlist --------------------------------------------------


@given(st.integers(min_value=0, max_value=255), st.integers(min_value=0, max_value=255))
def test_only_the_configured_range_is_allowed(third: int, fourth: int) -> None:
    """Allowlist is 203.0.113.0/24: only the matching /24 may pass."""
    allowlist = IpAllowlist(make_config())
    ip = f"203.0.{third}.{fourth}"
    assert allowlist.is_allowed(ip) is (third == 113)


@given(st.text(max_size=20))
def test_garbage_source_is_never_allowed(garbage: str) -> None:
    assert IpAllowlist(make_config()).is_allowed(garbage) is False


@given(st.integers(min_value=0, max_value=255), st.integers(min_value=0, max_value=255))
def test_empty_allowlist_denies_every_address(third: int, fourth: int) -> None:
    """P-SEC02 / SECURITY-15: an unset allowlist is not an open door."""
    assert IpAllowlist(SecurityConfig()).is_allowed(f"203.0.{third}.{fourth}") is False


# --- P-SEC09: rate limit ----------------------------------------------------


@given(st.integers(min_value=1, max_value=15))
def test_requests_beyond_the_limit_are_always_rejected(count: int) -> None:
    limiter = RateLimiter(make_config())
    limit = 5  # login_rate_limit_per_minute
    rejected = 0
    for _ in range(count):
        try:
            limiter.check("203.0.113.5", LOGIN, NOW)
        except RateLimitExceededError:
            rejected += 1
    assert rejected == max(0, count - limit)


# --- P-SEC04: audit events cannot carry PII ---------------------------------


@given(
    st.sampled_from(list(AuditAction)),
    st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=6),
)
def test_audit_json_contains_only_declared_keys(action: AuditAction, actor: str) -> None:
    """P-SEC04: the serialised event has no field that could hold a name.

    AuditEvent has no PII-capable attribute at all (DP-07), so this checks the
    serialisation does not invent one.
    """
    event = AuditEvent(timestamp=NOW, action=action, actor=UserId(actor))
    record = json.loads(event.to_json_line())
    allowed_keys = {
        "ts",
        "action",
        "actor",
        "event_id",
        "staff_id",
        "facility_id",
        "source_ip",
        "detail",
        "before",
        "after",
    }
    assert set(record) <= allowed_keys
    assert "name" not in record
    assert "reason_category" not in record  # U01-H22


# --- P-SEC01 / P-SEC03: deny by default -------------------------------------


@_SETTINGS
@given(st.text(min_size=1, max_size=30))
def test_unknown_session_id_is_always_denied(tmp_path: Path, session_id: str) -> None:
    """P-SEC01: only an issued session authenticates."""
    auth, _store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    with pytest.raises(AuthenticationFailedError):
        auth.authenticate(SessionId(session_id), NOW)


@_SETTINGS
@given(st.integers(min_value=3601, max_value=100_000))
def test_session_is_denied_after_expiry(tmp_path: Path, offset_seconds: int) -> None:
    """P-SEC03: past the TTL, no session is valid."""
    auth, _store, _hasher = build_authenticator(tmp_path / "audit.jsonl")
    session = auth.login(USER, PASSWORD, NOW)
    with pytest.raises(AuthenticationFailedError):
        auth.authenticate(session.id, NOW + timedelta(seconds=offset_seconds))
