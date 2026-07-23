"""Application configuration (NFR-M03: nothing here is hardcoded elsewhere)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from security import SecurityConfig
from shared_kernel import ObjectiveWeights, OptimizationParameters, TravelParameters


@dataclass(frozen=True)
class AppConfig:
    """Everything the composition root needs to build the application."""

    database_url: str = "sqlite://"
    audit_log_path: Path = field(default_factory=lambda: Path("audit/current.jsonl"))
    security: SecurityConfig = field(default_factory=SecurityConfig)

    #: Worker polling interval (NFR Req Q2=A).
    worker_poll_seconds: float = 2.0

    #: Built frontend bundle to serve as static assets (U08-H4). Mounted ONLY if the
    #: directory exists, so tests and an unbuilt checkout are unaffected. Serving the
    #: bundle from this process does not violate NFR-M05: the frontend still talks to
    #: the backend over REST; only its static files ride along on the same server (A-07).
    frontend_dist_path: Path = field(default_factory=lambda: Path("src/frontend/dist"))

    #: Direct peers whose forwarded-for header may be believed.
    #:
    #: The app sits behind the existing exposure platform (TLS termination, WAF -
    #: shared-infrastructure.md 1.2), so request.client.host is the PROXY's address,
    #: not the municipal egress address NFR-S10.2 wants to allowlist. The real client
    #: arrives in X-Forwarded-For.
    #:
    #: But believing that header unconditionally would let anyone spoof their source
    #: and walk straight through the allowlist. So it is believed ONLY when the direct
    #: peer is a proxy we listed here. Empty (the default) means: trust nobody, use the
    #: peer address. Fail closed either way (SECURITY-15).
    trusted_proxies: tuple[str, ...] = ()
    client_ip_header: str = "x-forwarded-for"

    #: Defaults a coordinator can override per request (US-14, FR-04.2).
    travel: TravelParameters = field(default_factory=TravelParameters)
    optimization: OptimizationParameters = field(
        default_factory=lambda: OptimizationParameters(
            weights=ObjectiveWeights(travel_time=1.0, travel_cost=1.0, inequity=0.5)
        )
    )


__all__ = ["AppConfig"]
