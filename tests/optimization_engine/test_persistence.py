"""U04-H4: persisting an AssignmentResult to U-03's tables (integration).

Seeds the masters and the event through data_management, solves, saves the
result, and reads the rows back -- exercising the reuse of U-03's skeleton tables
across the unit boundary (optimization_engine -> data_management is allowed).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select

from data_management import create_all, create_db_engine, repositories, schema
from optimization_engine import OptimizationService, save_assignment_result
from shared_kernel import (
    AssignmentResult,
    Coordinates,
    Department,
    DepartmentId,
    Event,
    EventId,
    EventType,
    SchoolDistrict,
    SchoolDistrictId,
)

from .support import facility, make_staff, problem, travel

_NOW = datetime(2026, 7, 16, tzinfo=UTC)


def test_result_persists_to_u03_tables() -> None:
    engine = create_db_engine("sqlite://")
    create_all(engine)

    staff = (make_staff(1), make_staff(2), make_staff(3))
    with engine.begin() as conn:
        repositories.insert_departments(conn, [Department(id=DepartmentId("D1"), name="d")])
        repositories.insert_school_districts(
            conn,
            [SchoolDistrict(id=SchoolDistrictId("SD1"), name="sd", representative_point=Coordinates(35.0, 139.0))],
        )
        repositories.insert_staff(conn, staff)
        repositories.insert_facilities(conn, [facility("F1", 2)])
        repositories.insert_event(
            conn,
            Event(
                id=EventId("E1"),
                type=EventType.DISASTER_SHELTER_SUPPORT,
                name="e",
                scheduled_date=datetime(2026, 8, 1).date(),
            ),
        )

    metrics = {
        ("S1", "F1"): travel(600, 0.0),
        ("S2", "F1"): travel(1200, 300.0),
        ("S3", "F1"): travel(3600, 8000.0),
    }
    result = OptimizationService().optimize(problem(staff, (facility("F1", 2),), metrics), now=_NOW)
    assert isinstance(result, AssignmentResult)

    save_assignment_result(engine, result, result_id="R1", created_at=_NOW)

    with engine.connect() as conn:
        result_rows = conn.execute(
            select(func.count()).select_from(schema.assignment_results)
        ).scalar_one()
        assignment_rows = conn.execute(
            select(func.count()).select_from(schema.assignments)
        ).scalar_one()
    assert result_rows == 1
    assert assignment_rows == 2
