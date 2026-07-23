"""U-04 optimization-engine — the generalised assignment problem, solved.

Formulates the assignment problem as a MILP and solves it with OR-Tools CP-SAT
(H-3). Depends on U-01/U-02/U-03. ``ortools`` is confined to ``cp_sat_adapter``
(DP-03), so the rest of the unit is solver-product-agnostic and unit-testable
against the SolverPort abstraction.

Layers:
  * scaling      — normalisation + integer scaling of the objective (DP-02)
  * model        — abstract MilpModel / SolveOutcome
  * builder      — AssignmentProblem -> MilpModel (pure)
  * solver_port  — the SolverPort contract
  * cp_sat_adapter — the CP-SAT implementation (only ortools importer)
  * diagnoser    — the infeasibility decision tree (H-9)
  * result_mapper — SolveOutcome -> AssignmentResult (BR-07)
  * service      — OptimizationService (orchestration, pin validation, time limit)
  * repository   — persist results to U-03's tables (U04-H4)
"""

from __future__ import annotations

from .diagnoser import InfeasibilityCause, InfeasibilityDiagnosis, total_shortage
from .exceptions import ModelConstructionError, PinnedAssignmentInfeasibleError
from .model import MilpModel, ServiceHistory, SolveOutcome
from .repository import save_assignment_result
from .service import OptimizationService
from .solver_port import SolverPort
from .validation import check_assignments, validate_assignments

__all__ = [
    "InfeasibilityCause",
    "InfeasibilityDiagnosis",
    "MilpModel",
    "ModelConstructionError",
    "OptimizationService",
    "PinnedAssignmentInfeasibleError",
    "ServiceHistory",
    "SolveOutcome",
    "SolverPort",
    "check_assignments",
    "save_assignment_result",
    "total_shortage",
    "validate_assignments",
]
