"""Build an AssignmentProblem from stored data (U07-H4).

Pulls the current master and the event's effective declarations from U-03, and
computes the travel matrix with U-02 -- the same compute_travel_metrics U-05 uses
for the comparison, so an optimisation and a comparison of the same event are
measured identically.

FR-04.1: only staff who declared themselves AVAILABLE become decision variables.
That is what makes C4 structural rather than a constraint the solver could violate.
"""

from __future__ import annotations

from sqlalchemy import Engine

from data_management import repositories
from distance_cost import compute_travel_metrics
from shared_kernel import (
    Assignment,
    AssignmentProblem,
    EventId,
    FacilityId,
    OptimizationParameters,
    StaffId,
    TravelMetrics,
    TravelParameters,
)

from .jobs import ReoptimizationMode


class ProblemBuildError(Exception):
    """The event cannot be turned into a problem (missing event/master data)."""


def build_problem(
    engine: Engine,
    event_id: EventId,
    parameters: OptimizationParameters,
    travel: TravelParameters,
    *,
    mode: ReoptimizationMode = ReoptimizationMode.FULL,
    previous: tuple[Assignment, ...] = (),
) -> AssignmentProblem:
    with engine.connect() as conn:
        event = repositories.get_event(conn, event_id)
        if event is None:
            raise ProblemBuildError("event not found")
        facilities = tuple(repositories.find_all_facilities(conn))
        all_staff = {s.id: s for s in repositories.find_all_staff(conn)}
        districts = {d.id: d for d in repositories.find_all_school_districts(conn)}
        declarations = repositories.effective_declarations(conn, event_id)

    # FR-04.1: available declarers only.
    available = tuple(
        all_staff[d.staff_id]
        for d in declarations
        if d.is_available and d.staff_id in all_staff
    )

    travel_matrix: dict[tuple[StaffId, FacilityId], TravelMetrics] = {}
    for member in available:
        for facility in facilities:
            travel_matrix[(member.id, facility.id)] = compute_travel_metrics(
                districts[member.residence_district_id],
                districts[facility.district_id],
                travel,
            )

    # INCREMENTAL pins the previous assignment so nobody already notified is moved
    # (FR-06.6). U-04 validates the pins before solving and refuses if they conflict.
    pinned = (
        tuple(
            Assignment(
                event_id=a.event_id,
                staff_id=a.staff_id,
                facility_id=a.facility_id,
                is_pinned=True,
            )
            for a in previous
        )
        if mode is ReoptimizationMode.INCREMENTAL
        else ()
    )

    return AssignmentProblem(
        event=event,
        facilities=facilities,
        available_staff=available,
        travel_matrix=travel_matrix,
        parameters=parameters,
        pinned_assignments=pinned,
    )


__all__ = ["ProblemBuildError", "build_problem"]
