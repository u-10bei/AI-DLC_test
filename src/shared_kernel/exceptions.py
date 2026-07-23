"""Domain exception hierarchy.

Every exception carries its debugging context as *structured attributes*, never
inside the message string. This is what lets the global error handler in U-07
write the context to a structured log while returning a generic message to the
user (SECURITY-09).

CRITICAL (SECURITY-03): neither the attributes nor the message may contain a
staff member's name or residence school district. Staff IDs only.

    Correct:  InconsistentDeclarationError(staff_id="S001", event_id="E001", ...)
    Wrong:    InconsistentDeclarationError("鈴木太郎(第三小学校区)の申告が不整合です")
"""

from __future__ import annotations

from .identifiers import EventId, FacilityId, StaffId


class DomainError(Exception):
    """Base class for every rule violation detected inside the domain layer.

    Raised by ``__post_init__`` when a value or entity would violate an
    invariant. Construction is refused; no partially-built object escapes
    (SECURITY-15, fail closed).
    """

    def __init__(
        self,
        message: str,
        *,
        violated_rule: str,
        staff_id: StaffId | None = None,
        event_id: EventId | None = None,
        facility_id: FacilityId | None = None,
    ) -> None:
        super().__init__(message)
        self.violated_rule = violated_rule
        self.staff_id = staff_id
        self.event_id = event_id
        self.facility_id = facility_id

    def context(self) -> dict[str, str]:
        """Structured context for the log. Contains no PII."""
        ctx: dict[str, str] = {"violated_rule": self.violated_rule}
        if self.staff_id is not None:
            ctx["staff_id"] = self.staff_id
        if self.event_id is not None:
            ctx["event_id"] = self.event_id
        if self.facility_id is not None:
            ctx["facility_id"] = self.facility_id
        return ctx


# --- BR-01: Coordinates -----------------------------------------------------


class InvalidCoordinatesError(DomainError):
    """Latitude outside [-90, 90], longitude outside [-180, 180], or NaN/inf."""


# --- BR-02: ObjectiveWeights ------------------------------------------------


class AllWeightsZeroError(DomainError):
    """Every objective weight is zero, so the objective function is a constant."""


class NegativeWeightError(DomainError):
    """An objective weight is negative."""


# --- BR-03: Facility --------------------------------------------------------


class QualificationRequirementExceedsHeadcountError(DomainError):
    """Sum of qualification-specific headcounts exceeds the facility's headcount."""


class DuplicateQualificationRequirementError(DomainError):
    """The same qualification appears twice in a facility's requirements."""


# --- BR-04: TravelParameters ------------------------------------------------


class InvalidTravelParametersError(DomainError):
    """detour_factor < 1.0, average_speed_kmh <= 0, or a negative value."""


# --- BR-05: AvailabilityDeclaration -----------------------------------------


class InconsistentDeclarationError(DomainError):
    """is_available and reason_category/other_reason_note disagree."""


# --- BR-07: AssignmentResult ------------------------------------------------


class NonDemotableConstraintViolationError(DomainError):
    """A result carries a violation of C1, C2, C4 or C5.

    FR-04.5 demotes C3 and nothing else. A result violating any other hard
    constraint means the solver has a bug, and it is refused here rather than
    allowed to propagate downstream.
    """


class DuplicateAssignmentError(DomainError):
    """Two assignments share the same (event_id, staff_id). Violates INV-01."""


class InvalidObjectiveValueError(DomainError):
    """objective_value is NaN, infinite, or negative. Violates INV-06."""


# --- Event state machine ----------------------------------------------------


class InvalidStateTransitionError(DomainError):
    """A transition not present in the Event state-transition table."""


# --- effective_declaration_for ----------------------------------------------


class AmbiguousDeclarationError(DomainError):
    """Two declarations for the same (staff, event) share the same timestamp.

    Which one is in force cannot be determined, so we refuse rather than pick
    arbitrarily (fail closed). U-03 must guarantee timestamp uniqueness when
    bulk-importing declarations (handoff U01-H11).
    """


# --- Distance and cost (U-02) -----------------------------------------------


class InvalidCostModelError(DomainError):
    """A distance-band cost model is malformed.

    Covers a band with a negative amount or non-positive upper bound (BR-D01),
    a table without exactly one unbounded final band or with non-increasing
    bounds (BR-D02), and - the important one - a table whose cost DECREASES with
    distance (BR-D04), which would make the optimizer prefer the further facility.
    """


class UnknownSchoolDistrictError(DomainError):
    """A referenced school district is not in the master.

    Raised rather than returning None: a caller ignoring the None would silently
    drop that staff member from the optimization (fail closed, BR-D09). The
    context carries the school-district ID only, never a staff name.
    """


# --- Persistence (U-03) -----------------------------------------------------


class DataIntegrityError(DomainError):
    """A row read back from the database fails a domain invariant.

    Raised by U-03's mappers when ``__post_init__`` refuses to rebuild a domain
    object from a stored row -- e.g. a persisted latitude of 95.0. The database
    is corrupt, and failing here stops that corruption from propagating
    downstream as a silently-wrong result (SECURITY-15, fail closed; BR-DM13).

    The context carries the entity kind and the row's ID only. Like every other
    DomainError it must never carry a staff name or residence district
    (SECURITY-03, BR-DM14) -- the ID is not PII, the name is.
    """

    def __init__(self, message: str, *, entity: str, entity_id: str) -> None:
        super().__init__(message, violated_rule="BR-DM13")
        self.entity = entity
        self.entity_id = entity_id

    def context(self) -> dict[str, str]:
        return {
            "violated_rule": self.violated_rule,
            "entity": self.entity,
            "entity_id": self.entity_id,
        }


# --- Enum conversion --------------------------------------------------------


class UnknownEnumValueError(DomainError):
    """A CSV or API value has no entry in the conversion table.

    Never coerced to OTHER: an unrecognised job title must surface as an import
    error with its row number, not be silently absorbed (SECURITY-15).
    """


__all__ = [
    "AllWeightsZeroError",
    "AmbiguousDeclarationError",
    "DataIntegrityError",
    "DomainError",
    "DuplicateAssignmentError",
    "DuplicateQualificationRequirementError",
    "InconsistentDeclarationError",
    "InvalidCoordinatesError",
    "InvalidCostModelError",
    "InvalidObjectiveValueError",
    "InvalidStateTransitionError",
    "InvalidTravelParametersError",
    "NegativeWeightError",
    "NonDemotableConstraintViolationError",
    "QualificationRequirementExceedsHeadcountError",
    "UnknownEnumValueError",
    "UnknownSchoolDistrictError",
]
