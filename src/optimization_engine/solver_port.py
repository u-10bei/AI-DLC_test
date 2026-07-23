"""SolverPort — the abstract solve contract (DP-03).

U-04 defines this; CpSatAdapter implements it. Dependency inversion keeps ortools
out of the core: OptimizationService and InfeasibilityDiagnoser depend on this
Protocol, never on a concrete solver.
"""

from __future__ import annotations

from typing import Protocol

from .model import MilpModel, SolveOutcome


class SolverPort(Protocol):
    """Solve a MilpModel within a time limit, reproducibly."""

    def solve(
        self,
        model: MilpModel,
        *,
        time_limit_seconds: int,
        random_seed: int,
        num_workers: int,
    ) -> SolveOutcome:
        """Return the best solution found, its status and optimality gap.

        ``random_seed`` and ``num_workers`` are fixed by the caller for
        reproducibility (NFR-U04-R03). A solver must not emit PII: variable names
        carry IDs only and search logging is off (DP-06).
        """
        ...


__all__ = ["SolverPort"]
