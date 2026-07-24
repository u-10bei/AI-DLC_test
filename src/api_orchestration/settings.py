"""W-1: build AppConfig from environment variables (NFR-M03, 12-factor).

Deployment supplies configuration through the environment; nothing operational is
hardcoded. Every variable is optional and falls back to the dataclass default, with
two deliberate exceptions to the "convenient default" habit:

  * ``AIDLC_IP_ALLOWLIST`` unset means an EMPTY allowlist, which DENIES EVERYTHING
    (SECURITY-15). A missing allowlist must fail closed.
  * ``AIDLC_TRUSTED_PROXIES`` unset means trust nobody, so the peer address is used
    verbatim. Behind a reverse proxy that denies everything — which is the safe
    direction, and the runbook calls it out as the most common deployment mistake.

Parsing is strict: a malformed number raises at startup rather than silently
falling back, because a config typo that quietly halves the session TTL is worse
than a process that refuses to boot.
"""

from __future__ import annotations

import os
from pathlib import Path

from security import SecurityConfig

from .config import AppConfig

PREFIX = "AIDLC_"


class ConfigurationError(ValueError):
    """A configuration variable is present but unusable."""


def _raw(name: str) -> str | None:
    value = os.environ.get(PREFIX + name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def _str(name: str, default: str) -> str:
    value = _raw(name)
    return default if value is None else value


def _int(name: str, default: int) -> int:
    value = _raw(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{PREFIX}{name} must be an integer, got {value!r}") from exc


def _float(name: str, default: float) -> float:
    value = _raw(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigurationError(f"{PREFIX}{name} must be a number, got {value!r}") from exc


def _tuple(name: str) -> tuple[str, ...]:
    """Comma-separated list. Unset or empty -> empty tuple (fail closed)."""
    value = _raw(name)
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _path(name: str, default: Path) -> Path:
    value = _raw(name)
    return default if value is None else Path(value)


def load_security_config_from_env() -> SecurityConfig:
    defaults = SecurityConfig()
    return SecurityConfig(
        # Empty = deny everything (SECURITY-15). Not defaulted to something permissive.
        ip_allowlist=_tuple("IP_ALLOWLIST"),
        session_ttl_seconds=_int("SESSION_TTL_SECONDS", defaults.session_ttl_seconds),
        lock_threshold=_int("LOCK_THRESHOLD", defaults.lock_threshold),
        lock_duration_seconds=_int("LOCK_DURATION_SECONDS", defaults.lock_duration_seconds),
        rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", defaults.rate_limit_per_minute),
        login_rate_limit_per_minute=_int(
            "LOGIN_RATE_LIMIT_PER_MINUTE", defaults.login_rate_limit_per_minute
        ),
        argon2_memory_kib=_int("ARGON2_MEMORY_KIB", defaults.argon2_memory_kib),
        argon2_time_cost=_int("ARGON2_TIME_COST", defaults.argon2_time_cost),
        argon2_parallelism=_int("ARGON2_PARALLELISM", defaults.argon2_parallelism),
    )


def load_config_from_env() -> AppConfig:
    """Assemble the whole application configuration from the environment."""
    defaults = AppConfig()
    return AppConfig(
        database_url=_str("DATABASE_URL", defaults.database_url),
        audit_log_path=_path("AUDIT_LOG_PATH", defaults.audit_log_path),
        security=load_security_config_from_env(),
        worker_poll_seconds=_float("WORKER_POLL_SECONDS", defaults.worker_poll_seconds),
        frontend_dist_path=_path("FRONTEND_DIST_PATH", defaults.frontend_dist_path),
        trusted_proxies=_tuple("TRUSTED_PROXIES"),
        client_ip_header=_str("CLIENT_IP_HEADER", defaults.client_ip_header),
        travel=defaults.travel,  # distance parameters stay code defaults (US-14, no UI yet)
        optimization=defaults.optimization,
    )


__all__ = ["ConfigurationError", "load_config_from_env", "load_security_config_from_env"]
