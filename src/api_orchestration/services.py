"""The wired dependency bundle the routers use (LC-05's product).

Everything here was assembled by the composition root: U-03's services, U-04's
solver, U-06's gates, plus the small amount of persistence U-07 owns itself
(sessions, the job queue, assignment reads/writes).

`clock` is injected rather than calling datetime.now() inside routes, so tests are
deterministic — the same discipline U-04 and U-06 follow.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import Engine, delete, insert, select

from data_management import (
    AvailabilityService,
    EventService,
    MasterDataService,
    repositories,
    schema,
)
from security import AuditAction, AuditEvent, AuditService, Authenticator, Authorizer, Principal
from shared_kernel import (
    Assignment,
    AssignmentResult,
    ConstraintViolation,
    EventId,
    FacilityId,
    SolverStatus,
    StaffId,
)

from . import dto
from .config import AppConfig
from .jobs import OptimizationJob


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Services:
    engine: Engine
    config: AppConfig
    authenticator: Authenticator
    authorizer: Authorizer
    audit: AuditService
    events: EventService
    master: MasterDataService
    availability: AvailabilityService
    #: CSV export with U-06's sanitiser already injected (U06-H3, MU-02).
    export_staff_csv: Callable[[], bytes]
    export_facilities_csv: Callable[[], bytes]
    export_districts_csv: Callable[[], bytes]
    clock: Callable[[], datetime] = _utc_now

    # --- assignments (U-07 owns these reads/writes; U-03 owns the schema) ----

    def load_assignments(self, event_id: EventId) -> tuple[Assignment, ...]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(schema.assignments).where(schema.assignments.c.event_id == str(event_id))
            ).all()
        return tuple(
            Assignment(
                event_id=event_id,
                staff_id=StaffId(str(r._mapping["staff_id"])),
                facility_id=FacilityId(str(r._mapping["facility_id"])),
                is_pinned=bool(r._mapping["is_pinned"]),
            )
            for r in rows
        )

    def save_assignments(self, event_id: EventId, assignments: tuple[Assignment, ...]) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                delete(schema.assignments).where(schema.assignments.c.event_id == str(event_id))
            )
            if assignments:
                conn.execute(
                    insert(schema.assignments),
                    [
                        {
                            "event_id": str(a.event_id),
                            "staff_id": str(a.staff_id),
                            "facility_id": str(a.facility_id),
                            "is_pinned": a.is_pinned,
                        }
                        for a in assignments
                    ],
                )

    def load_result(self, job: OptimizationJob) -> AssignmentResult | None:
        if job.result_id is None:
            return None
        with self.engine.connect() as conn:
            row = conn.execute(
                select(schema.assignment_results).where(
                    schema.assignment_results.c.id == job.result_id
                )
            ).first()
            violation_rows = conn.execute(
                select(schema.constraint_violations).where(
                    schema.constraint_violations.c.result_id == job.result_id
                )
            ).all()
        if row is None:
            return None
        mapping = row._mapping
        violations = tuple(
            ConstraintViolation(
                constraint_id="C3",  # only C3 is ever demotable (BR-07)
                detail=str(v._mapping["detail"] or ""),
            )
            for v in violation_rows
        )
        return AssignmentResult(
            event_id=job.event_id,
            assignments=self.load_assignments(job.event_id),
            objective_value=float(mapping["objective_value"] or 0.0),
            optimality_gap=0.0,
            solver_status=SolverStatus(str(mapping["solver_status"] or "OPTIMAL")),
            computed_at=self.clock(),
            violations=violations,
        )

    # --- audit --------------------------------------------------------------

    def audit_assignment_change(
        self,
        principal: Principal,
        event_id: EventId,
        patch: dto.AssignmentPatchRequest,
        before: tuple[Assignment, ...],
    ) -> None:
        """FR-07.1 / US-03: who, when, what, before -> after. IDs only, no PII."""
        previous = next(
            (a for a in before if a.staff_id == StaffId(patch.staff_id)), None
        )
        self.audit.record(
            AuditEvent(
                timestamp=self.clock(),
                action=AuditAction.ASSIGNMENT_CHANGED,
                actor=principal.user_id,
                event_id=event_id,
                staff_id=StaffId(patch.staff_id),
                before=None if previous is None else {"facility_id": str(previous.facility_id)},
                after={"facility_id": patch.facility_id},
            )
        )

    # --- convenience --------------------------------------------------------

    def all_staff_ids(self) -> set[str]:
        with self.engine.connect() as conn:
            return repositories.existing_staff_ids(conn)


__all__ = ["Services"]
