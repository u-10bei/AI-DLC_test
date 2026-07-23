"""LC-04 ResultMapper: SolveOutcome -> AssignmentResult (BR-07 firewall, DP-05).

The objective value is RECOMPUTED from the assignments (scaling.normalised_objective)
rather than read from the solver, so it is always finite, non-negative and free of
the big-M penalty -- exactly what BR-07 requires. Constructing the AssignmentResult
re-runs its __post_init__, which refuses any C1/C2/C4/C5 violation, a bad objective
or a duplicate assignment: a solver bug stops here (fail closed, SECURITY-15).
"""

from __future__ import annotations

from datetime import datetime

from shared_kernel import AssignmentProblem, AssignmentResult

from .model import SolveOutcome
from .scaling import normalised_objective


def to_assignment_result(
    problem: AssignmentProblem, outcome: SolveOutcome, computed_at: datetime
) -> AssignmentResult:
    return AssignmentResult(
        event_id=problem.event.id,
        assignments=outcome.assignments,
        objective_value=normalised_objective(problem, outcome.assignments),
        optimality_gap=outcome.optimality_gap,
        solver_status=outcome.status,
        computed_at=computed_at,
        violations=outcome.c3_violations,
    )


__all__ = ["to_assignment_result"]
