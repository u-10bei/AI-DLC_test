"""Hard-constraint checking of a given assignment set (U07-H1).

U-07 needs this for FR-06.3: after a coordinator edits an assignment by hand, the
C1..C5 violations must be reported immediately. Reimplementing that check in U-07
would put two interpretations of the same constraints in two units, and they would
drift. U-04 owns the constraints, so U-04 answers the question.

The same core serves two callers with different expectations:

  * a COMPLETE assignment must fill each facility exactly (C1 as equality) and
    satisfy the qualification requirements (C3);
  * a set of PINS is partial by definition, so it may only be checked for not
    already exceeding a facility's headcount, and C3 cannot be judged yet.

Hence the two flags rather than two copies.
"""

from __future__ import annotations

from collections import Counter

from shared_kernel import (
    Assignment,
    AssignmentProblem,
    ConstraintViolation,
    DepartmentId,
    FacilityId,
    JobType,
    Position,
    Qualification,
    Staff,
    StaffId,
)


def _is_eligible(staff: Staff, requirement: Qualification | Position | JobType) -> bool:
    if isinstance(requirement, Qualification):
        return requirement in staff.qualifications
    if isinstance(requirement, Position):
        return staff.position is requirement
    return staff.job_type is requirement


def check_assignments(
    problem: AssignmentProblem,
    assignments: tuple[Assignment, ...],
    *,
    require_exact_capacity: bool,
    check_qualifications: bool,
) -> tuple[ConstraintViolation, ...]:
    """Return every hard-constraint violation in ``assignments``. Empty means valid."""
    violations: list[ConstraintViolation] = []
    available: dict[StaffId, Staff] = {s.id: s for s in problem.available_staff}
    facilities = {f.id: f for f in problem.facilities}

    # C4: only staff who declared availability may be assigned.
    for assignment in assignments:
        if assignment.staff_id not in available:
            violations.append(
                ConstraintViolation(
                    constraint_id="C4",
                    detail="staff is not available for this event",
                    staff_id=assignment.staff_id,
                )
            )
        if assignment.facility_id not in facilities:
            violations.append(
                ConstraintViolation(
                    constraint_id="C1",
                    detail="facility does not belong to this event",
                    facility_id=assignment.facility_id,
                )
            )

    # C2: at most one facility per staff member.
    per_staff: Counter[StaffId] = Counter(a.staff_id for a in assignments)
    for staff_id, count in per_staff.items():
        if count > 1:
            violations.append(
                ConstraintViolation(
                    constraint_id="C2",
                    detail="staff assigned to more than one facility",
                    staff_id=staff_id,
                )
            )

    # C1: headcount. Exact for a complete assignment, an upper bound for pins.
    per_facility: Counter[FacilityId] = Counter(a.facility_id for a in assignments)
    for facility in problem.facilities:
        count = per_facility[facility.id]
        if count > facility.required_headcount:
            violations.append(
                ConstraintViolation(
                    constraint_id="C1",
                    detail=f"assigned {count} exceeds headcount {facility.required_headcount}",
                    facility_id=facility.id,
                )
            )
        elif require_exact_capacity and count < facility.required_headcount:
            violations.append(
                ConstraintViolation(
                    constraint_id="C1",
                    detail=f"assigned {count} is below headcount {facility.required_headcount}",
                    facility_id=facility.id,
                )
            )

    # C5: department concurrency cap.
    cap = problem.parameters.department_cap_limit
    per_department: Counter[DepartmentId] = Counter(
        available[a.staff_id].department_id for a in assignments if a.staff_id in available
    )
    for _department_id, count in per_department.items():
        if count > cap:
            violations.append(
                ConstraintViolation(
                    constraint_id="C5",
                    detail=f"{count} assigned from one department exceeds the cap {cap}",
                )
            )

    # C3: qualification requirements. Only meaningful for a complete assignment.
    if check_qualifications:
        for facility in problem.facilities:
            assigned = [
                available[a.staff_id]
                for a in assignments
                if a.facility_id == facility.id and a.staff_id in available
            ]
            for requirement in facility.qualification_requirements:
                matching = sum(1 for s in assigned if _is_eligible(s, requirement.requirement))
                if matching < requirement.required_count:
                    violations.append(
                        ConstraintViolation(
                            constraint_id="C3",
                            detail=(
                                f"{matching} of {requirement.required_count} required "
                                f"{requirement.requirement.name}"
                            ),
                            facility_id=facility.id,
                        )
                    )

    return tuple(violations)


def validate_assignments(
    problem: AssignmentProblem, assignments: tuple[Assignment, ...]
) -> tuple[ConstraintViolation, ...]:
    """Every C1..C5 violation of a COMPLETE assignment set (FR-06.3, U07-H1).

    Empty tuple means the assignment satisfies every hard constraint. U-07 calls
    this after a manual edit so the coordinator is warned immediately.
    """
    return check_assignments(
        problem, assignments, require_exact_capacity=True, check_qualifications=True
    )


__all__ = ["check_assignments", "validate_assignments"]
