"""Builders for U-04 tests: deterministic problems with known feasibility.

Kept explicit (not fully random) so each test's expected outcome is clear. A
feasible problem places facilities whose total headcount fits the staff, one
department with a loose cap, and a full travel matrix.
"""

from __future__ import annotations

from datetime import date

from shared_kernel import (
    AssignmentProblem,
    Department,
    DepartmentId,
    Event,
    EventId,
    EventStatus,
    EventType,
    Facility,
    FacilityId,
    JobType,
    ObjectiveWeights,
    OptimizationParameters,
    Position,
    Qualification,
    QualificationRequirement,
    SchoolDistrictId,
    Staff,
    StaffId,
    TravelMetrics,
)


def make_staff(
    index: int,
    *,
    department: str = "D1",
    position: Position = Position.GENERAL,
    job_type: JobType = JobType.CLERICAL,
    qualifications: frozenset[Qualification] = frozenset(),
) -> Staff:
    return Staff(
        id=StaffId(f"S{index}"),
        name=f"name{index}",
        department_id=DepartmentId(department),
        job_type=job_type,
        position=position,
        residence_district_id=SchoolDistrictId("SD1"),
        qualifications=qualifications,
    )


def make_event() -> Event:
    return Event(
        id=EventId("E1"),
        type=EventType.DISASTER_SHELTER_SUPPORT,
        name="drill",
        scheduled_date=date(2026, 8, 1),
        status=EventStatus.COLLECTING_DECLARATIONS,
    )


def make_params(
    *,
    time_limit_seconds: int = 10,
    department_cap_limit: int = 100,
    weights: ObjectiveWeights | None = None,
) -> OptimizationParameters:
    return OptimizationParameters(
        weights=weights or ObjectiveWeights(travel_time=1.0, travel_cost=1.0, inequity=0.5),
        time_limit_seconds=time_limit_seconds,
        department_cap_limit=department_cap_limit,
        random_seed=0,
    )


def travel(seconds: int, cost: float, distance: float = 1.0) -> TravelMetrics:
    return TravelMetrics(distance_km=distance, time_seconds=seconds, cost_yen=cost)


def full_matrix(
    staff: tuple[Staff, ...],
    facilities: tuple[Facility, ...],
    metrics: dict[tuple[str, str], TravelMetrics],
) -> dict[tuple[StaffId, FacilityId], TravelMetrics]:
    """Complete the travel matrix, defaulting any unspecified pair."""
    result: dict[tuple[StaffId, FacilityId], TravelMetrics] = {}
    for member in staff:
        for facility in facilities:
            key = (str(member.id), str(facility.id))
            result[(member.id, facility.id)] = metrics.get(key, travel(600, 0.0))
    return result


def facility(fid: str, headcount: int, requirements: tuple[QualificationRequirement, ...] = ()) -> Facility:
    return Facility(
        id=FacilityId(fid),
        name=fid,
        district_id=SchoolDistrictId("SD1"),
        required_headcount=headcount,
        qualification_requirements=requirements,
    )


def problem(
    staff: tuple[Staff, ...],
    facilities: tuple[Facility, ...],
    metrics: dict[tuple[str, str], TravelMetrics] | None = None,
    *,
    params: OptimizationParameters | None = None,
) -> AssignmentProblem:
    return AssignmentProblem(
        event=make_event(),
        facilities=facilities,
        available_staff=staff,
        travel_matrix=full_matrix(staff, facilities, metrics or {}),
        parameters=params or make_params(),
    )


DEPARTMENT = Department(id=DepartmentId("D1"), name="dept")


__all__ = [
    "DEPARTMENT",
    "facility",
    "full_matrix",
    "make_event",
    "make_params",
    "make_staff",
    "problem",
    "travel",
]
