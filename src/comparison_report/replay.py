"""LC-01 ReplayBuilder: HistoricalRecord + current master -> AssignmentProblem.

Per FR-05.1.2-1.5: each facility's headcount is the number actually assigned
there; the candidate staff are those who declared availability; residence /
department / qualifications come from the CURRENT master (A-09). The travel matrix
uses the shared metrics_for (DP-01) so the replay and the baseline are measured
identically.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

from shared_kernel import (
    AssignmentProblem,
    Event,
    FacilityId,
    HistoricalRecord,
    OptimizationParameters,
    Staff,
    StaffId,
    TravelMetrics,
)

from .metrics import Master, MetricsFor


def build_replay(
    record: HistoricalRecord,
    event: Event,
    master: Master,
    optimization_parameters: OptimizationParameters,
    metrics_for: MetricsFor,
) -> AssignmentProblem:
    # (1) facility headcount = actual assigned count (FR-05.1.2)
    counts: Counter[FacilityId] = Counter(a.facility_id for a in record.actual_assignments)
    facilities = tuple(
        replace(master.facilities_by_id[facility_id], required_headcount=count)
        for facility_id, count in counts.items()
        if facility_id in master.facilities_by_id
    )

    # (2) candidate staff = those who declared available (FR-05.1.3), from current master
    available_ids = {
        d.staff_id for d in record.availability_declarations if d.is_available
    }
    available: tuple[Staff, ...] = tuple(
        master.staff_by_id[staff_id]
        for staff_id in available_ids
        if staff_id in master.staff_by_id
    )

    # (3) travel matrix via the shared metrics_for (DP-01)
    travel_matrix: dict[tuple[StaffId, FacilityId], TravelMetrics] = {
        (member.id, facility.id): metrics_for(member.id, facility.id)
        for member in available
        for facility in facilities
    }

    return AssignmentProblem(
        event=event,
        facilities=facilities,
        available_staff=available,
        travel_matrix=travel_matrix,
        parameters=optimization_parameters,
    )


__all__ = ["build_replay"]
