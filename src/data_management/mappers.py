"""LC-03 mappers: DB row <-> frozen domain type (A-02, DP-06).

Hand-written, because the domain types are frozen and an ORM would need mutable
models (Q1=A). Two directions:

  * ``*_to_row`` / ``*_rows`` build the ``dict`` parameters for an INSERT.
  * ``row_to_*`` rebuild a domain object from a stored row, RE-RUNNING its
    ``__post_init__``. A corrupt row (a persisted latitude of 95.0, an unknown
    job-title identifier) therefore fails right here as a ``DataIntegrityError``
    rather than escaping as a silently-wrong domain object (DP-02, BR-DM13,
    SECURITY-15). The error context is the entity kind and the row's ID only,
    never a name (SECURITY-03, BR-DM14).

Enum members are stored as their English identifier (``member.name``), not their
Japanese label; the Japanese label lives only at the CSV/API boundary (U01-H24).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime

from distance_cost import DistanceCacheEntry
from shared_kernel import (
    AvailabilityDeclaration,
    Coordinates,
    DataIntegrityError,
    Department,
    DepartmentId,
    DomainError,
    Event,
    EventId,
    EventStatus,
    EventType,
    Facility,
    FacilityId,
    JobType,
    Position,
    Qualification,
    QualificationRequirement,
    ReasonCategory,
    SchoolDistrict,
    SchoolDistrictId,
    Staff,
    StaffId,
)

# --- typed coercion ---------------------------------------------------------
# The DBAPI hands back values typed ``object``; these narrow them and reject
# anything unexpected. A rejection is wrapped as DataIntegrityError by the caller.


def _as_str(value: object) -> str:
    if isinstance(value, str):
        return value
    raise TypeError("expected a string column")


def _as_int(value: object) -> int:
    if isinstance(value, bool):  # bool is an int subclass; not a valid integer column here
        raise TypeError("expected an integer column, got bool")
    if isinstance(value, int):
        return value
    raise TypeError("expected an integer column")


def _as_float(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("expected a float column, got bool")
    if isinstance(value, int | float):
        return float(value)
    raise TypeError("expected a float column")


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise TypeError("expected a boolean column")


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        raise TypeError("expected a date column, got datetime")
    if isinstance(value, date):
        return value
    raise TypeError("expected a date column")


def _as_utc_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        # Stored naive-UTC; re-attach UTC so it round-trips to a UTC-aware value.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    raise TypeError("expected a datetime column")


def _safe_id(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    return value if isinstance(value, str) else "<unknown>"


# --- requirement enum (Qualification | Position | JobType) ------------------

_Requirement = Qualification | Position | JobType


def requirement_name(requirement: _Requirement) -> str:
    return requirement.name


def requirement_from_name(name: str) -> _Requirement:
    """Reconstruct a facility requirement from its stored identifier.

    The three enums share no member names, so the lookup is unambiguous.
    """
    for enum_cls in (Qualification, Position, JobType):
        try:
            return enum_cls[name]
        except KeyError:
            continue
    raise ValueError(f"unknown requirement identifier: {name}")


# --- Department -------------------------------------------------------------


def department_to_row(department: Department) -> dict[str, object]:
    return {
        "id": str(department.id),
        "name": department.name,
        "concurrent_assignment_cap": department.concurrent_assignment_cap,
    }


def row_to_department(mapping: Mapping[str, object]) -> Department:
    entity_id = _safe_id(mapping, "id")
    try:
        cap_raw = mapping["concurrent_assignment_cap"]
        cap = None if cap_raw is None else _as_int(cap_raw)
        return Department(
            id=DepartmentId(_as_str(mapping["id"])),
            name=_as_str(mapping["name"]),
            concurrent_assignment_cap=cap,
        )
    except (KeyError, ValueError, TypeError, DomainError) as exc:
        raise DataIntegrityError(str(exc), entity="department", entity_id=entity_id) from exc


# --- SchoolDistrict ---------------------------------------------------------


def school_district_to_row(district: SchoolDistrict) -> dict[str, object]:
    return {
        "id": str(district.id),
        "name": district.name,
        "latitude": district.representative_point.latitude,
        "longitude": district.representative_point.longitude,
    }


def row_to_school_district(mapping: Mapping[str, object]) -> SchoolDistrict:
    entity_id = _safe_id(mapping, "id")
    try:
        return SchoolDistrict(
            id=SchoolDistrictId(_as_str(mapping["id"])),
            name=_as_str(mapping["name"]),
            representative_point=Coordinates(
                latitude=_as_float(mapping["latitude"]),
                longitude=_as_float(mapping["longitude"]),
            ),
        )
    except (KeyError, ValueError, TypeError, DomainError) as exc:
        raise DataIntegrityError(
            str(exc), entity="school_district", entity_id=entity_id
        ) from exc


# --- Staff ------------------------------------------------------------------


def staff_to_row(member: Staff) -> dict[str, object]:
    return {
        "id": str(member.id),
        "name": member.name,
        "department_id": str(member.department_id),
        "job_type": member.job_type.name,
        "position": member.position.name,
        "residence_district_id": str(member.residence_district_id),
    }


def staff_qualification_rows(member: Staff) -> list[dict[str, object]]:
    return [
        {"staff_id": str(member.id), "qualification": qualification.name}
        for qualification in member.qualifications
    ]


def row_to_staff(
    mapping: Mapping[str, object], qualifications: frozenset[Qualification]
) -> Staff:
    entity_id = _safe_id(mapping, "id")
    try:
        return Staff(
            id=StaffId(_as_str(mapping["id"])),
            name=_as_str(mapping["name"]),
            department_id=DepartmentId(_as_str(mapping["department_id"])),
            job_type=JobType[_as_str(mapping["job_type"])],
            position=Position[_as_str(mapping["position"])],
            residence_district_id=SchoolDistrictId(_as_str(mapping["residence_district_id"])),
            qualifications=qualifications,
        )
    except (KeyError, ValueError, TypeError, DomainError) as exc:
        raise DataIntegrityError(str(exc), entity="staff", entity_id=entity_id) from exc


# --- Facility ---------------------------------------------------------------


def facility_to_row(facility: Facility) -> dict[str, object]:
    return {
        "id": str(facility.id),
        "name": facility.name,
        "district_id": str(facility.district_id),
        "required_headcount": facility.required_headcount,
    }


def facility_requirement_rows(facility: Facility) -> list[dict[str, object]]:
    return [
        {
            "facility_id": str(facility.id),
            "requirement": requirement_name(req.requirement),
            "required_count": req.required_count,
        }
        for req in facility.qualification_requirements
    ]


def row_to_facility(
    mapping: Mapping[str, object],
    requirements: tuple[QualificationRequirement, ...],
) -> Facility:
    entity_id = _safe_id(mapping, "id")
    try:
        return Facility(
            id=FacilityId(_as_str(mapping["id"])),
            name=_as_str(mapping["name"]),
            district_id=SchoolDistrictId(_as_str(mapping["district_id"])),
            required_headcount=_as_int(mapping["required_headcount"]),
            qualification_requirements=requirements,
        )
    except (KeyError, ValueError, TypeError, DomainError) as exc:
        raise DataIntegrityError(str(exc), entity="facility", entity_id=entity_id) from exc


def row_to_qualification_requirement(
    mapping: Mapping[str, object],
) -> QualificationRequirement:
    return QualificationRequirement(
        requirement=requirement_from_name(_as_str(mapping["requirement"])),
        required_count=_as_int(mapping["required_count"]),
    )


# --- Event ------------------------------------------------------------------


def event_to_row(event: Event) -> dict[str, object]:
    return {
        "id": str(event.id),
        "type": event.type.name,
        "name": event.name,
        "scheduled_date": event.scheduled_date,
        "status": event.status.name,
    }


def row_to_event(mapping: Mapping[str, object]) -> Event:
    entity_id = _safe_id(mapping, "id")
    try:
        return Event(
            id=EventId(_as_str(mapping["id"])),
            type=EventType[_as_str(mapping["type"])],
            name=_as_str(mapping["name"]),
            scheduled_date=_as_date(mapping["scheduled_date"]),
            status=EventStatus[_as_str(mapping["status"])],
        )
    except (KeyError, ValueError, TypeError, DomainError) as exc:
        raise DataIntegrityError(str(exc), entity="event", entity_id=entity_id) from exc


# --- AvailabilityDeclaration ------------------------------------------------


def declaration_to_row(
    declaration: AvailabilityDeclaration, event_id: EventId
) -> dict[str, object]:
    reason = declaration.reason_category
    declared_at = declaration.declared_at
    stored_at = (
        declared_at.astimezone(UTC).replace(tzinfo=None)
        if declared_at.tzinfo is not None
        else declared_at
    )
    return {
        "staff_id": str(declaration.staff_id),
        "event_id": str(event_id),
        "is_available": declaration.is_available,
        "reason_category": None if reason is None else reason.name,
        "other_reason_note": declaration.other_reason_note,
        "declared_at": stored_at,
    }


def row_to_declaration(mapping: Mapping[str, object]) -> AvailabilityDeclaration:
    staff_id = _safe_id(mapping, "staff_id")
    try:
        reason_raw = mapping["reason_category"]
        reason = None if reason_raw is None else ReasonCategory[_as_str(reason_raw)]
        note_raw = mapping["other_reason_note"]
        note = None if note_raw is None else _as_str(note_raw)
        return AvailabilityDeclaration(
            staff_id=StaffId(_as_str(mapping["staff_id"])),
            event_id=EventId(_as_str(mapping["event_id"])),
            is_available=_as_bool(mapping["is_available"]),
            declared_at=_as_utc_datetime(mapping["declared_at"]),
            reason_category=reason,
            other_reason_note=note,
        )
    except (KeyError, ValueError, TypeError, DomainError) as exc:
        raise DataIntegrityError(
            str(exc), entity="availability_declaration", entity_id=staff_id
        ) from exc


# --- DistanceCacheEntry -----------------------------------------------------


def distance_entry_to_row(entry: DistanceCacheEntry) -> dict[str, object]:
    return {
        "district_a": str(entry.district_a),
        "district_b": str(entry.district_b),
        "great_circle_km": entry.great_circle_km,
    }


def row_to_distance_entry(mapping: Mapping[str, object]) -> DistanceCacheEntry:
    entity_id = _safe_id(mapping, "district_a")
    try:
        return DistanceCacheEntry(
            district_a=SchoolDistrictId(_as_str(mapping["district_a"])),
            district_b=SchoolDistrictId(_as_str(mapping["district_b"])),
            great_circle_km=_as_float(mapping["great_circle_km"]),
        )
    except (KeyError, ValueError, TypeError, DomainError) as exc:
        raise DataIntegrityError(
            str(exc), entity="distance_cache", entity_id=entity_id
        ) from exc


__all__ = [
    "declaration_to_row",
    "department_to_row",
    "distance_entry_to_row",
    "event_to_row",
    "facility_requirement_rows",
    "facility_to_row",
    "requirement_from_name",
    "requirement_name",
    "row_to_declaration",
    "row_to_department",
    "row_to_distance_entry",
    "row_to_event",
    "row_to_facility",
    "row_to_qualification_requirement",
    "row_to_school_district",
    "row_to_staff",
    "school_district_to_row",
    "staff_qualification_rows",
    "staff_to_row",
]
