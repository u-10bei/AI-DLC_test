"""Builders for U-05 tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

from comparison_report import Master
from shared_kernel import (
    Assignment,
    AvailabilityDeclaration,
    Coordinates,
    DepartmentId,
    Event,
    EventId,
    EventStatus,
    EventType,
    Facility,
    FacilityId,
    HistoricalRecord,
    JobType,
    ObjectiveWeights,
    OptimizationParameters,
    Position,
    SchoolDistrict,
    SchoolDistrictId,
    Staff,
    StaffId,
    TravelParameters,
)

NOW = datetime(2026, 7, 16, tzinfo=UTC)


def district(did: str, lat: float, lon: float) -> SchoolDistrict:
    return SchoolDistrict(
        id=SchoolDistrictId(did), name=did, representative_point=Coordinates(lat, lon)
    )


def staff(sid: str, residence: str, department: str = "D1") -> Staff:
    return Staff(
        id=StaffId(sid),
        name=f"name-{sid}",
        department_id=DepartmentId(department),
        job_type=JobType.CLERICAL,
        position=Position.GENERAL,
        residence_district_id=SchoolDistrictId(residence),
    )


def facility(fid: str, district_id: str, headcount: int = 1) -> Facility:
    return Facility(
        id=FacilityId(fid),
        name=fid,
        district_id=SchoolDistrictId(district_id),
        required_headcount=headcount,
    )


def master(
    staff_list: tuple[Staff, ...],
    facilities: tuple[Facility, ...],
    districts: tuple[SchoolDistrict, ...],
) -> Master:
    return Master(
        staff_by_id={s.id: s for s in staff_list},
        facilities_by_id={f.id: f for f in facilities},
        districts_by_id={d.id: d for d in districts},
    )


def event(event_id: str = "E1") -> Event:
    return Event(
        id=EventId(event_id),
        type=EventType.DISASTER_SHELTER_SUPPORT,
        name="drill",
        scheduled_date=date(2026, 8, 1),
        status=EventStatus.COLLECTING_DECLARATIONS,
    )


def declaration(staff_id: str, event_id: str = "E1", *, available: bool = True) -> AvailabilityDeclaration:
    from shared_kernel import ReasonCategory

    return AvailabilityDeclaration(
        staff_id=StaffId(staff_id),
        event_id=EventId(event_id),
        is_available=available,
        declared_at=NOW,
        reason_category=None if available else ReasonCategory.LEAVE,
    )


def assignment(staff_id: str, facility_id: str, event_id: str = "E1") -> Assignment:
    return Assignment(
        event_id=EventId(event_id), staff_id=StaffId(staff_id), facility_id=FacilityId(facility_id)
    )


def historical(
    actual: tuple[Assignment, ...], declared: tuple[AvailabilityDeclaration, ...], event_id: str = "E1"
) -> HistoricalRecord:
    return HistoricalRecord(
        event_id=EventId(event_id), actual_assignments=actual, availability_declarations=declared
    )


def opt_params(
    *, travel_time: float = 1.0, travel_cost: float = 1.0, inequity: float = 0.0
) -> OptimizationParameters:
    return OptimizationParameters(
        weights=ObjectiveWeights(travel_time=travel_time, travel_cost=travel_cost, inequity=inequity),
        time_limit_seconds=10,
        department_cap_limit=100,
        random_seed=0,
    )


def travel_params() -> TravelParameters:
    return TravelParameters()


__all__ = [
    "NOW",
    "assignment",
    "declaration",
    "district",
    "event",
    "facility",
    "historical",
    "master",
    "opt_params",
    "staff",
    "travel_params",
]
