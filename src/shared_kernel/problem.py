"""The assignment problem, its result, and the historical record.

``AssignmentResult.__post_init__`` (BR-07) is the type-level firewall against
solver bugs. FR-04.5 demotes C3 and nothing else, so a result carrying a C1,
C2, C4 or C5 violation means U-04 is wrong. It is refused here, at the boundary,
instead of flowing into the comparison report and onto a manager's desk.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from .entities import Assignment, AvailabilityDeclaration, Event, Facility, Staff
from .enums import SolverStatus
from .exceptions import (
    DuplicateAssignmentError,
    InvalidObjectiveValueError,
    NonDemotableConstraintViolationError,
)
from .identifiers import EventId, FacilityId, StaffId
from .value_objects import OptimizationParameters, TravelMetrics

ConstraintId = Literal["C1", "C2", "C3", "C4", "C5"]

#: The only constraint FR-04.5 ever demotes to a soft constraint.
DEMOTABLE_CONSTRAINTS: frozenset[str] = frozenset({"C3"})


@dataclass(frozen=True, slots=True)
class ConstraintViolation:
    """A hard constraint that the returned solution does not satisfy."""

    constraint_id: ConstraintId
    detail: str
    facility_id: FacilityId | None = None
    staff_id: StaffId | None = None


@dataclass(frozen=True, slots=True)
class AssignmentProblem:
    """Everything the solver needs for one run.

    ``available_staff`` holds only those who *declared* availability (FR-04.1).
    Staff who never answered are absent, and so are staff who declared
    themselves unavailable -- but for different reasons, which U-03 must keep
    distinct when it reports sufficiency (handoff U01-H10).
    """

    event: Event
    facilities: tuple[Facility, ...]
    available_staff: tuple[Staff, ...]
    travel_matrix: dict[tuple[StaffId, FacilityId], TravelMetrics]
    parameters: OptimizationParameters
    pinned_assignments: tuple[Assignment, ...] = ()


@dataclass(frozen=True, slots=True)
class AssignmentResult:
    """A solved (or partially solved) assignment. BR-07.

    A ``TIME_LIMIT_REACHED`` result is still a valid one: US-20 requires the
    best feasible solution found so far, together with its optimality gap.
    """

    event_id: EventId
    assignments: tuple[Assignment, ...]
    objective_value: float
    optimality_gap: float
    solver_status: SolverStatus
    computed_at: datetime
    violations: tuple[ConstraintViolation, ...] = ()

    def __post_init__(self) -> None:
        # INV-06
        if math.isnan(self.objective_value) or math.isinf(self.objective_value):
            raise InvalidObjectiveValueError(
                "objective_value is not finite", violated_rule="BR-07", event_id=self.event_id
            )
        if self.objective_value < 0.0:
            raise InvalidObjectiveValueError(
                "objective_value is negative", violated_rule="BR-07", event_id=self.event_id
            )
        if not 0.0 <= self.optimality_gap <= 1.0:
            raise InvalidObjectiveValueError(
                "optimality_gap outside [0, 1]", violated_rule="BR-07", event_id=self.event_id
            )

        # BR-07: only C3 is ever demoted. Anything else here is a solver bug.
        for violation in self.violations:
            if violation.constraint_id not in DEMOTABLE_CONSTRAINTS:
                raise NonDemotableConstraintViolationError(
                    f"result carries a {violation.constraint_id} violation, "
                    "but only C3 is demotable",
                    violated_rule="BR-07",
                    event_id=self.event_id,
                    facility_id=violation.facility_id,
                    staff_id=violation.staff_id,
                )

        # INV-01
        seen: set[StaffId] = set()
        for assignment in self.assignments:
            if assignment.staff_id in seen:
                raise DuplicateAssignmentError(
                    "a staff member appears in two assignments for one event",
                    violated_rule="BR-07",
                    event_id=self.event_id,
                    staff_id=assignment.staff_id,
                )
            seen.add(assignment.staff_id)


@dataclass(frozen=True, slots=True)
class HistoricalRecord:
    """What actually happened at a past event, used as the comparison baseline.

    ``availability_declarations`` matters: the staff who *could* have served is a
    superset of those who did. Replaying the event over only the people actually
    assigned would understate the reduction the optimizer can achieve (R3-CQ6=A).
    """

    event_id: EventId
    actual_assignments: tuple[Assignment, ...]
    availability_declarations: tuple[AvailabilityDeclaration, ...] = field(default=())


__all__ = [
    "DEMOTABLE_CONSTRAINTS",
    "AssignmentProblem",
    "AssignmentResult",
    "ConstraintId",
    "ConstraintViolation",
    "HistoricalRecord",
]
