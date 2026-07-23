"""LC-05 the composition root — the one place that knows every unit (DP-06).

Explicit hand-wiring, no DI container: one extra dependency buys nothing that this
function does not already say more plainly.

Two injections here are not conveniences but the load-bearing consequences of other
units' lint contracts:

  * **SqlSessionStore -> Authenticator** (U06-H2). U-06 is forbidden sqlalchemy, so
    it cannot persist a session. This is where the capability is supplied.
  * **sanitize_csv_cell -> CSV export** (U06-H3, MU-02). U-03 and U-05 are forbidden
    from importing U-06, so the sanitiser cannot reach them any other way. Forget
    this line and formula injection is live — which is why P-API07 tests it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from fastapi import FastAPI
from sqlalchemy import Engine

from data_management import (
    AvailabilityService,
    EventService,
    MasterDataService,
    create_all,
    create_db_engine,
)
from security import (
    AppendOnlyFileAuditLog,
    Argon2PasswordHasher,
    AuditService,
    Authenticator,
    Authorizer,
    IpAllowlist,
    RateLimiter,
    sanitize_csv_cell,
)

from .config import AppConfig
from .errors import register_exception_handlers
from .middleware import register_middleware
from .routers import build_router
from .services import Services
from .session_store import SqlSessionStore


def build_services(
    config: AppConfig,
    *,
    engine: Engine | None = None,
    clock: Callable[[], datetime] | None = None,
) -> Services:
    db = engine if engine is not None else create_db_engine(config.database_url)
    hasher = Argon2PasswordHasher(config.security)
    audit = AuditService(AppendOnlyFileAuditLog(config.audit_log_path))
    session_store = SqlSessionStore(db)  # U06-H2: the capability U-06 cannot have
    master = MasterDataService(db)

    return Services(
        engine=db,
        config=config,
        authenticator=Authenticator(session_store, hasher, audit, config.security),
        authorizer=Authorizer(audit),
        audit=audit,
        events=EventService(db),
        master=master,
        availability=AvailabilityService(db),
        # U06-H3 / MU-02: the sanitiser reaches U-03 only through these arguments.
        # Every master export goes through it, not just staff — P-API07's guarantee
        # must hold for facilities and school districts too (U08-H1).
        export_staff_csv=lambda: master.export_staff(sanitize=sanitize_csv_cell),
        export_facilities_csv=lambda: master.export_facilities(sanitize=sanitize_csv_cell),
        export_districts_csv=lambda: master.export_school_districts(sanitize=sanitize_csv_cell),
        clock=clock if clock is not None else (lambda: datetime.now(UTC)),
    )


def build_application(
    config: AppConfig,
    *,
    engine: Engine | None = None,
    clock: Callable[[], datetime] | None = None,
    create_schema: bool = False,
) -> FastAPI:
    """Assemble the API process (LC-01)."""
    services = build_services(config, engine=engine, clock=clock)
    if create_schema:
        create_all(services.engine)

    app = FastAPI(title="居住地考慮型 従事者割当最適化システム", version="0.1.0")
    register_exception_handlers(app)
    register_middleware(
        app,
        ip_allowlist=IpAllowlist(config.security),
        rate_limiter=RateLimiter(config.security),
        authenticator=services.authenticator,
        trusted_proxies=config.trusted_proxies,
        client_ip_header=config.client_ip_header,
        clock=services.clock,  # one clock for routes AND middleware (session expiry)
    )
    app.include_router(build_router(services))
    _mount_frontend(app, config)
    app.state.services = services  # the worker/tests reach the same wiring
    return app


def _mount_frontend(app: FastAPI, config: AppConfig) -> None:
    """Serve the built SPA if it exists (U08-H4).

    The API routes are registered first and win for their own paths; this catch-all
    mount only handles everything else (the SPA and its assets, html=True falls back
    to index.html for client-side routes). Guarded on directory existence so tests
    and an unbuilt checkout never touch it.
    """
    dist = config.frontend_dist_path
    if not dist.is_dir():
        return
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")


__all__ = ["build_application", "build_services"]
