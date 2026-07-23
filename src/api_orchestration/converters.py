"""LC-04 DTO <-> domain conversions — hand-written pure functions (DP-05).

Collected in one module for two reasons: the round-trip is property-testable
(P-API01), and Pydantic never gets to construct a domain object, which is what
keeps the framework out of the domain layer (U-01 pattern 1).

The same reasoning as U-03's hand-written mappers: automatic mapping saves typing
and costs the boundary.
"""

from __future__ import annotations

from comparison_report import ComparisonReport
from data_management import SufficiencyStatus
from shared_kernel import (
    Assignment,
    AssignmentResult,
    ConstraintViolation,
    Event,
    EventId,
    EventStatus,
    EventType,
    FacilityId,
    ObjectiveWeights,
    OptimizationParameters,
    StaffId,
    from_japanese,
    to_japanese,
)

from . import dto
from .jobs import JobState, OptimizationJob, ReoptimizationMode

# --- Event ------------------------------------------------------------------


def to_domain_event(request: dto.EventRequest) -> Event:
    return Event(
        id=EventId(request.id),
        type=from_japanese(EventType, request.type),  # unknown label -> raises (BR-DM03)
        name=request.name,
        scheduled_date=request.scheduled_date,
    )


def from_domain_event(event: Event) -> dto.EventResponse:
    return dto.EventResponse(
        id=str(event.id),
        type=to_japanese(event.type),
        name=event.name,
        scheduled_date=event.scheduled_date,
        status=to_japanese(event.status),
    )


def to_domain_event_status(label: str) -> EventStatus:
    return from_japanese(EventStatus, label)


# --- Optimization parameters ------------------------------------------------


def to_domain_parameters(request: dto.OptimizationRequest) -> OptimizationParameters:
    return OptimizationParameters(
        weights=ObjectiveWeights(
            travel_time=request.travel_time_weight,
            travel_cost=request.travel_cost_weight,
            inequity=request.inequity_weight,
        ),
        time_limit_seconds=request.time_limit_seconds,
        department_cap_limit=request.department_cap_limit,
    )


def to_domain_mode(request: dto.OptimizationRequest) -> ReoptimizationMode:
    return ReoptimizationMode(request.mode)


# --- Assignment -------------------------------------------------------------


def to_domain_assignment(
    request: dto.AssignmentPatchRequest, event_id: EventId
) -> Assignment:
    return Assignment(
        event_id=event_id,
        staff_id=StaffId(request.staff_id),
        facility_id=FacilityId(request.facility_id),
    )


def from_domain_assignment(assignment: Assignment) -> dto.AssignmentResponse:
    return dto.AssignmentResponse(
        staff_id=str(assignment.staff_id),
        facility_id=str(assignment.facility_id),
        is_pinned=assignment.is_pinned,
    )


def from_domain_violation(violation: ConstraintViolation) -> dto.ConstraintViolationResponse:
    return dto.ConstraintViolationResponse(
        constraint_id=violation.constraint_id,
        detail=violation.detail,
        facility_id=None if violation.facility_id is None else str(violation.facility_id),
        staff_id=None if violation.staff_id is None else str(violation.staff_id),
    )


# --- Job --------------------------------------------------------------------


def from_domain_job_accepted(job: OptimizationJob) -> dto.JobAcceptedResponse:
    return dto.JobAcceptedResponse(job_id=str(job.id), state=job.state.value)


def from_domain_job_status(
    job: OptimizationJob, result: AssignmentResult | None = None
) -> dto.JobStatusResponse:
    if result is None:
        return dto.JobStatusResponse(
            job_id=str(job.id), state=job.state.value, detail=job.detail
        )
    return dto.JobStatusResponse(
        job_id=str(job.id),
        state=JobState.SUCCEEDED.value,
        assignments=[from_domain_assignment(a) for a in result.assignments],
        objective_value=result.objective_value,
        optimality_gap=result.optimality_gap,
        solver_status=result.solver_status.value,
        violations=[from_domain_violation(v) for v in result.violations] or None,
        detail=job.detail,
    )


# --- Sufficiency / Comparison -----------------------------------------------


def from_domain_sufficiency(status: SufficiencyStatus) -> dto.SufficiencyResponse:
    return dto.SufficiencyResponse(
        available=status.available,
        unavailable=status.unavailable,
        undeclared=status.undeclared,
        required=status.required,
        shortage=status.shortage,
    )


def from_domain_comparison(report: ComparisonReport) -> dto.ComparisonResponse:
    return dto.ComparisonResponse(
        event_id=str(report.event_id),
        baseline_time_seconds=report.baseline_time_seconds,
        optimized_time_seconds=report.optimized_time_seconds,
        time_reduction_seconds=report.time_reduction_seconds,
        time_reduction_rate=report.time_reduction_rate,
        baseline_cost_yen=report.baseline_cost_yen,
        optimized_cost_yen=report.optimized_cost_yen,
        cost_reduction_yen=report.cost_reduction_yen,
        cost_reduction_rate=report.cost_reduction_rate,
        assigned_count=report.assigned_count,
        note=report.note,
    )


__all__ = [
    "from_domain_assignment",
    "from_domain_comparison",
    "from_domain_event",
    "from_domain_job_accepted",
    "from_domain_job_status",
    "from_domain_sufficiency",
    "from_domain_violation",
    "to_domain_assignment",
    "to_domain_event",
    "to_domain_event_status",
    "to_domain_mode",
    "to_domain_parameters",
]
