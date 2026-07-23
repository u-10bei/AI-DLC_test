"""Persist an AssignmentResult to U-03's skeleton tables (U04-H4).

U-03 created the assignment_results / constraint_violations / assignments tables;
U-04 owns their write logic. Reuses data_management's Core schema and the same
one-transaction, parameterised-query pattern (U03-H4). No PII is written beyond
what the tables already hold (assignments are staff/facility IDs).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Engine, insert

from data_management import schema
from shared_kernel import AssignmentResult


def save_assignment_result(
    engine: Engine, result: AssignmentResult, *, result_id: str, created_at: datetime
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(schema.assignment_results),
            {
                "id": result_id,
                "event_id": str(result.event_id),
                "objective_value": result.objective_value,
                "solver_status": result.solver_status.name,
                "created_at": created_at,
            },
        )
        if result.assignments:
            conn.execute(
                insert(schema.assignments),
                [
                    {
                        "event_id": str(a.event_id),
                        "staff_id": str(a.staff_id),
                        "facility_id": str(a.facility_id),
                        "is_pinned": a.is_pinned,
                    }
                    for a in result.assignments
                ],
            )
        if result.violations:
            conn.execute(
                insert(schema.constraint_violations),
                [
                    {
                        "id": f"{result_id}-{index}",
                        "result_id": result_id,
                        "constraint_id": violation.constraint_id,
                        "detail": violation.detail,
                    }
                    for index, violation in enumerate(result.violations)
                ],
            )


__all__ = ["save_assignment_result"]
