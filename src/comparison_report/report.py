"""Comparison report types (U05-H5). No PII (SECURITY-03, BR-CMP11)."""

from __future__ import annotations

from dataclasses import dataclass

from shared_kernel import Assignment, AvailabilityDeclaration, EventId, HistoricalRecord


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    """Baseline vs optimised, aggregates only. Reductions may be negative (BR-CMP08)."""

    event_id: EventId
    baseline_time_seconds: int
    optimized_time_seconds: int
    time_reduction_seconds: int
    time_reduction_rate: float
    baseline_cost_yen: float
    optimized_cost_yen: float
    cost_reduction_yen: float
    cost_reduction_rate: float
    assigned_count: int
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ManualBaseline:
    """A coordinator-entered baseline for an event with no history (FR-05.1.6)."""

    event_id: EventId
    actual_assignments: tuple[Assignment, ...]
    availability_declarations: tuple[AvailabilityDeclaration, ...]

    def to_historical_record(self) -> HistoricalRecord:
        return HistoricalRecord(
            event_id=self.event_id,
            actual_assignments=self.actual_assignments,
            availability_declarations=self.availability_declarations,
        )


__all__ = ["ComparisonReport", "ManualBaseline"]
