"""LC-01 ModelBuilder: AssignmentProblem -> MilpModel (pure, ortools-free).

No variable pruning (Q3=A): every (available staff, facility) pair is a variable,
so no optimal solution is excluded. C4 is structural -- only ``available_staff``
become variables, so an unavailable person can never be assigned.
"""

from __future__ import annotations

from shared_kernel import (
    AssignmentProblem,
    DepartmentId,
    JobType,
    Position,
    Qualification,
    QualificationRequirement,
    Staff,
    StaffId,
)

from .exceptions import ModelConstructionError
from .model import C3Requirement, MilpModel, Pair
from .scaling import big_m, compute_normalisation, pair_objective_coeff, tmax_coeff


def _is_eligible(staff: Staff, requirement: Qualification | Position | JobType) -> bool:
    if isinstance(requirement, Qualification):
        return requirement in staff.qualifications
    if isinstance(requirement, Position):
        return staff.position is requirement
    return staff.job_type is requirement


def _c3_requirement(
    facility_id: str, req: QualificationRequirement, staff: tuple[Staff, ...]
) -> C3Requirement:
    from shared_kernel import FacilityId

    eligible = frozenset(s.id for s in staff if _is_eligible(s, req.requirement))
    return C3Requirement(
        facility_id=FacilityId(facility_id),
        eligible_staff=eligible,
        required_count=req.required_count,
    )


def build_model(
    problem: AssignmentProblem, *, demote_c3: bool = False, include_c3: bool = True
) -> MilpModel:
    """Translate the problem into an abstract integer program.

    ``include_c3=False`` drops the C3 requirements entirely (the relaxed solve used
    to isolate a C3-only infeasibility, BR-OPT08). ``demote_c3=True`` keeps them but
    as soft constraints penalised by big-M.
    """
    staff = problem.available_staff
    facilities = problem.facilities
    norm = compute_normalisation(problem)

    pairs: list[Pair] = []
    objective_coeff: dict[Pair, int] = {}
    travel_seconds: dict[Pair, int] = {}
    for member in staff:
        for facility in facilities:
            key = (member.id, facility.id)
            if key not in problem.travel_matrix:
                raise ModelConstructionError(
                    "travel matrix is missing an entry",
                    violated_rule="ModelBuilder",
                    staff_id=member.id,
                    facility_id=facility.id,
                )
            pairs.append(key)
            objective_coeff[key] = pair_objective_coeff(problem, norm, member.id, facility.id)
            travel_seconds[key] = problem.travel_matrix[key].time_seconds

    capacity = {f.id: f.required_headcount for f in facilities}

    c3_requirements = (
        tuple(
            _c3_requirement(str(f.id), req, staff)
            for f in facilities
            for req in f.qualification_requirements
        )
        if include_c3
        else ()
    )

    department_members: dict[DepartmentId, list[StaffId]] = {}
    for member in staff:
        department_members.setdefault(member.department_id, []).append(member.id)

    pinned = frozenset(
        (a.staff_id, a.facility_id) for a in problem.pinned_assignments
    )

    return MilpModel(
        event_id=problem.event.id,
        staff_ids=tuple(s.id for s in staff),
        facility_ids=tuple(f.id for f in facilities),
        pairs=tuple(pairs),
        objective_coeff=objective_coeff,
        tmax_coeff=tmax_coeff(problem, norm),
        travel_seconds=travel_seconds,
        max_travel_seconds=norm.max_travel_seconds,
        capacity=capacity,
        c3_requirements=c3_requirements,
        department_members={d: tuple(m) for d, m in department_members.items()},
        department_cap=problem.parameters.department_cap_limit,
        pinned=pinned,
        big_m=big_m(problem, len(pairs)),
        demote_c3=demote_c3,
    )


__all__ = ["build_model"]
