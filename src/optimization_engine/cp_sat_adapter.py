"""LC-02 CpSatAdapter — the ONLY module that imports ortools (DP-03).

Translates an abstract MilpModel into a CP-SAT CpModel using native constraint
helpers (DP-01), solves within the time limit, and returns a product-agnostic
SolveOutcome. Reproducibility and PII safety per DP-06: fixed seed and worker
count, ``log_search_progress`` off, variable names carry IDs only.

This is the isolation boundary for the untyped solver library; the mypy strict
relaxation for this one module (pyproject) is scoped here on purpose.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from shared_kernel import Assignment, ConstraintViolation, SolverStatus

from .model import MilpModel, SolveOutcome


def _optimality_gap(objective: float, bound: float) -> float:
    if objective == 0.0:
        return 0.0
    gap = abs(objective - bound) / abs(objective)
    return min(1.0, max(0.0, gap))


class CpSatAdapter:
    """SolverPort backed by OR-Tools CP-SAT."""

    def solve(
        self,
        model: MilpModel,
        *,
        time_limit_seconds: int,
        random_seed: int,
        num_workers: int,
    ) -> SolveOutcome:
        cp = cp_model.CpModel()

        # Decision variables x_ij. Names carry IDs only (SECURITY-03).
        x = {pair: cp.NewBoolVar(f"x_{pair[0]}_{pair[1]}") for pair in model.pairs}

        # Pinned assignments fixed to 1 (BR-OPT13).
        for pair in model.pinned:
            if pair in x:
                cp.Add(x[pair] == 1)

        # C1 exact headcount per facility.
        for facility_id in model.facility_ids:
            terms = [x[pair] for pair in model.pairs if pair[1] == facility_id]
            cp.Add(sum(terms) == model.capacity[facility_id])

        # C2 at most one facility per staff member.
        for staff_id in model.staff_ids:
            terms = [x[pair] for pair in model.pairs if pair[0] == staff_id]
            cp.AddAtMostOne(terms)

        # C3 qualification requirements (soft with slack when demoted).
        slacks: list[tuple[ConstraintViolation, cp_model.IntVar]] = []
        for index, req in enumerate(model.c3_requirements):
            terms = [
                x[(staff_id, req.facility_id)]
                for staff_id in req.eligible_staff
                if (staff_id, req.facility_id) in x
            ]
            if model.demote_c3:
                slack = cp.NewIntVar(0, req.required_count, f"s_{req.facility_id}_{index}")
                cp.Add(sum(terms) + slack >= req.required_count)
                slacks.append(
                    (
                        ConstraintViolation(
                            constraint_id="C3",
                            detail="qualification shortfall",
                            facility_id=req.facility_id,
                        ),
                        slack,
                    )
                )
            else:
                cp.Add(sum(terms) >= req.required_count)

        # C5 department concurrency cap.
        for members in model.department_members.values():
            member_set = set(members)
            terms = [x[pair] for pair in model.pairs if pair[0] in member_set]
            if terms:
                cp.Add(sum(terms) <= model.department_cap)

        # Objective: integer-scaled time+cost, plus minimax T_max, plus C3 penalty.
        objective = [model.objective_coeff[pair] * x[pair] for pair in model.pairs]
        if model.tmax_coeff > 0 and model.max_travel_seconds > 0:
            t_max = cp.NewIntVar(0, model.max_travel_seconds, "T_max")
            for pair in model.pairs:
                cp.Add(t_max >= model.travel_seconds[pair]).OnlyEnforceIf(x[pair])
            objective.append(model.tmax_coeff * t_max)
        for _violation, slack in slacks:
            objective.append(model.big_m * slack)
        cp.Minimize(sum(objective))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit_seconds)
        solver.parameters.random_seed = random_seed
        solver.parameters.num_search_workers = num_workers
        solver.parameters.log_search_progress = False

        status = solver.Solve(cp)
        status_name = solver.StatusName(status)
        if status_name not in ("OPTIMAL", "FEASIBLE"):
            return SolveOutcome(
                feasible=False,
                assignments=(),
                objective_value=0.0,
                optimality_gap=1.0,
                status=SolverStatus.CANCELLED,
            )

        assignments = tuple(
            Assignment(
                event_id=model.event_id,
                staff_id=pair[0],
                facility_id=pair[1],
                is_pinned=pair in model.pinned,
            )
            for pair in model.pairs
            if solver.Value(x[pair]) == 1
        )

        violations = tuple(
            violation for violation, slack in slacks if solver.Value(slack) > 0
        )

        objective_value = solver.ObjectiveValue()
        is_optimal = status_name == "OPTIMAL"
        gap = (
            0.0 if is_optimal else _optimality_gap(objective_value, solver.BestObjectiveBound())
        )
        solver_status = SolverStatus.OPTIMAL if is_optimal else SolverStatus.TIME_LIMIT_REACHED
        return SolveOutcome(
            feasible=True,
            assignments=assignments,
            objective_value=objective_value,
            optimality_gap=gap,
            status=solver_status,
            c3_violations=violations,
        )


__all__ = ["CpSatAdapter"]
