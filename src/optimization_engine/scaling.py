"""Objective normalisation and integer scaling (DP-02).

CP-SAT is an integer solver: objective coefficients must be integers. The
Functional Design objective is a NORMALISED weighted sum (each term divided by a
representative scale so a coordinator's weights are meaningful), which is
floating point. This module turns it into integers by multiplying by a fixed
precision factor SCALE and rounding, and derives the integer big-M as a strict
upper bound on the scaled objective so INV-12 survives the rounding.

Normalisation constants (SCALE, and the representative scales) are module-level
here and externalised as configuration in production (NFR-M03, U04-H9).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from shared_kernel import Assignment, AssignmentProblem, FacilityId, StaffId

#: Fixed precision for integer scaling. 10^6 keeps rounding error below 1e-6 of a
#: normalised unit -- negligible. Externalised in production (NFR-M03, U04-H9).
SCALE = 1_000_000


@dataclass(frozen=True, slots=True)
class Normalisation:
    """Representative scales that make each objective term dimensionless in ~[0,1]."""

    n_time: float  # (total required headcount) x (max travel seconds)
    n_cost: float  # (total required headcount) x (max travel cost yen)
    n_time_single: float  # max travel seconds (for the minimax T_max term)
    max_travel_seconds: int


def compute_normalisation(problem: AssignmentProblem) -> Normalisation:
    metrics = list(problem.travel_matrix.values())
    max_t = max((m.time_seconds for m in metrics), default=0)
    max_c = max((m.cost_yen for m in metrics), default=0.0)
    total_required = sum(f.required_headcount for f in problem.facilities)
    total_required = max(total_required, 1)
    return Normalisation(
        n_time=float(total_required * max(max_t, 1)),
        n_cost=float(total_required * max(max_c, 1.0)),
        n_time_single=float(max(max_t, 1)),
        max_travel_seconds=max_t,
    )


def pair_objective_coeff(
    problem: AssignmentProblem, norm: Normalisation, staff_id: StaffId, facility_id: FacilityId
) -> int:
    """Integer objective coefficient for x_ij (time + cost terms)."""
    metrics = problem.travel_matrix[(staff_id, facility_id)]
    weights = problem.parameters.weights
    value = (
        weights.travel_time * (metrics.time_seconds / norm.n_time)
        + weights.travel_cost * (metrics.cost_yen / norm.n_cost)
    )
    return round(SCALE * value)


def tmax_coeff(problem: AssignmentProblem, norm: Normalisation) -> int:
    """Integer objective coefficient for the minimax T_max term."""
    return round(SCALE * problem.parameters.weights.inequity / norm.n_time_single)


def big_m(problem: AssignmentProblem, pair_count: int) -> int:
    """Integer C3-demotion penalty. Strict upper bound on the scaled objective + margin.

    Each normalised term is <= 1 by construction, so the un-scaled objective is at
    most (w_time + w_cost + w_inequity). big_m therefore exceeds the entire scaled
    objective range, guaranteeing that removing one C3 violation always outweighs
    any objective increase (INV-12, H-10). The pair-count margin absorbs rounding.
    """
    weights = problem.parameters.weights
    weight_sum = weights.travel_time + weights.travel_cost + weights.inequity
    return int(math.ceil(SCALE * weight_sum)) + pair_count + 2


def normalised_objective(problem: AssignmentProblem, assignments: tuple[Assignment, ...]) -> float:
    """The real (de-scaled, penalty-free) normalised objective for reporting.

    Recomputed from the assignments rather than read from the solver, so the value
    stored on AssignmentResult is always finite and non-negative (BR-07) and never
    includes the big-M penalty.
    """
    norm = compute_normalisation(problem)
    weights = problem.parameters.weights
    sum_t = 0
    sum_c = 0.0
    max_t = 0
    for assignment in assignments:
        metrics = problem.travel_matrix[(assignment.staff_id, assignment.facility_id)]
        sum_t += metrics.time_seconds
        sum_c += metrics.cost_yen
        max_t = max(max_t, metrics.time_seconds)
    return (
        weights.travel_time * (sum_t / norm.n_time)
        + weights.travel_cost * (sum_c / norm.n_cost)
        + weights.inequity * (max_t / norm.n_time_single)
    )


__all__ = [
    "SCALE",
    "Normalisation",
    "big_m",
    "compute_normalisation",
    "normalised_objective",
    "pair_objective_coeff",
    "tmax_coeff",
]
