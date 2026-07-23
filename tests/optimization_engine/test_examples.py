"""Example-based tests for U-04: optimal choice, diagnosis branches, pins."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from optimization_engine import (
    InfeasibilityCause,
    InfeasibilityDiagnosis,
    OptimizationService,
    PinnedAssignmentInfeasibleError,
)
from shared_kernel import (
    Assignment,
    AssignmentProblem,
    AssignmentResult,
    FacilityId,
    Position,
    QualificationRequirement,
    SolverStatus,
    StaffId,
)

from .support import facility, make_params, make_staff, problem, travel

_NOW = datetime(2026, 7, 16, tzinfo=UTC)


def _solve(prob: AssignmentProblem) -> AssignmentResult | InfeasibilityDiagnosis:
    return OptimizationService().optimize(prob, now=_NOW)


def _pin_all_to(prob: AssignmentProblem, facility_id: str) -> AssignmentProblem:
    pins = tuple(
        Assignment(
            event_id=prob.event.id,
            staff_id=s.id,
            facility_id=FacilityId(facility_id),
            is_pinned=True,
        )
        for s in prob.available_staff
    )
    return replace(prob, pinned_assignments=pins)


def test_optimal_picks_the_two_cheapest() -> None:
    staff = (make_staff(1), make_staff(2, department="D2"), make_staff(3, department="D3"))
    metrics = {
        ("S1", "F1"): travel(600, 0.0),
        ("S2", "F1"): travel(1200, 300.0),
        ("S3", "F1"): travel(3600, 8000.0),  # far and expensive
    }
    result = _solve(problem(staff, (facility("F1", 2),), metrics))
    assert isinstance(result, AssignmentResult)
    assert result.solver_status is SolverStatus.OPTIMAL
    assert result.optimality_gap == 0.0
    assert sorted(str(a.staff_id) for a in result.assignments) == ["S1", "S2"]
    assert result.objective_value >= 0.0


def test_total_shortage_is_diagnosed_not_relaxed() -> None:
    staff = (make_staff(1), make_staff(2), make_staff(3))
    result = _solve(problem(staff, (facility("F1", 5),)))  # need 5, have 3
    assert isinstance(result, InfeasibilityDiagnosis)
    assert result.cause is InfeasibilityCause.TOTAL_SHORTAGE
    assert result.shortage_count == 2


def test_c3_only_cause_is_demoted() -> None:
    staff = (make_staff(1), make_staff(2), make_staff(3))
    fac = facility(
        "F1", 2, (QualificationRequirement(requirement=Position.MANAGER, required_count=1),)
    )
    result = _solve(problem(staff, (fac,)))
    assert isinstance(result, AssignmentResult)
    assert len(result.assignments) == 2
    assert [v.constraint_id for v in result.violations] == ["C3"]


def test_c3_satisfiable_yields_no_violation() -> None:
    # A manager IS available -> the solver must satisfy C3 (INV-12).
    staff = (make_staff(1, position=Position.MANAGER), make_staff(2), make_staff(3))
    fac = facility(
        "F1", 2, (QualificationRequirement(requirement=Position.MANAGER, required_count=1),)
    )
    result = _solve(problem(staff, (fac,)))
    assert isinstance(result, AssignmentResult)
    assert result.violations == ()
    assert StaffId("S1") in {a.staff_id for a in result.assignments}


def test_pinned_assignment_is_preserved() -> None:
    staff = (make_staff(1), make_staff(2), make_staff(3, department="D3"))
    prob = problem(staff, (facility("F1", 2),), {("S3", "F1"): travel(9000, 9000.0)})
    pinned = replace(
        prob,
        pinned_assignments=(
            Assignment(
                event_id=prob.event.id,
                staff_id=StaffId("S3"),
                facility_id=FacilityId("F1"),
                is_pinned=True,
            ),
        ),
    )
    result = _solve(pinned)
    assert isinstance(result, AssignmentResult)
    s3 = [a for a in result.assignments if a.staff_id == StaffId("S3")]
    assert len(s3) == 1
    assert s3[0].is_pinned is True


def test_pin_exceeding_capacity_errors_without_solving() -> None:
    staff = (make_staff(1), make_staff(2), make_staff(3))
    pinned = _pin_all_to(problem(staff, (facility("F1", 2),)), "F1")  # 3 pins, cap 2
    with pytest.raises(PinnedAssignmentInfeasibleError) as exc_info:
        _solve(pinned)
    assert exc_info.value.violated_rule == "C1"


def test_pin_violating_department_cap_errors() -> None:
    staff = (make_staff(1), make_staff(2))  # both in D1
    pinned = _pin_all_to(
        problem(staff, (facility("F1", 2),), params=make_params(department_cap_limit=1)), "F1"
    )
    with pytest.raises(PinnedAssignmentInfeasibleError) as exc_info:
        _solve(pinned)
    assert exc_info.value.violated_rule == "C5"


def test_pin_error_carries_no_pii() -> None:
    staff = (make_staff(1), make_staff(2), make_staff(3))
    pinned = _pin_all_to(problem(staff, (facility("F1", 2),)), "F1")
    with pytest.raises(PinnedAssignmentInfeasibleError) as exc_info:
        _solve(pinned)
    assert "name1" not in str(exc_info.value.context())


def test_department_cap_limits_assignment() -> None:
    staff = tuple(make_staff(i) for i in range(1, 5))  # 4 staff, all D1
    result = _solve(
        problem(staff, (facility("F1", 1),), params=make_params(department_cap_limit=1))
    )
    assert isinstance(result, AssignmentResult)
    assert len(result.assignments) == 1
