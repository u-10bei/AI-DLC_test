"""Property-based tests for U-03 (PBT-01..05).

  INV-10a  CSV export -> import round-trips the master data.
  INV-10b  distance-cache round-trip: put then get returns the stored value.
  P-DM01   CSV import is atomic: one bad row leaves the DB unchanged.
  P-DM02   the effective declaration is exactly the latest one.
  P-DM03   sufficiency's three classes partition the whole staff master.
  P-DM04   the cache key is canonical: get(a, b) == get(b, a).
  P-DM05   the mappers round-trip: row_to(to_row(x)) == x.

Every DB-touching example runs against its own fresh in-memory database.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from operator import attrgetter
from typing import TypeVar

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from data_management import (
    AvailabilityService,
    CsvImportError,
    EventService,
    MasterDataService,
    mappers,
    repositories,
)
from data_management.csv_codec import serialize_csv
from data_management.services import (
    _DECLARATION_COLUMNS,
    _STAFF_COLUMNS,
)
from distance_cost import compute_district_distance_matrix
from shared_kernel import (
    AvailabilityDeclaration,
    Department,
    Event,
    EventId,
    EventType,
    SchoolDistrict,
    Staff,
    StaffId,
)
from tests.shared_kernel.generators import (
    gen_availability_declaration,
    gen_department,
    gen_event,
    gen_school_district,
    gen_staff,
)

from .generators import Dataset, gen_master_dataset
from .support import fresh_engine, seed_masters

_DB_SETTINGS = settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.data_too_large],
)


# --- P-DM05: mapper round-trips (pure) --------------------------------------


@given(gen_department())
def test_department_mapper_round_trip(department: Department) -> None:
    assert mappers.row_to_department(mappers.department_to_row(department)) == department


@given(gen_school_district())
def test_school_district_mapper_round_trip(district: SchoolDistrict) -> None:
    assert (
        mappers.row_to_school_district(mappers.school_district_to_row(district)) == district
    )


@given(gen_staff())
def test_staff_mapper_round_trip(member: Staff) -> None:
    row = mappers.staff_to_row(member)
    assert mappers.row_to_staff(row, member.qualifications) == member


@given(gen_event())
def test_event_mapper_round_trip(event: Event) -> None:
    assert mappers.row_to_event(mappers.event_to_row(event)) == event


@given(gen_availability_declaration())
def test_declaration_mapper_round_trip(declaration: AvailabilityDeclaration) -> None:
    row = mappers.declaration_to_row(declaration, declaration.event_id)
    assert mappers.row_to_declaration(row) == declaration


# --- INV-10a: CSV export -> import round-trips masters -----------------------


@_DB_SETTINGS
@given(gen_master_dataset())
def test_csv_round_trip_preserves_masters(dataset: Dataset) -> None:
    source = fresh_engine()
    seed_masters(source, dataset)
    md_source = MasterDataService(source)
    districts_csv = md_source.export_school_districts()
    staff_csv = md_source.export_staff()
    facilities_csv = md_source.export_facilities()

    target = fresh_engine()
    md_target = MasterDataService(target)
    md_target.save_departments(dataset.departments)
    md_target.import_school_districts(districts_csv)
    md_target.import_staff(staff_csv)
    md_target.import_facilities(facilities_csv)

    with source.connect() as a, target.connect() as b:
        assert _by_id(repositories.find_all_school_districts(a)) == _by_id(
            repositories.find_all_school_districts(b)
        )
        assert _by_id(repositories.find_all_staff(a)) == _by_id(repositories.find_all_staff(b))
        assert _by_id(repositories.find_all_facilities(a)) == _by_id(
            repositories.find_all_facilities(b)
        )


# --- INV-10b / P-DM04: distance cache round-trip and key symmetry -----------


@_DB_SETTINGS
@given(st.lists(gen_school_district(), min_size=1, max_size=6, unique_by=lambda d: d.id))
def test_distance_cache_round_trip_and_symmetry(districts: list[SchoolDistrict]) -> None:
    engine = fresh_engine()
    entries = compute_district_distance_matrix(districts)
    with engine.begin() as conn:
        cache = repositories.SqlDistanceCache(conn)
        cache.put_distances(entries)
    with engine.connect() as conn:
        cache = repositories.SqlDistanceCache(conn)
        for entry in entries:
            stored = cache.get_distance(entry.district_a, entry.district_b)
            assert stored == entry.great_circle_km  # INV-10b
            # P-DM04: symmetric lookup returns the same value
            assert cache.get_distance(entry.district_b, entry.district_a) == stored


# --- P-DM01: import atomicity -----------------------------------------------


@_DB_SETTINGS
@given(gen_master_dataset())
def test_import_is_atomic_on_error(dataset: Dataset) -> None:
    engine = fresh_engine()
    md = MasterDataService(engine)
    md.save_departments(dataset.departments)
    md.import_school_districts(md_export_districts(dataset))

    with engine.connect() as conn:
        before = repositories.existing_staff_ids(conn)

    # A CSV with one perfectly valid new row and one row referencing a district
    # that does not exist. The whole import must roll back (BR-DM01).
    good_district = str(dataset.districts[0].id)
    good_dept = str(dataset.departments[0].id)
    rows = [
        ["SNEW", "新規", good_dept, "事務職", "一般職", good_district, ""],
        ["SBAD", "不正", good_dept, "事務職", "一般職", "SD_DOES_NOT_EXIST", ""],
    ]
    bad_csv = serialize_csv(_STAFF_COLUMNS, rows)

    try:
        md.import_staff(bad_csv)
        raise AssertionError("import should have raised CsvImportError")
    except CsvImportError:
        pass

    with engine.connect() as conn:
        after = repositories.existing_staff_ids(conn)
    assert after == before
    assert "SNEW" not in after


# --- P-DM02: the effective declaration is the latest ------------------------


@_DB_SETTINGS
@given(gen_master_dataset(), st.integers(min_value=1, max_value=5))
def test_effective_declaration_is_latest(dataset: Dataset, revisions: int) -> None:
    if not dataset.staff:
        return
    engine = fresh_engine()
    seed_masters(engine, dataset)
    EventService(engine).create_event(
        Event(
            id=EventId("EV"),
            type=EventType.ELECTION_ADMINISTRATION,
            name="e",
            scheduled_date=date(2026, 9, 1),
        )
    )
    staff_id = str(dataset.staff[0].id)
    avail = AvailabilityService(engine)
    for day in range(1, revisions + 1):
        available_label = "可" if day == revisions else "不可"
        reason = "" if day == revisions else "休暇"
        rows = [[staff_id, available_label, f"2026-08-{day:02d} 09:00:00", reason, ""]]
        avail.import_declarations(EventId("EV"), serialize_csv(_DECLARATION_COLUMNS, rows))

    effective = [
        d for d in avail.effective_declarations(EventId("EV")) if d.staff_id == StaffId(staff_id)
    ]
    assert len(effective) == 1
    assert effective[0].is_available is True  # the last revision said 可
    latest_jst_day = revisions
    assert effective[0].declared_at == datetime(2026, 8, latest_jst_day, 0, 0, tzinfo=UTC)


# --- P-DM03: sufficiency's three classes partition the staff master ----------


@_DB_SETTINGS
@given(gen_master_dataset())
def test_sufficiency_three_classes_partition_all_staff(dataset: Dataset) -> None:
    engine = fresh_engine()
    seed_masters(engine, dataset)
    EventService(engine).create_event(
        Event(
            id=EventId("EV"),
            type=EventType.DISASTER_SHELTER_SUPPORT,
            name="e",
            scheduled_date=date(2026, 9, 1),
        )
    )
    avail = AvailabilityService(engine)
    # Declare a deterministic subset: index %3 == 0 available, ==1 unavailable,
    # ==2 undeclared. The property must hold for any split.
    rows: list[list[str]] = []
    for index, member in enumerate(dataset.staff):
        bucket = index % 3
        if bucket == 0:
            rows.append([str(member.id), "可", "2026-08-01 09:00:00", "", ""])
        elif bucket == 1:
            rows.append([str(member.id), "不可", "2026-08-01 09:00:00", "休暇", ""])
    if rows:
        avail.import_declarations(EventId("EV"), serialize_csv(_DECLARATION_COLUMNS, rows))

    status = avail.sufficiency_status(EventId("EV"))
    assert status.available + status.unavailable + status.undeclared == len(dataset.staff)


# --- helpers ----------------------------------------------------------------


_T = TypeVar("_T")


def _by_id(items: Sequence[_T]) -> list[_T]:
    return sorted(items, key=attrgetter("id"))


def md_export_districts(dataset: Dataset) -> bytes:
    """A districts CSV built straight from the dataset (no DB needed)."""
    rows = [
        [
            str(d.id),
            d.name,
            str(d.representative_point.latitude),
            str(d.representative_point.longitude),
        ]
        for d in dataset.districts
    ]
    return serialize_csv(("小学校区ID", "名称", "緯度", "経度"), rows)
