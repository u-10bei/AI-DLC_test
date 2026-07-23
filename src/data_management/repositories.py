"""LC-02 repositories: P-02 RepositoryPort and P-03 DistanceCachePort (A-02).

Every function takes the ``Connection`` its caller's transaction owns and never
commits (DP-01) -- the service that opened ``engine.begin()`` decides the
boundary. All statements are Core expression-language (parameterised, DP-07,
SECURITY-05); no value is ever concatenated into SQL.

The effective-declaration query is a correlated ``MAX(declared_at)`` subquery
(U03-H6), not a window function, so the same SQL runs on old SQLite and on
PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import Connection, RowMapping, Table, delete, func, insert, select, update

from distance_cost import DistanceCacheEntry, canonical_key
from shared_kernel import (
    AvailabilityDeclaration,
    Department,
    Event,
    EventId,
    Facility,
    Qualification,
    QualificationRequirement,
    SchoolDistrict,
    SchoolDistrictId,
    Staff,
    StaffId,
)

from . import mappers, schema


def _require_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _plain(mapping: RowMapping) -> dict[str, object]:
    """A RowMapping as a plain dict, so the mappers stay Row-implementation-agnostic."""
    return dict(mapping)


def _executemany(conn: Connection, table: Table, rows: Sequence[dict[str, object]]) -> None:
    if rows:
        conn.execute(insert(table), list(rows))


# --- writes -----------------------------------------------------------------


def insert_departments(conn: Connection, departments: Iterable[Department]) -> int:
    rows = [mappers.department_to_row(d) for d in departments]
    _executemany(conn, schema.departments, rows)
    return len(rows)


def insert_school_districts(
    conn: Connection, districts: Iterable[SchoolDistrict]
) -> int:
    rows = [mappers.school_district_to_row(d) for d in districts]
    _executemany(conn, schema.school_districts, rows)
    return len(rows)


def insert_staff(conn: Connection, members: Iterable[Staff]) -> int:
    member_list = list(members)
    _executemany(conn, schema.staff, [mappers.staff_to_row(m) for m in member_list])
    qual_rows: list[dict[str, object]] = []
    for member in member_list:
        qual_rows.extend(mappers.staff_qualification_rows(member))
    _executemany(conn, schema.staff_qualifications, qual_rows)
    return len(member_list)


def insert_facilities(conn: Connection, facilities: Iterable[Facility]) -> int:
    facility_list = list(facilities)
    _executemany(conn, schema.facilities, [mappers.facility_to_row(f) for f in facility_list])
    req_rows: list[dict[str, object]] = []
    for facility in facility_list:
        req_rows.extend(mappers.facility_requirement_rows(facility))
    _executemany(conn, schema.facility_qualification_requirements, req_rows)
    return len(facility_list)


def insert_event(conn: Connection, event: Event) -> None:
    conn.execute(insert(schema.events), mappers.event_to_row(event))


def update_event_status(conn: Connection, event_id: EventId, status_name: str) -> None:
    conn.execute(
        update(schema.events)
        .where(schema.events.c.id == str(event_id))
        .values(status=status_name)
    )


def delete_event(conn: Connection, event_id: EventId) -> bool:
    result = conn.execute(delete(schema.events).where(schema.events.c.id == str(event_id)))
    return result.rowcount > 0


def insert_declarations(
    conn: Connection, event_id: EventId, declarations: Iterable[AvailabilityDeclaration]
) -> int:
    rows = [mappers.declaration_to_row(d, event_id) for d in declarations]
    _executemany(conn, schema.availability_declarations, rows)
    return len(rows)


# --- reads ------------------------------------------------------------------


def existing_department_ids(conn: Connection) -> set[str]:
    return {str(v) for v in conn.execute(select(schema.departments.c.id)).scalars().all()}


def existing_district_ids(conn: Connection) -> set[str]:
    return {str(v) for v in conn.execute(select(schema.school_districts.c.id)).scalars().all()}


def existing_staff_ids(conn: Connection) -> set[str]:
    return {str(v) for v in conn.execute(select(schema.staff.c.id)).scalars().all()}


def all_staff_count(conn: Connection) -> int:
    return _require_int(
        conn.execute(select(func.count()).select_from(schema.staff)).scalar_one()
    )


def facility_count(conn: Connection) -> int:
    return _require_int(
        conn.execute(select(func.count()).select_from(schema.facilities)).scalar_one()
    )


def total_required_headcount(conn: Connection) -> int:
    """Sum of required_headcount over the facility master.

    Facilities are a global master with no per-event link in this schema, so the
    sufficiency denominator is the whole master (business-logic-model.md 3.4).
    """
    value = conn.execute(
        select(func.coalesce(func.sum(schema.facilities.c.required_headcount), 0))
    ).scalar_one()
    return _require_int(value)


def _qualifications_by_staff(conn: Connection) -> dict[str, set[Qualification]]:
    result: dict[str, set[Qualification]] = {}
    rows = conn.execute(
        select(
            schema.staff_qualifications.c.staff_id,
            schema.staff_qualifications.c.qualification,
        )
    )
    for row in rows:
        staff_id = str(row._mapping["staff_id"])
        name = str(row._mapping["qualification"])
        result.setdefault(staff_id, set()).add(Qualification[name])
    return result


def find_all_school_districts(conn: Connection) -> list[SchoolDistrict]:
    rows = conn.execute(select(schema.school_districts)).all()
    return [mappers.row_to_school_district(_plain(row._mapping)) for row in rows]


def find_all_staff(conn: Connection) -> list[Staff]:
    quals = _qualifications_by_staff(conn)
    rows = conn.execute(select(schema.staff)).all()
    members: list[Staff] = []
    for row in rows:
        staff_id = str(row._mapping["id"])
        members.append(
            mappers.row_to_staff(_plain(row._mapping), frozenset(quals.get(staff_id, set())))
        )
    return members


def get_staff(conn: Connection, staff_id: StaffId) -> Staff | None:
    row = conn.execute(
        select(schema.staff).where(schema.staff.c.id == str(staff_id))
    ).first()
    if row is None:
        return None
    qual_rows = conn.execute(
        select(schema.staff_qualifications.c.qualification).where(
            schema.staff_qualifications.c.staff_id == str(staff_id)
        )
    ).scalars().all()
    qualifications = frozenset(Qualification[str(name)] for name in qual_rows)
    return mappers.row_to_staff(_plain(row._mapping), qualifications)


def get_event(conn: Connection, event_id: EventId) -> Event | None:
    row = conn.execute(
        select(schema.events).where(schema.events.c.id == str(event_id))
    ).first()
    return None if row is None else mappers.row_to_event(_plain(row._mapping))


def find_all_facilities(conn: Connection) -> list[Facility]:
    req_rows = conn.execute(select(schema.facility_qualification_requirements)).all()
    reqs_by_facility: dict[str, list[QualificationRequirement]] = {}
    for row in req_rows:
        facility_id = str(row._mapping["facility_id"])
        reqs_by_facility.setdefault(facility_id, []).append(
            mappers.row_to_qualification_requirement(_plain(row._mapping))
        )
    rows = conn.execute(select(schema.facilities)).all()
    facilities: list[Facility] = []
    for row in rows:
        facility_id = str(row._mapping["id"])
        facilities.append(
            mappers.row_to_facility(
                _plain(row._mapping), tuple(reqs_by_facility.get(facility_id, []))
            )
        )
    return facilities


def effective_declarations(
    conn: Connection, event_id: EventId
) -> list[AvailabilityDeclaration]:
    """Each (staff, event)'s latest declaration -- correlated MAX subquery (U03-H6)."""
    outer = schema.availability_declarations.alias("d1")
    inner = schema.availability_declarations.alias("d2")
    latest = (
        select(func.max(inner.c.declared_at))
        .where(inner.c.staff_id == outer.c.staff_id)
        .where(inner.c.event_id == outer.c.event_id)
        .scalar_subquery()
    )
    stmt = select(outer).where(
        outer.c.event_id == str(event_id), outer.c.declared_at == latest
    )
    rows = conn.execute(stmt).all()
    return [mappers.row_to_declaration(_plain(row._mapping)) for row in rows]


def declaration_history(
    conn: Connection, staff_id: StaffId, event_id: EventId
) -> list[AvailabilityDeclaration]:
    stmt = (
        select(schema.availability_declarations)
        .where(schema.availability_declarations.c.staff_id == str(staff_id))
        .where(schema.availability_declarations.c.event_id == str(event_id))
        .order_by(schema.availability_declarations.c.declared_at.desc())
    )
    rows = conn.execute(stmt).all()
    return [mappers.row_to_declaration(_plain(row._mapping)) for row in rows]


# --- P-03 DistanceCachePort implementation ----------------------------------


class SqlDistanceCache:
    """P-03 DistanceCachePort backed by the ``distance_cache`` table.

    Constructed with the connection of the transaction it participates in, so a
    recompute (invalidate_all + put_distances) is atomic with the master update
    that triggered it (DP-04).
    """

    def __init__(self, conn: Connection) -> None:
        self._conn = conn

    def get_distance(
        self, district_a: SchoolDistrictId, district_b: SchoolDistrictId
    ) -> float | None:
        a, b = canonical_key(district_a, district_b)
        value = self._conn.execute(
            select(schema.distance_cache.c.great_circle_km).where(
                schema.distance_cache.c.district_a == str(a),
                schema.distance_cache.c.district_b == str(b),
            )
        ).scalar_one_or_none()
        if value is None:
            return None
        return float(value) if isinstance(value, int | float) else None

    def put_distances(self, entries: Iterable[DistanceCacheEntry]) -> None:
        rows = [mappers.distance_entry_to_row(entry) for entry in entries]
        _executemany(self._conn, schema.distance_cache, rows)

    def invalidate_all(self) -> None:
        self._conn.execute(delete(schema.distance_cache))


__all__ = [
    "SqlDistanceCache",
    "all_staff_count",
    "declaration_history",
    "delete_event",
    "effective_declarations",
    "existing_department_ids",
    "existing_district_ids",
    "existing_staff_ids",
    "facility_count",
    "find_all_facilities",
    "find_all_school_districts",
    "find_all_staff",
    "get_event",
    "get_staff",
    "insert_declarations",
    "insert_departments",
    "insert_event",
    "insert_facilities",
    "insert_school_districts",
    "insert_staff",
    "total_required_headcount",
    "update_event_status",
]
