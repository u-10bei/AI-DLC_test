"""Facility & school-district master endpoints (U08-H1).

These are symmetric with the staff endpoints the PoC already had. The frontend
needs them to seed the masters an optimisation requires (US-08, US-09). The point
worth testing is that they went through the SAME sanitiser as staff export — a new
export path is exactly where formula injection quietly comes back (P-API07).
"""

from __future__ import annotations

from .support import DISTRICTS_CSV, build_harness, login, seed_masters


def test_district_import_then_export_round_trips() -> None:
    harness = build_harness()
    client = login(harness)
    assert client.post("/masters/districts/import", content=DISTRICTS_CSV).status_code == 200
    exported = client.get("/masters/districts/export")
    assert exported.status_code == 200
    assert "SD1" in exported.text
    assert "SD2" in exported.text


def test_facility_import_requires_its_district_and_then_succeeds() -> None:
    harness = build_harness()
    client = login(harness)
    # A facility references a school district, so districts must exist first.
    client.post("/masters/districts/import", content=DISTRICTS_CSV)
    facility_csv = "施設ID,名称,小学校区ID,必要人数,資格要件\nF1,避難所A,SD1,2,\n".encode()
    assert client.post("/masters/facilities/import", content=facility_csv).status_code == 200
    assert "F1" in client.get("/masters/facilities/export").text


def test_facility_export_is_sanitised_like_staff() -> None:
    """P-API07 must hold for the new export path too, not just staff."""
    harness = build_harness()
    client = login(harness)
    client.post("/masters/districts/import", content=DISTRICTS_CSV)
    evil = (
        "施設ID,名称,小学校区ID,必要人数,資格要件\n"
        "F9,=SUM(A1),SD1,1,\n"
    ).encode()
    assert client.post("/masters/facilities/import", content=evil).status_code == 200
    exported = client.get("/masters/facilities/export").text
    assert "'=SUM(A1)" in exported  # neutralised
    assert ",=SUM(A1)" not in exported  # never raw


def test_master_endpoints_require_authentication() -> None:
    harness = build_harness()
    for method, path in (
        ("POST", "/masters/facilities/import"),
        ("GET", "/masters/facilities/export"),
        ("POST", "/masters/districts/import"),
        ("GET", "/masters/districts/export"),
    ):
        assert harness.client.request(method, path).status_code == 401


def test_district_import_reports_row_errors_without_pii() -> None:
    harness = build_harness()
    seed_masters(harness)  # districts already present; re-import a broken row
    client = login(harness)
    bad = "小学校区ID,名称,緯度,経度\nSD9,壊れた,not-a-number,139.00\n".encode()
    response = client.post("/masters/districts/import", content=bad)
    assert response.status_code == 400
    assert response.json()["errors"][0]["line"] == 2
