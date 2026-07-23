"""Entities.

All frozen, like the value objects. Changing an entity means building a new one
with ``dataclasses.replace``, which re-runs ``__post_init__`` and so re-checks
the invariant. Persistence adapters therefore cannot rely on ORM dirty-checking
(handoff U01-H21).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime

from .enums import (
    ALLOWED_EVENT_TRANSITIONS,
    EventStatus,
    EventType,
    JobType,
    Position,
    Qualification,
    ReasonCategory,
)
from .exceptions import (
    DuplicateQualificationRequirementError,
    InconsistentDeclarationError,
    InvalidStateTransitionError,
    QualificationRequirementExceedsHeadcountError,
)
from .identifiers import DepartmentId, EventId, FacilityId, SchoolDistrictId, StaffId
from .value_objects import Coordinates, QualificationRequirement

REDACTED = "<redacted>"


@dataclass(frozen=True, slots=True)
class Department:
    """A municipal department.

    Modelled as an entity rather than a string on Staff so that spelling drift
    ("危機管理課" vs "危機管理担当課") cannot split one department into two, and
    so that constraint C5's per-department cap has somewhere to live.
    """

    id: DepartmentId
    name: str
    concurrent_assignment_cap: int | None = None


@dataclass(frozen=True, slots=True)
class SchoolDistrict:
    """An elementary-school district.

    ``representative_point`` is the school's own location (assumption A-02). A
    district is an area, not a point, so distance calculations need a chosen
    representative; the school building is easy to source and sits near the
    centre of the residents' daily range.
    """

    id: SchoolDistrictId
    name: str
    representative_point: Coordinates


@dataclass(frozen=True, slots=True)
class Staff:
    """A municipal employee.

    ``name`` and ``residence_district_id`` are personal information. They must
    never reach a log (SECURITY-03, NFR-S02).

    Two layers guard that. Structurally, ``src/security/`` cannot import this
    module at all (.importlinter), so U-06 has no path to these fields. At
    runtime, ``__repr__`` redacts them, so a unit that carelessly writes
    ``logger.info("%s", staff)`` still emits nothing sensitive.
    """

    id: StaffId
    name: str
    department_id: DepartmentId
    job_type: JobType
    position: Position
    residence_district_id: SchoolDistrictId
    qualifications: frozenset[Qualification] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.name:
            raise InconsistentDeclarationError("staff name is empty", violated_rule="BR-06")

    def __repr__(self) -> str:
        return (
            f"Staff(id={self.id!r}, department_id={self.department_id!r}, "
            f"job_type={self.job_type.name}, position={self.position.name}, "
            f"qualifications={{{', '.join(sorted(q.name for q in self.qualifications))}}}, "
            f"name={REDACTED}, residence_district_id={REDACTED})"
        )

    __str__ = __repr__


@dataclass(frozen=True, slots=True)
class Facility:
    """A shelter or polling station. BR-03."""

    id: FacilityId
    name: str
    district_id: SchoolDistrictId
    required_headcount: int
    qualification_requirements: tuple[QualificationRequirement, ...] = ()

    def __post_init__(self) -> None:
        if self.required_headcount < 1:
            raise QualificationRequirementExceedsHeadcountError(
                "required_headcount must be >= 1",
                violated_rule="BR-03",
                facility_id=self.id,
            )

        seen: set[Qualification | Position | JobType] = set()
        for req in self.qualification_requirements:
            if req.requirement in seen:
                raise DuplicateQualificationRequirementError(
                    "the same requirement appears twice",
                    violated_rule="BR-03",
                    facility_id=self.id,
                )
            seen.add(req.requirement)

        # US-08: a facility needing 5 people cannot also need 6 managers.
        total = sum(req.required_count for req in self.qualification_requirements)
        if total > self.required_headcount:
            raise QualificationRequirementExceedsHeadcountError(
                "sum of qualification requirements exceeds required_headcount",
                violated_rule="BR-03",
                facility_id=self.id,
            )


@dataclass(frozen=True, slots=True)
class Event:
    """A disaster-shelter deployment, an election, or anything a coordinator registers.

    ``scheduled_date`` is the sole exception to storing times in UTC: it is a JST
    calendar date with no time component. Storing it as a UTC timestamp would
    shift the date across midnight.
    """

    id: EventId
    type: EventType
    name: str
    scheduled_date: date
    status: EventStatus = EventStatus.DRAFT

    def transition_to(self, target: EventStatus) -> Event:
        """Return a new Event in ``target``, or refuse.

        Preconditions that need the database -- "does this event have at least
        one facility?" -- belong to U-03's EventService. What is enforceable
        from the type alone is enforced here.
        """
        if target not in ALLOWED_EVENT_TRANSITIONS[self.status]:
            raise InvalidStateTransitionError(
                f"cannot transition from {self.status.name} to {target.name}",
                violated_rule="EventStatus",
                event_id=self.id,
            )
        return replace(self, status=target)

    def start_collecting_declarations(self) -> Event:
        return self.transition_to(EventStatus.COLLECTING_DECLARATIONS)

    def mark_optimized(self) -> Event:
        return self.transition_to(EventStatus.OPTIMIZED)

    def reopen_declarations(self) -> Event:
        """Go back to collecting declarations after an optimization ran (US-24)."""
        return self.transition_to(EventStatus.COLLECTING_DECLARATIONS)

    def confirm(self) -> Event:
        return self.transition_to(EventStatus.CONFIRMED)


@dataclass(frozen=True, slots=True)
class AvailabilityDeclaration:
    """One staff member's answer for one event. FR-02.7, BR-05.

    Availability is *not* an attribute of Staff. The same person is available for
    one event and unavailable for another, so it belongs to the (staff, event)
    pair. Re-declarations accumulate as history; ``effective_declaration_for``
    picks the one in force.

    ``reason_category`` is close to sensitive personal information -- it reveals
    leave, caregiving, or a health accommodation. It must not be written to the
    audit log (handoff U01-H22).
    """

    staff_id: StaffId
    event_id: EventId
    is_available: bool
    declared_at: datetime
    reason_category: ReasonCategory | None = None
    other_reason_note: str | None = None

    def __post_init__(self) -> None:
        if self.is_available and self.reason_category is not None:
            raise InconsistentDeclarationError(
                "available declaration carries a reason_category",
                violated_rule="BR-05",
                staff_id=self.staff_id,
                event_id=self.event_id,
            )
        if not self.is_available and self.reason_category is None:
            raise InconsistentDeclarationError(
                "unavailable declaration lacks a reason_category",
                violated_rule="BR-05",
                staff_id=self.staff_id,
                event_id=self.event_id,
            )
        if self.reason_category is ReasonCategory.OTHER and not self.other_reason_note:
            raise InconsistentDeclarationError(
                "reason_category OTHER requires other_reason_note",
                violated_rule="BR-05",
                staff_id=self.staff_id,
                event_id=self.event_id,
            )
        if self.reason_category is not ReasonCategory.OTHER and self.other_reason_note is not None:
            raise InconsistentDeclarationError(
                "other_reason_note is only valid with reason_category OTHER",
                violated_rule="BR-05",
                staff_id=self.staff_id,
                event_id=self.event_id,
            )


@dataclass(frozen=True, slots=True)
class Assignment:
    """One staff member placed at one facility for one event.

    Identity is ``(event_id, staff_id)``. INV-01 -- a person goes to at most one
    facility per event -- is therefore a property of the identifier, not a rule
    that has to be checked.
    """

    event_id: EventId
    staff_id: StaffId
    facility_id: FacilityId
    is_pinned: bool = False


__all__ = [
    "REDACTED",
    "Assignment",
    "AvailabilityDeclaration",
    "Department",
    "Event",
    "Facility",
    "SchoolDistrict",
    "Staff",
]
