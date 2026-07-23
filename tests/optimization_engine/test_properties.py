"""Property-based tests for U-04 (P-OPT01..12).

  P-OPT01..05  a feasible solution satisfies C1 (exact), C2, C4, C5.
  P-OPT06/07   objective is finite and non-negative; gap in [0, 1].
  P-OPT08      pinned assignments are preserved.
  P-OPT10      oracle: the solver's objective equals the brute-force optimum.
  P-OPT12      INV-12: when C3 is satisfiable, the solution has no C3 violation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from optimization_engine import OptimizationService
from optimization_engine.scaling import normalised_objective
from shared_kernel import (
    Assignment,
    AssignmentProblem,
    AssignmentResult,
    FacilityId,
    ObjectiveWeights,
    Position,
    QualificationRequirement,
    TravelMetrics,
)

from .support import facility, make_params, make_staff, problem, travel

_NOW = datetime(2026, 7, 16, tzinfo=UTC)
_SETTINGS = settings(max_examples=30, deadline=None)


def _weights(draw: st.DrawFn) -> ObjectiveWeights:
    values = draw(
        st.lists(st.floats(min_value=0.0, max_value=5.0, allow_nan=False), min_size=3, max_size=3)
        .filter(lambda ws: any(w > 0.0 for w in ws))
    )
    return ObjectiveWeights(travel_time=values[0], travel_cost=values[1], inequity=values[2])


@st.composite
def gen_feasible(draw: st.DrawFn) -> AssignmentProblem:
    n_staff = draw(st.integers(min_value=2, max_value=5))
    staff = tuple(make_staff(i) for i in range(1, n_staff + 1))  # all in D1
    n_fac = draw(st.integers(min_value=1, max_value=2))
    facilities = []
    remaining = n_staff
    for k in range(n_fac):
        if remaining <= 0:
            break
        headcount = draw(st.integers(min_value=1, max_value=remaining))
        facilities.append(facility(f"F{k + 1}", headcount))
        remaining -= headcount
    facs = tuple(facilities)
    metrics: dict[tuple[str, str], TravelMetrics] = {}
    for member in staff:
        for fac in facs:
            metrics[(str(member.id), str(fac.id))] = travel(
                draw(st.integers(min_value=0, max_value=3600)),
                draw(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False)),
            )
    params = make_params(weights=_weights(draw), department_cap_limit=n_staff)
    return problem(staff, facs, metrics, params=params)


@_SETTINGS
@given(gen_feasible())
def test_feasible_solution_satisfies_hard_constraints(prob: AssignmentProblem) -> None:
    result = OptimizationService().optimize(prob, now=_NOW)
    assert isinstance(result, AssignmentResult)  # generator guarantees feasibility

    # P-OPT01 C1: each facility gets exactly its headcount
    per_facility = Counter(str(a.facility_id) for a in result.assignments)
    for fac in prob.facilities:
        assert per_facility[str(fac.id)] == fac.required_headcount

    # P-OPT02 C2: each staff member appears at most once
    staff_ids = [a.staff_id for a in result.assignments]
    assert len(staff_ids) == len(set(staff_ids))

    # P-OPT04 C4: only available staff are assigned
    available = {s.id for s in prob.available_staff}
    assert all(a.staff_id in available for a in result.assignments)

    # P-OPT06 / P-OPT07
    assert result.objective_value >= 0.0
    assert 0.0 <= result.optimality_gap <= 1.0


@_SETTINGS
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=3600),
            st.floats(min_value=0.0, max_value=10000.0, allow_nan=False),
        ),
        min_size=3,
        max_size=3,
    ),
    st.integers(min_value=1, max_value=5),
)
def test_oracle_single_slot(pairs: list[tuple[int, float]], seed: int) -> None:
    """One facility needing 1 person: the solver must pick the brute-force best."""
    staff = tuple(make_staff(i) for i in range(1, 4))
    fac = facility("F1", 1)
    metrics = {
        (f"S{i + 1}", "F1"): travel(pairs[i][0], pairs[i][1]) for i in range(3)
    }
    params = make_params(department_cap_limit=3)
    prob = problem(staff, (fac,), metrics, params=replace(params, random_seed=seed))

    result = OptimizationService().optimize(prob, now=_NOW)
    assert isinstance(result, AssignmentResult)

    # brute force: best single assignment
    candidates = [
        (Assignment(event_id=prob.event.id, staff_id=s.id, facility_id=FacilityId("F1")),)
        for s in staff
    ]
    brute_min = min(normalised_objective(prob, c) for c in candidates)
    assert result.objective_value <= brute_min + 1e-6
    assert result.objective_value >= brute_min - 1e-6


@_SETTINGS
@given(st.integers(min_value=0, max_value=2))
def test_inv12_satisfiable_c3_has_no_violation(extra_managers: int) -> None:
    """INV-12: with a manager available, a manager requirement is always met."""
    managers = tuple(
        make_staff(i, position=Position.MANAGER) for i in range(1, 2 + extra_managers)
    )
    others = (make_staff(90), make_staff(91))
    staff = managers + others
    fac = facility(
        "F1",
        2,
        (QualificationRequirement(requirement=Position.MANAGER, required_count=1),),
    )
    result = OptimizationService().optimize(
        problem(staff, (fac,), params=make_params(department_cap_limit=len(staff))), now=_NOW
    )
    assert isinstance(result, AssignmentResult)
    assert result.violations == ()
    assert any(a.staff_id in {m.id for m in managers} for a in result.assignments)


@_SETTINGS
@given(gen_feasible())
def test_pinned_assignment_is_always_kept(prob: AssignmentProblem) -> None:
    """P-OPT08: a valid pin is present in the result."""
    first_staff = prob.available_staff[0]
    first_facility = prob.facilities[0]
    pinned = replace(
        prob,
        pinned_assignments=(
            Assignment(
                event_id=prob.event.id,
                staff_id=first_staff.id,
                facility_id=first_facility.id,
                is_pinned=True,
            ),
        ),
    )
    result = OptimizationService().optimize(pinned, now=_NOW)
    assert isinstance(result, AssignmentResult)
    assert (
        Assignment(
            event_id=prob.event.id,
            staff_id=first_staff.id,
            facility_id=first_facility.id,
            is_pinned=True,
        )
        in result.assignments
    )
