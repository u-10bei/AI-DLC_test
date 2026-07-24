"""The static SPA mount co-exists with deny-by-default auth (U08-H4 + U08-H7).

Surfaced during Build and Test: the auth middleware guards every non-public route,
which meant the browser could not even load the SPA shell (GET / -> 401) to show the
login form. Auth must guard the API, not the static bundle. This pins that: the shell
loads, the IP gate still applies to it, and the API stays protected.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from api_orchestration import build_application
from data_management import create_all, create_db_engine

from .support import ALLOWED_IP, BASE_URL, DENIED_IP, NOW, make_config


def _harness_with_spa() -> TestClient:
    dist = Path(tempfile.mkdtemp())
    (dist / "index.html").write_text('<!doctype html><div id="root"></div>', encoding="utf-8")
    audit_dir = Path(tempfile.mkdtemp())
    config = make_config(audit_dir, frontend_dist_path=dist)
    engine = create_db_engine(config.database_url)
    create_all(engine)
    app = build_application(config, engine=engine, clock=lambda: NOW)
    return TestClient(app, base_url=BASE_URL, headers={"X-Forwarded-For": ALLOWED_IP})


def test_spa_shell_loads_without_a_session() -> None:
    """GET / serves index.html — you cannot log in if you cannot load the page."""
    client = _harness_with_spa()
    response = client.get("/")
    assert response.status_code == 200
    assert '<div id="root">' in response.text


def test_api_route_is_still_guarded_when_the_spa_is_mounted() -> None:
    """The static mount does not open a hole in the API (still 401 without a session)."""
    client = _harness_with_spa()
    assert client.get("/events/E1").status_code == 401


def test_ip_allowlist_still_applies_to_static_assets() -> None:
    dist = Path(tempfile.mkdtemp())
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    config = make_config(Path(tempfile.mkdtemp()), frontend_dist_path=dist)
    engine = create_db_engine(config.database_url)
    create_all(engine)
    app = build_application(config, engine=engine, clock=lambda: NOW)
    denied = TestClient(app, base_url=BASE_URL, headers={"X-Forwarded-For": DENIED_IP})
    assert denied.get("/").status_code == 403
