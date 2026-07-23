"""U-07 api-orchestration — the integration point.

The only unit that knows every other one, and the only one permitted Pydantic and
FastAPI. It has no business logic of its own: it exposes U-03/U-04/U-05 over HTTP
and puts U-06's gates in front of them.

Two structural notes worth keeping in view:

  * **Authentication is middleware, not a per-route dependency** (DP-01). A new
    route is protected by default; forgetting something yields a 401 rather than a
    silently public endpoint.
  * **SqlSessionStore lives here** because U-06's lint contract forbids sqlalchemy.
    The contract decided the placement, not taste.

The worker runs the solve OUTSIDE any write transaction (U07-H13): SQLite is a
single writer and a 300-second write transaction would stall the API process.
"""

from __future__ import annotations

from .composition import build_application, build_services
from .config import AppConfig
from .identifiers import JobId
from .jobs import TERMINAL_STATES, JobState, OptimizationJob, ReoptimizationMode
from .middleware import PUBLIC_ROUTES, SESSION_COOKIE
from .services import Services
from .session_store import SqlSessionStore
from .worker import run_forever, step

__all__ = [
    "PUBLIC_ROUTES",
    "SESSION_COOKIE",
    "TERMINAL_STATES",
    "AppConfig",
    "JobId",
    "JobState",
    "OptimizationJob",
    "ReoptimizationMode",
    "Services",
    "SqlSessionStore",
    "build_application",
    "build_services",
    "run_forever",
    "step",
]
