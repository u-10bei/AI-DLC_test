"""LC-03 ComparisonService: orchestrate the baseline comparison (DP-04/05).

Builds the replay, optimises via U-04, evaluates both the actual and optimised
assignments on the SAME metrics, and reports the reductions. fail closed: an
infeasible replay returns U-04's InfeasibilityDiagnosis rather than a fabricated
report (BR-CMP09).
"""

from __future__ import annotations

from datetime import datetime

from optimization_engine import InfeasibilityDiagnosis, OptimizationService
from shared_kernel import Event, HistoricalRecord, OptimizationParameters, TravelParameters

from .evaluator import evaluate_totals
from .metrics import Master, make_metrics_for
from .replay import build_replay
from .report import ComparisonReport


def _rate(reduction: float, baseline: float) -> float:
    """reduction / baseline, guarding a zero baseline (BR-CMP07)."""
    return reduction / baseline if baseline != 0 else 0.0


class ComparisonService:
    def __init__(self, optimizer: OptimizationService | None = None) -> None:
        self._optimizer = optimizer if optimizer is not None else OptimizationService()

    def compare(
        self,
        record: HistoricalRecord,
        event: Event,
        master: Master,
        *,
        optimization_parameters: OptimizationParameters,
        travel_parameters: TravelParameters,
        now: datetime | None = None,
    ) -> ComparisonReport | InfeasibilityDiagnosis:
        metrics_for = make_metrics_for(master, travel_parameters)
        problem = build_replay(record, event, master, optimization_parameters, metrics_for)

        result = self._optimizer.optimize(problem, now=now)
        if isinstance(result, InfeasibilityDiagnosis):
            return result  # fail closed: do not fabricate a report

        baseline_time, baseline_cost = evaluate_totals(record.actual_assignments, metrics_for)
        optimized_time, optimized_cost = evaluate_totals(result.assignments, metrics_for)

        # A-10 note: some actually-assigned staff may lack an availability declaration,
        # so the candidate set is narrower and the reduction reads conservatively.
        available_ids = {d.staff_id for d in record.availability_declarations if d.is_available}
        actual_ids = {a.staff_id for a in record.actual_assignments}
        note = (
            "過去の従事可否申告が一部欠落しているため、削減効果は控えめに出る可能性があります (A-10)"
            if actual_ids - available_ids
            else None
        )

        time_reduction = baseline_time - optimized_time
        cost_reduction = baseline_cost - optimized_cost
        return ComparisonReport(
            event_id=record.event_id,
            baseline_time_seconds=baseline_time,
            optimized_time_seconds=optimized_time,
            time_reduction_seconds=time_reduction,
            time_reduction_rate=_rate(float(time_reduction), float(baseline_time)),
            baseline_cost_yen=baseline_cost,
            optimized_cost_yen=optimized_cost,
            cost_reduction_yen=cost_reduction,
            cost_reduction_rate=_rate(cost_reduction, baseline_cost),
            assigned_count=len(result.assignments),
            note=note,
        )


__all__ = ["ComparisonService"]
