"""LC-05 HistoricalRepository: ingest past-event actuals (U05-H2, US-26).

Parses a past event's actual assignments from CSV (reusing U-03's parser) and
records a marker row in U-03's historical_records skeleton table. Full-detail
persistence of every historical assignment/declaration needs a schema extension
(historical_assignments / historical_declarations), deferred to a later migration
(U05-H6); the PoC comparison flow works from an in-memory HistoricalRecord.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Engine, insert

from data_management import schema
from data_management.csv_codec import CsvImportError, RowError, parse_csv
from shared_kernel import Assignment, EventId, FacilityId, StaffId

_ASSIGNMENT_COLUMNS = ("職員ID", "施設ID")


def parse_historical_assignments(event_id: EventId, raw: bytes) -> tuple[Assignment, ...]:
    """Parse a past event's actual assignments (職員ID, 施設ID) into domain objects."""
    parsed = parse_csv(raw, required_columns=_ASSIGNMENT_COLUMNS)
    errors: list[RowError] = []
    assignments: list[Assignment] = []
    seen: set[str] = set()
    for line, row in enumerate(parsed.rows, start=2):
        staff_id = row["職員ID"]
        if staff_id in seen:
            errors.append(RowError(line, f"duplicate 職員ID {staff_id}"))
            continue
        seen.add(staff_id)
        assignments.append(
            Assignment(
                event_id=event_id,
                staff_id=StaffId(staff_id),
                facility_id=FacilityId(row["施設ID"]),
            )
        )
    if errors:
        raise CsvImportError(errors)
    return tuple(assignments)


def save_historical_marker(
    engine: Engine, *, record_id: str, event_id: EventId, recorded_at: datetime
) -> None:
    """Record that a historical baseline exists for an event (U-03 skeleton table)."""
    with engine.begin() as conn:
        conn.execute(
            insert(schema.historical_records),
            {"id": record_id, "event_id": str(event_id), "recorded_at": recorded_at},
        )


__all__ = ["parse_historical_assignments", "save_historical_marker"]
