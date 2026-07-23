"""LC-02 BaselineEvaluator: score assignments on the shared metrics (DP-01/03).

Totals use the same metrics_for as the replay (FR-05.1.4). The objective-dominance
check reuses U-04's normalised_objective so U-05 never diverges from the objective
the optimiser actually minimised (P-CMP03, U05-H4).
"""

from __future__ import annotations

from optimization_engine.scaling import normalised_objective
from shared_kernel import Assignment, AssignmentProblem

from .metrics import MetricsFor


def evaluate_totals(
    assignments: tuple[Assignment, ...], metrics_for: MetricsFor
) -> tuple[int, float]:
    """Total travel time (seconds) and cost (yen) for a set of assignments."""
    total_time = 0
    total_cost = 0.0
    for assignment in assignments:
        metrics = metrics_for(assignment.staff_id, assignment.facility_id)
        total_time += metrics.time_seconds
        total_cost += metrics.cost_yen
    return total_time, total_cost


def objective_of(problem: AssignmentProblem, assignments: tuple[Assignment, ...]) -> float:
    """The normalised objective (U-04) for these assignments in this problem."""
    return normalised_objective(problem, assignments)


__all__ = ["evaluate_totals", "objective_of"]
