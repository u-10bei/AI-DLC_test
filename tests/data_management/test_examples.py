"""Example-based tests for U-03: schema constraints, CASCADE, transitions, CSV.

These pin the SQL-level behaviour the property tests then generalise. They run
against a real in-memory SQLite with foreign_keys=ON, so ON DELETE CASCADE and
the UNIQUE/CHECK constraints are genuinely exercised.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, insert
from sqlalchemy.exc import IntegrityError

from data_management import (
    AvailabilityService,
    CsvImportError,
    EventService,
    MasterDataService,
    repositories,
    schema,
)
from shared_kernel import (
    DataIntegrityError,
    Department,
    DepartmentId,
    Event,
    EventId,
    EventStatus,
    EventType,
    InvalidStateTransitionError,
    StaffId,
)

from .support import fresh_engine

# --- fixtures as plain builders ---------------------------------------------

_DEPT_CSV_DEP = Department(id=DepartmentId("D1"), name="総務課")
_DISTRICTS = "小学校区ID,名称,緯度,経度\nSD1,第一,35.0,139.0\nSD2,第二,35.1,139.1\n".encode()
_STAFF = (
    "職員ID,氏名,所属部署ID,職種,役職,居住小学校区ID,資格\n"
    "S1,山田,D1,事務職,一般職,SD1,防災士\n"
    "S2,鈴木,D1,技術職,管理職,SD2,\n"
).encode()
_FACILITY = "施設ID,名称,小学校区ID,必要人数,資格要件\nF1,避難所A,SD1,5,防災士:1\n".encode()


def _seed_masters(engine: Engine) -> None:
    md = MasterDataService(engine)
    md.save_departments([_DEPT_CSV_DEP])
    md.import_school_districts(_DISTRICTS)
    md.import_staff(_STAFF)
    md.import_facilities(_FACILITY)


def _event(status: EventStatus = EventStatus.DRAFT) -> Event:
    return Event(
        id=EventId("E1"),
        type=EventType.DISASTER_SHELTER_SUPPORT,
        name="訓練",
        scheduled_date=date(2026, 8, 1),
        status=status,
    )


# --- schema constraints -----------------------------------------------------


def test_distance_cache_rejects_non_canonical_key() -> None:
    engine = fresh_engine()
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(
                insert(schema.distance_cache),
                {"district_a": "SDZ", "district_b": "SDA", "great_circle_km": 1.0},
            )


def test_declaration_unique_instant_is_enforced() -> None:
    engine = fresh_engine()
    _seed_masters(engine)
    EventService(engine).create_event(_event())
    row = {
        "staff_id": "S1",
        "event_id": "E1",
        "is_available": True,
        "reason_category": None,
        "other_reason_note": None,
        "declared_at": datetime(2026, 7, 1, 0, 0, 0),
    }
    with pytest.raises(IntegrityError):
        with engine.begin() as conn:
            conn.execute(insert(schema.availability_declarations), [row, dict(row)])


# --- ON DELETE CASCADE (BR-DM10) --------------------------------------------


def test_deleting_event_cascades_declarations() -> None:
    engine = fresh_engine()
    _seed_masters(engine)
    events = EventService(engine)
    events.create_event(_event())
    avail = AvailabilityService(engine)
    decls = "職員ID,従事可否,申告日時,理由区分,その他理由\nS1,可,2026-07-01 09:00:00,,\n".encode()
    avail.import_declarations(EventId("E1"), decls)

    events.delete_event(EventId("E1"))

    assert events.get_event(EventId("E1")) is None
    assert avail.declaration_history(StaffId("S1"), EventId("E1")) == []


def test_confirmed_event_cannot_be_deleted() -> None:
    engine = fresh_engine()
    _seed_masters(engine)
    events = EventService(engine)
    events.create_event(_event())
    with engine.begin() as conn:
        repositories.update_event_status(conn, EventId("E1"), EventStatus.CONFIRMED.name)
    with pytest.raises(InvalidStateTransitionError):
        events.delete_event(EventId("E1"))


# --- event transition preconditions (BR-DM09) -------------------------------


def test_cannot_start_collecting_without_facilities() -> None:
    engine = fresh_engine()
    md = MasterDataService(engine)
    md.save_departments([_DEPT_CSV_DEP])
    md.import_school_districts(_DISTRICTS)
    md.import_staff(_STAFF)
    # deliberately NO facilities imported
    events = EventService(engine)
    events.create_event(_event())
    with pytest.raises(InvalidStateTransitionError):
        events.transition(EventId("E1"), EventStatus.COLLECTING_DECLARATIONS)


def test_transition_succeeds_with_a_facility() -> None:
    engine = fresh_engine()
    _seed_masters(engine)
    events = EventService(engine)
    events.create_event(_event())
    updated = events.transition(EventId("E1"), EventStatus.COLLECTING_DECLARATIONS)
    assert updated.status is EventStatus.COLLECTING_DECLARATIONS
    stored = events.get_event(EventId("E1"))
    assert stored is not None
    assert stored.status is EventStatus.COLLECTING_DECLARATIONS


# --- CSV import: all errors, line numbers, no PII (BR-DM02, BR-DM14) ---------


def test_import_reports_all_errors_with_line_numbers_and_no_pii() -> None:
    engine = fresh_engine()
    md = MasterDataService(engine)
    md.save_departments([_DEPT_CSV_DEP])
    md.import_school_districts(_DISTRICTS)
    bad_staff = (
        "職員ID,氏名,所属部署ID,職種,役職,居住小学校区ID,資格\n"
        "S1,山田太郎,D1,事務職,一般職,SD9,防災士\n"      # unknown district
        "S2,鈴木花子,D1,課長補佐,一般職,SD1,\n"           # unknown enum (BR-DM03)
    ).encode()
    with pytest.raises(CsvImportError) as exc_info:
        md.import_staff(bad_staff)
    errors = exc_info.value.errors
    assert {e.line for e in errors} == {2, 3}
    combined = " ".join(e.message for e in errors)
    # PII (the names in the CSV) must never appear in the error text (BR-DM14).
    assert "山田太郎" not in combined
    assert "鈴木花子" not in combined
    # nothing was persisted (fail closed)
    with engine.connect() as conn:
        assert repositories.existing_staff_ids(conn) == set()


def test_unknown_enum_value_is_rejected_not_coerced() -> None:
    engine = fresh_engine()
    md = MasterDataService(engine)
    md.save_departments([_DEPT_CSV_DEP])
    md.import_school_districts(_DISTRICTS)
    bad = (
        "職員ID,氏名,所属部署ID,職種,役職,居住小学校区ID,資格\n"
        "S1,山田,D1,宇宙飛行士,一般職,SD1,\n"
    ).encode()
    with pytest.raises(CsvImportError):
        md.import_staff(bad)


# --- formula-injection sanitiser is applied on export (BR-DM04, MU-02) -------


def test_export_applies_injected_sanitizer() -> None:
    engine = fresh_engine()
    md = MasterDataService(engine)
    md.save_departments([_DEPT_CSV_DEP])
    md.import_school_districts(_DISTRICTS)
    md.import_staff(
        "職員ID,氏名,所属部署ID,職種,役職,居住小学校区ID,資格\nS1,=SUM(A1),D1,事務職,一般職,SD1,\n".encode()
    )

    def escape(cell: str) -> str:
        return "'" + cell if cell[:1] in {"=", "+", "-", "@"} else cell

    exported = md.export_staff(sanitize=escape).decode("utf-8")
    assert "'=SUM(A1)" in exported


# --- fail closed on a corrupt DB row (BR-DM13, DP-02) -----------------------


def test_corrupt_row_raises_data_integrity_error() -> None:
    engine = fresh_engine()
    # Insert a latitude the domain would reject, bypassing validation.
    with engine.begin() as conn:
        conn.execute(
            insert(schema.school_districts),
            {"id": "SDX", "name": "壊れた", "latitude": 95.0, "longitude": 139.0},
        )
    with pytest.raises(DataIntegrityError) as exc_info:
        with engine.connect() as conn:
            repositories.find_all_school_districts(conn)
    # context carries the ID only, never a name (SECURITY-03)
    assert exc_info.value.entity_id == "SDX"
    assert "壊れた" not in str(exc_info.value.context())


def test_effective_declaration_is_the_latest() -> None:
    engine = fresh_engine()
    _seed_masters(engine)
    EventService(engine).create_event(_event())
    avail = AvailabilityService(engine)
    avail.import_declarations(
        EventId("E1"),
        "職員ID,従事可否,申告日時,理由区分,その他理由\nS1,不可,2026-07-01 09:00:00,休暇,\n".encode(),
    )
    avail.import_declarations(
        EventId("E1"),
        "職員ID,従事可否,申告日時,理由区分,その他理由\nS1,可,2026-07-05 09:00:00,,\n".encode(),
    )
    effective = avail.effective_declarations(EventId("E1"))
    s1 = [d for d in effective if d.staff_id == StaffId("S1")]
    assert len(s1) == 1
    assert s1[0].is_available is True
    assert s1[0].declared_at == datetime(2026, 7, 5, 0, 0, tzinfo=UTC)  # 09:00 JST -> 00:00 UTC
