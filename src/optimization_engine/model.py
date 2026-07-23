"""Abstract MILP model and solve outcome — product-agnostic (DP-03).

These types carry everything a solver needs, expressed without any reference to a
particular solver library. The CpSatAdapter (the only ortools importer) consumes
a MilpModel and produces a SolveOutcome. ModelBuilder, InfeasibilityDiagnoser and
ResultMapper work only on these abstractions, so they are unit-testable without a
solver and the solver product can be swapped by replacing one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared_kernel import (
    Assignment,
    ConstraintViolation,
    DepartmentId,
    EventId,
    FacilityId,
    SolverStatus,
    StaffId,
)

Pair = tuple[StaffId, FacilityId]


@dataclass(frozen=True, slots=True)
class C3Requirement:
    """A facility needs ``required_count`` people from ``eligible_staff`` (C3)."""

    facility_id: FacilityId
    eligible_staff: frozenset[StaffId]
    required_count: int


@dataclass(frozen=True, slots=True)
class MilpModel:
    """The generalised assignment problem as an abstract integer program."""

    event_id: EventId
    staff_ids: tuple[StaffId, ...]
    facility_ids: tuple[FacilityId, ...]
    pairs: tuple[Pair, ...]  # every (staff, facility) decision variable
    objective_coeff: dict[Pair, int]  # integer-scaled time+cost coefficient
    tmax_coeff: int  # integer-scaled minimax coefficient (0 disables T_max)
    travel_seconds: dict[Pair, int]  # t_ij, for the T_max constraints
    max_travel_seconds: int
    capacity: dict[FacilityId, int]  # C1 exact headcount
    c3_requirements: tuple[C3Requirement, ...]  # C3
    department_members: dict[DepartmentId, tuple[StaffId, ...]]  # C5
    department_cap: int  # C5 uniform cap (OptimizationParameters.department_cap_limit)
    pinned: frozenset[Pair]  # variables fixed to 1
    big_m: int  # C3-demotion penalty (only used when demote_c3)
    demote_c3: bool  # when True, C3 is a soft constraint with slack penalised by big_m


@dataclass(frozen=True, slots=True)
class SolveOutcome:
    """A solver's raw result, still product-agnostic."""

    feasible: bool
    assignments: tuple[Assignment, ...]
    objective_value: float
    optimality_gap: float
    status: SolverStatus
    c3_violations: tuple[ConstraintViolation, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class ServiceHistory:
    """History-levelling hook (FR-04.4, Q6). Disabled by default (weight 0).

    Wiring past service counts to the objective is future work (U04-H3); U-04 must
    not depend on U-05, so this stays an inert extension point in the PoC.
    """

    past_service_counts: dict[StaffId, int] = field(default_factory=dict)
    weight: float = 0.0


__all__ = [
    "C3Requirement",
    "MilpModel",
    "Pair",
    "ServiceHistory",
    "SolveOutcome",
]
