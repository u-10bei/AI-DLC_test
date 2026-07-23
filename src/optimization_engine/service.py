"""LC-05 OptimizationService: orchestration (DP-04/05).

Owns the staged-solve decision tree (Q4), pinned-assignment pre-validation (Q7),
and the time limit. Depends on the abstract SolverPort; the default is CpSatAdapter
but a test can inject any solver. Each staged solve gets its own budget (the
configured limit); the relaxed and demoted solves run only on infeasibility, so
the worst-case wall-clock is 3x the limit (documented, DP-04).
"""

from __future__ import annotations

from datetime import UTC, datetime

from shared_kernel import AssignmentProblem, AssignmentResult

from .builder import build_model
from .cp_sat_adapter import CpSatAdapter
from .diagnoser import InfeasibilityDiagnosis, classify_after_relaxed_infeasible
from .exceptions import PinnedAssignmentInfeasibleError
from .model import MilpModel, ServiceHistory, SolveOutcome
from .result_mapper import to_assignment_result
from .solver_port import SolverPort
from .validation import check_assignments

#: Single search worker: matches the single-worker deployment (A-07) and makes the
#: solve reproducible for OPTIMAL / run-to-completion results (DP-06, NFR-U04-R03).
DEFAULT_NUM_WORKERS = 1


class OptimizationService:
    def __init__(self, solver: SolverPort | None = None, *, num_workers: int = DEFAULT_NUM_WORKERS):
        self._solver: SolverPort = solver if solver is not None else CpSatAdapter()
        self._num_workers = num_workers

    def optimize(
        self,
        problem: AssignmentProblem,
        *,
        history: ServiceHistory | None = None,
        now: datetime | None = None,
    ) -> AssignmentResult | InfeasibilityDiagnosis:
        del history  # inert hook in the PoC (Q6); wiring is future work (U04-H3)
        computed_at = now if now is not None else datetime.now(UTC)
        self._validate_pins(problem)

        limit = problem.parameters.time_limit_seconds
        seed = problem.parameters.random_seed

        outcome = self._solve(build_model(problem), limit, seed)
        if outcome.feasible:
            return to_assignment_result(problem, outcome, computed_at)

        # Infeasible: is C3 the only cause? Solve without C3 (BR-OPT08).
        relaxed = self._solve(build_model(problem, include_c3=False), limit, seed)
        if relaxed.feasible:
            demoted = self._solve(build_model(problem, demote_c3=True), limit, seed)
            if demoted.feasible:
                return to_assignment_result(problem, demoted, computed_at)

        # Even the relaxed model is infeasible: total shortage or a C2/C5 interaction.
        return classify_after_relaxed_infeasible(problem)

    def _solve(self, model: MilpModel, limit: int, seed: int) -> SolveOutcome:
        return self._solver.solve(
            model, time_limit_seconds=limit, random_seed=seed, num_workers=self._num_workers
        )

    def _validate_pins(self, problem: AssignmentProblem) -> None:
        pins = problem.pinned_assignments
        if not pins:
            return
        # Pins are a PARTIAL assignment: a facility may legitimately be under its
        # headcount and C3 cannot be judged yet. The same checker serves the
        # complete-assignment case (validation.validate_assignments) with the
        # flags flipped, so the constraints are interpreted in exactly one place.
        violations = check_assignments(
            problem, pins, require_exact_capacity=False, check_qualifications=False
        )
        if violations:
            first = violations[0]
            raise PinnedAssignmentInfeasibleError(
                f"pinned assignments violate {first.constraint_id}: {first.detail}",
                violated_rule=first.constraint_id,
                staff_id=first.staff_id,
                facility_id=first.facility_id,
            )


__all__ = ["DEFAULT_NUM_WORKERS", "OptimizationService"]
