"""SEC-04 RateLimiter (NFR-S09, MU-03, DP-04).

A fixed one-minute window keyed on (source, kind). Simple, in-memory, and adequate
for a single server with a single worker (A-07).

Known property, stated rather than hidden: a fixed window permits a burst across
its boundary -- up to twice the limit if requests cluster either side of the minute
mark. For brute-force resistance that is acceptable because the lock threshold
(5 failures) bites long before the rate limit does. Swap in a sliding window if
this ever matters (U06-H12).
"""

from __future__ import annotations

from datetime import datetime

from .config import SecurityConfig
from .exceptions import RateLimitExceededError

#: Login is rate-limited far more tightly than everything else (MU-03).
LOGIN = "login"
GENERAL = "general"

_WINDOW_SECONDS = 60


class RateLimiter:
    def __init__(self, config: SecurityConfig | None = None) -> None:
        self._config = config if config is not None else SecurityConfig()
        self._counts: dict[tuple[str, str, int], int] = {}

    def check(self, source_ip: str, kind: str, now: datetime) -> None:
        """Count this request and raise if it exceeds the limit (DP-01)."""
        window = int(now.timestamp()) // _WINDOW_SECONDS
        self._prune(window)
        key = (source_ip, kind, window)
        self._counts[key] = self._counts.get(key, 0) + 1
        if self._counts[key] > self._limit_for(kind):
            raise RateLimitExceededError(source_ip=source_ip)

    def _limit_for(self, kind: str) -> int:
        if kind == LOGIN:
            return self._config.login_rate_limit_per_minute
        return self._config.rate_limit_per_minute

    def _prune(self, current_window: int) -> None:
        stale = [key for key in self._counts if key[2] < current_window - 1]
        for key in stale:
            del self._counts[key]


__all__ = ["GENERAL", "LOGIN", "RateLimiter"]
