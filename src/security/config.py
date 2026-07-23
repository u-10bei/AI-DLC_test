"""Security configuration — a frozen value, not a Protocol (NFR Design Q5).

Configuration is data with no behaviour, so a dataclass says what a Protocol
would only obscure. Every knob here is externalised rather than hardcoded
(NFR-M03): the IP allowlist above all, but also the session TTL, the lock
threshold and the rate limits.

Note the default ``ip_allowlist`` is EMPTY, which denies everything. That is
deliberate: a missing or unset allowlist must fail closed, not fail open
(SECURITY-15).
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: OWASP's recommended Argon2id parameters (m=19 MiB, t=2, p=1).
DEFAULT_ARGON2_MEMORY_KIB = 19_456
DEFAULT_ARGON2_TIME_COST = 2
DEFAULT_ARGON2_PARALLELISM = 1


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    """Externalised security knobs (NFR-M03)."""

    #: CIDR strings for the municipal egress addresses (NFR-S10.2).
    #: EMPTY MEANS DENY EVERYTHING - an unset allowlist must not open the door.
    ip_allowlist: tuple[str, ...] = field(default=())

    session_ttl_seconds: int = 28_800  # 8 hours, absolute (a working day)
    lock_threshold: int = 5  # consecutive failures before locking (MU-03)
    lock_duration_seconds: int = 900  # 15 minutes
    rate_limit_per_minute: int = 60  # general endpoints
    login_rate_limit_per_minute: int = 5  # stricter: brute force (MU-03)

    argon2_memory_kib: int = DEFAULT_ARGON2_MEMORY_KIB
    argon2_time_cost: int = DEFAULT_ARGON2_TIME_COST
    argon2_parallelism: int = DEFAULT_ARGON2_PARALLELISM


__all__ = [
    "DEFAULT_ARGON2_MEMORY_KIB",
    "DEFAULT_ARGON2_PARALLELISM",
    "DEFAULT_ARGON2_TIME_COST",
    "SecurityConfig",
]
