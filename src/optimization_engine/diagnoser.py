"""LC-03 InfeasibilityDiagnoser (Q4 decision tree, resolves H-9).

Classifies why a problem is infeasible, having already established (by the
service) that a solve with C3 removed is still infeasible. The distinction that
needs data is TOTAL_SHORTAGE vs a C2/C5 interaction; that is what this module
decides. The C3-only case is handled by the service re-solving with demotion, so
it never reaches here. Diagnoses carry facility/constraint IDs only (SECURITY-03).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from shared_kernel import AssignmentProblem, ConstraintId, FacilityId


class InfeasibilityCause(Enum):
    TOTAL_SHORTAGE = "TOTAL_SHORTAGE"  # too few available staff; C1 is NOT relaxed
    C3_DEMOTED = "C3_DEMOTED"  # C3 was the only cause; solved with demotion
    HARD_CONSTRAINT = "HARD_CONSTRAINT"  # C2/C5 interaction; not demotable


@dataclass(frozen=True, slots=True)
class InfeasibilityDiagnosis:
    """Why a problem could not be solved, and what the coordinator should act on."""

    cause: InfeasibilityCause
    shortage_count: int | None = None
    affected_facilities: tuple[FacilityId, ...] = ()
    blocking_constraints: tuple[ConstraintId, ...] = field(default=())


def total_shortage(problem: AssignmentProblem) -> int:
    """Required headcount minus available staff (0 if there is no shortage)."""
    required = sum(f.required_headcount for f in problem.facilities)
    available = len(problem.available_staff)
    return max(0, required - available)


def classify_after_relaxed_infeasible(problem: AssignmentProblem) -> InfeasibilityDiagnosis:
    """Diagnose when even the C3-relaxed model is infeasible (BR-OPT08/09).

    A total shortage means C1 (exact headcount) cannot be met with the available
    staff; C1 is never relaxed (BR-OPT09) -- the coordinator gathers more
    declarations and re-optimises. Otherwise the cause is a C2/C5 interaction,
    which is never demoted (BR-OPT10).
    """
    shortage = total_shortage(problem)
    if shortage > 0:
        return InfeasibilityDiagnosis(
            cause=InfeasibilityCause.TOTAL_SHORTAGE,
            shortage_count=shortage,
            affected_facilities=tuple(f.id for f in problem.facilities),
        )
    return InfeasibilityDiagnosis(
        cause=InfeasibilityCause.HARD_CONSTRAINT,
        blocking_constraints=("C1", "C2", "C5"),
    )


__all__ = [
    "InfeasibilityCause",
    "InfeasibilityDiagnosis",
    "classify_after_relaxed_infeasible",
    "total_shortage",
]
