"""Example-based tests for U-07, through the real HTTP boundary."""

from __future__ import annotations

from api_orchestration import JobState, step
from api_orchestration.middleware import PUBLIC_ROUTES

from .support import (
    DECLARATIONS_CSV,
    NOW,
    USER,
    build_harness,
    login,
    seed_event,
    seed_masters,
)

# --- the security chain (US-01, US-02, DP-01) --------------------------------


def test_health_is_public() -> None:
    assert build_harness().client.get("/health").status_code == 200


def test_disallowed_source_ip_is_rejected_before_anything_else() -> None:
    """US-02 / NFR-S10.2: even /health is unreachable from outside the allowlist."""
    assert build_harness().denied_client.get("/health").status_code == 403


def test_protected_route_without_a_session_is_401() -> None:
    """DP-01: no route outside PUBLIC_ROUTES is reachable unauthenticated."""
    assert build_harness().client.get("/events/E1").status_code == 401


def test_public_routes_are_only_login_and_health() -> None:
    """U07-H11: this list is a security decision. Changing it should be deliberate."""
    assert PUBLIC_ROUTES == frozenset({("POST", "/sessions"), ("GET", "/health")})


def test_login_then_logout_revokes_immediately() -> None:
    harness = build_harness()
    client = login(harness)
    assert client.get("/events/E1").status_code in (200, 404)  # authenticated
    assert client.delete("/sessions").status_code == 204
    assert client.get("/events/E1").status_code == 401  # revoked at once


def test_bad_login_is_generic_401() -> None:
    harness = build_harness()
    response = harness.client.post("/sessions", json={"user_id": USER, "password": "wrong"})
    assert response.status_code == 401
    assert response.json() == {"message": "authentication failed"}


def test_security_headers_on_every_response() -> None:
    """SECURITY-04."""
    headers = {k.lower() for k in build_harness().client.get("/health").headers}
    for expected in (
        "content-security-policy",
        "strict-transport-security",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
    ):
        assert expected in headers


# --- error responses (SECURITY-09) -------------------------------------------


def test_invalid_body_is_422_not_500() -> None:
    client = login(build_harness())
    response = client.post(
        "/events", json={"id": "", "type": "x", "name": "n", "scheduled_date": "not-a-date"}
    )
    assert response.status_code == 422


def test_unknown_enum_label_is_rejected_not_coerced() -> None:
    """BR-DM03 surfacing through the API: an unknown type fails the request."""
    client = login(build_harness())
    response = client.post(
        "/events",
        json={"id": "E9", "type": "宇宙イベント", "name": "n", "scheduled_date": "2026-08-01"},
    )
    assert response.status_code == 400


def test_error_bodies_carry_no_internals() -> None:
    """SECURITY-09: no stack trace, path or framework version in any error."""
    harness = build_harness()
    for response in (
        harness.denied_client.get("/health"),
        harness.client.get("/events/E1"),
        harness.client.post("/sessions", json={"user_id": USER, "password": "wrong"}),
    ):
        body = response.text
        for leak in ("Traceback", "/home/", "site-packages", "fastapi", "sqlalchemy"):
            assert leak not in body


# --- CSV export sanitisation (P-API07, MU-02, U06-H3) ------------------------


def test_exported_csv_is_sanitised() -> None:
    """P-API07 guards the injection at the composition root.

    If someone deletes the `sanitize=sanitize_csv_cell` argument, U-03 keeps working,
    U-06 keeps working, and formula injection quietly comes back. Only this test
    notices.
    """
    harness = build_harness()
    seed_masters(harness)
    client = login(harness)
    # a staff name that Excel would execute
    evil = (
        "職員ID,氏名,所属部署ID,職種,役職,居住小学校区ID,資格\n"
        "S9,=SUM(A1),D1,事務職,一般職,SD1,\n"
    ).encode()
    assert client.post("/masters/staff/import", content=evil).status_code == 200

    exported = client.get("/masters/staff/export").text
    assert "'=SUM(A1)" in exported  # neutralised
    assert ",=SUM(A1)" not in exported  # never raw


def test_csv_import_errors_are_reported_with_line_numbers_and_no_pii() -> None:
    harness = build_harness()
    seed_masters(harness)
    client = login(harness)
    bad = (
        "職員ID,氏名,所属部署ID,職種,役職,居住小学校区ID,資格\n"
        "S8,山田太郎,D1,事務職,一般職,SD99,\n"
    ).encode()
    response = client.post("/masters/staff/import", content=bad)
    assert response.status_code == 400
    body = response.json()
    assert body["errors"][0]["line"] == 2
    assert "山田太郎" not in response.text  # BR-DM14


# --- optimization job flow (US-16, US-20, DP-04) -----------------------------


def test_optimization_is_a_job_not_a_blocking_call() -> None:
    harness = build_harness()
    seed_masters(harness)
    client = login(harness)
    seed_event(client)
    assert (
        client.post("/events/E1/declarations/import", content=DECLARATIONS_CSV).status_code == 200
    )

    accepted = client.post("/optimizations", json={"event_id": "E1", "department_cap_limit": 10})
    assert accepted.status_code == 202  # returns immediately
    job_id = accepted.json()["job_id"]
    assert client.get(f"/optimizations/{job_id}").json()["state"] == JobState.QUEUED.value

    # the worker does the solving, out of band
    assert step(harness.engine, harness.app_config, now=NOW) is True
    assert step(harness.engine, harness.app_config, now=NOW) is False  # queue drained

    status = client.get(f"/optimizations/{job_id}").json()
    assert status["state"] == JobState.SUCCEEDED.value
    assert len(status["assignments"]) == 2  # facility F1 needs 2


def test_sufficiency_counts_all_three_classes() -> None:
    harness = build_harness()
    seed_masters(harness)
    client = login(harness)
    seed_event(client)
    client.post("/events/E1/declarations/import", content=DECLARATIONS_CSV)
    body = client.get("/events/E1/sufficiency").json()
    assert body["available"] + body["unavailable"] + body["undeclared"] == 3


# --- manual edit validation (US-22, FR-06.3, U07-H1) -------------------------


def test_manual_edit_rejects_a_constraint_violation() -> None:
    """The check comes from U-04, not from a second implementation here."""
    harness = build_harness()
    seed_masters(harness)
    client = login(harness)
    seed_event(client)
    client.post("/events/E1/declarations/import", content=DECLARATIONS_CSV)
    client.post("/optimizations", json={"event_id": "E1", "department_cap_limit": 10})
    step(harness.engine, harness.app_config, now=NOW)

    assigned = client.get("/events/E1/assignments").json()
    assert len(assigned) == 2
    # Moving a third person in would make F1 exceed its headcount of 2 (C1).
    unassigned = ({"S1", "S2", "S3"} - {a["staff_id"] for a in assigned}).pop()
    response = client.patch(
        "/events/E1/assignments", json={"staff_id": unassigned, "facility_id": "F1"}
    )
    assert response.status_code == 400
    assert "C1" in response.text
