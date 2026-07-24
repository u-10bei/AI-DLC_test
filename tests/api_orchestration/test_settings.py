"""Environment-variable configuration (W-1, G-1).

The two properties worth pinning are the fail-closed ones: an unset IP allowlist
must deny everything (SECURITY-15), and unset trusted proxies must trust nobody.
A permissive default in either place is a silent security hole, so a regression
here has to break a test rather than a deployment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from api_orchestration.settings import ConfigurationError, load_config_from_env


def test_unset_environment_yields_fail_closed_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(__import__("os").environ):
        if key.startswith("AIDLC_"):
            monkeypatch.delenv(key, raising=False)

    config = load_config_from_env()

    assert config.security.ip_allowlist == ()  # deny everything (SECURITY-15)
    assert config.trusted_proxies == ()  # trust nobody
    assert config.database_url == "sqlite://"


def test_lists_are_comma_separated_and_trimmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIDLC_IP_ALLOWLIST", " 203.0.113.0/24 , 198.51.100.7 ")
    monkeypatch.setenv("AIDLC_TRUSTED_PROXIES", "127.0.0.1")

    config = load_config_from_env()

    assert config.security.ip_allowlist == ("203.0.113.0/24", "198.51.100.7")
    assert config.trusted_proxies == ("127.0.0.1",)


def test_empty_string_is_treated_as_unset_not_as_a_blank_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An exported-but-empty variable must not become a bogus allowlist entry."""
    monkeypatch.setenv("AIDLC_IP_ALLOWLIST", "   ")
    assert load_config_from_env().security.ip_allowlist == ()


def test_paths_and_numbers_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIDLC_DATABASE_URL", "sqlite:////srv/aidlc/app.db")
    monkeypatch.setenv("AIDLC_AUDIT_LOG_PATH", "/srv/aidlc/audit/current.jsonl")
    monkeypatch.setenv("AIDLC_FRONTEND_DIST_PATH", "/srv/aidlc/dist")
    monkeypatch.setenv("AIDLC_WORKER_POLL_SECONDS", "5")
    monkeypatch.setenv("AIDLC_SESSION_TTL_SECONDS", "3600")

    config = load_config_from_env()

    assert config.database_url == "sqlite:////srv/aidlc/app.db"
    assert config.audit_log_path == Path("/srv/aidlc/audit/current.jsonl")
    assert config.frontend_dist_path == Path("/srv/aidlc/dist")
    assert config.worker_poll_seconds == 5.0
    assert config.security.session_ttl_seconds == 3600


def test_a_malformed_number_fails_at_startup_rather_than_silently_defaulting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A config typo must stop the process, not halve the session TTL unnoticed."""
    monkeypatch.setenv("AIDLC_SESSION_TTL_SECONDS", "eight-hours")
    with pytest.raises(ConfigurationError):
        load_config_from_env()
