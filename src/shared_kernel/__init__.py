"""U-01 shared-kernel — the types every backend unit shares.

The root of the dependency graph. Depends on the standard library and nothing
else, which is precisely why six units can share it: swapping SQLite for
PostgreSQL, or FastAPI for something else, never reaches this package.

What lives here:
  * domain types (frozen, validated on construction)
  * the exception hierarchy
  * the enum <-> Japanese conversion table

What does not, and where it lives instead:
  * distance/cost arithmetic        -> U-02 distance-cost
  * persistence                     -> U-03 data-management
  * constraint checking, the solver -> U-04 optimization-engine
  * authn/authz, the audit log      -> U-06 security
  * HTTP, DTOs, Pydantic            -> U-07 api-orchestration
"""

from .availability import effective_declaration_for
from .entities import (
    REDACTED,
    Assignment,
    AvailabilityDeclaration,
    Department,
    Event,
    Facility,
    SchoolDistrict,
    Staff,
)
from .enums import (
    ALLOWED_EVENT_TRANSITIONS,
    DELETABLE_EVENT_STATUSES,
    EventStatus,
    EventType,
    JobType,
    Position,
    Qualification,
    ReasonCategory,
    SolverStatus,
    from_japanese,
    to_japanese,
)
from .exceptions import (
    AllWeightsZeroError,
    AmbiguousDeclarationError,
    DataIntegrityError,
    DomainError,
    DuplicateAssignmentError,
    DuplicateQualificationRequirementError,
    InconsistentDeclarationError,
    InvalidCoordinatesError,
    InvalidCostModelError,
    InvalidObjectiveValueError,
    InvalidStateTransitionError,
    InvalidTravelParametersError,
    NegativeWeightError,
    NonDemotableConstraintViolationError,
    QualificationRequirementExceedsHeadcountError,
    UnknownEnumValueError,
    UnknownSchoolDistrictError,
)
from .identifiers import (
    DepartmentId,
    EventId,
    FacilityId,
    SchoolDistrictId,
    StaffId,
)
from .problem import (
    DEMOTABLE_CONSTRAINTS,
    AssignmentProblem,
    AssignmentResult,
    ConstraintId,
    ConstraintViolation,
    HistoricalRecord,
)
from .value_objects import (
    DEFAULT_AVERAGE_SPEED_KMH,
    DEFAULT_COST_MODEL,
    DEFAULT_DETOUR_FACTOR,
    DEFAULT_SAME_DISTRICT_FIXED_SECONDS,
    DEFAULT_TIME_LIMIT_SECONDS,
    Coordinates,
    CostBand,
    CostModel,
    CostRule,
    ObjectiveWeights,
    OptimizationParameters,
    QualificationRequirement,
    TravelMetrics,
    TravelParameters,
)

__all__ = [
    "ALLOWED_EVENT_TRANSITIONS",
    "DEFAULT_AVERAGE_SPEED_KMH",
    "DEFAULT_COST_MODEL",
    "DEFAULT_DETOUR_FACTOR",
    "DEFAULT_SAME_DISTRICT_FIXED_SECONDS",
    "DEFAULT_TIME_LIMIT_SECONDS",
    "DELETABLE_EVENT_STATUSES",
    "DEMOTABLE_CONSTRAINTS",
    "REDACTED",
    "AllWeightsZeroError",
    "AmbiguousDeclarationError",
    "Assignment",
    "AssignmentProblem",
    "AssignmentResult",
    "AvailabilityDeclaration",
    "ConstraintId",
    "ConstraintViolation",
    "Coordinates",
    "CostBand",
    "CostModel",
    "CostRule",
    "DataIntegrityError",
    "Department",
    "DepartmentId",
    "DomainError",
    "DuplicateAssignmentError",
    "DuplicateQualificationRequirementError",
    "Event",
    "EventId",
    "EventStatus",
    "EventType",
    "Facility",
    "FacilityId",
    "HistoricalRecord",
    "InconsistentDeclarationError",
    "InvalidCoordinatesError",
    "InvalidCostModelError",
    "InvalidObjectiveValueError",
    "InvalidStateTransitionError",
    "InvalidTravelParametersError",
    "JobType",
    "NegativeWeightError",
    "NonDemotableConstraintViolationError",
    "ObjectiveWeights",
    "OptimizationParameters",
    "Position",
    "Qualification",
    "QualificationRequirement",
    "QualificationRequirementExceedsHeadcountError",
    "ReasonCategory",
    "SchoolDistrict",
    "SchoolDistrictId",
    "SolverStatus",
    "Staff",
    "StaffId",
    "TravelMetrics",
    "TravelParameters",
    "UnknownEnumValueError",
    "UnknownSchoolDistrictError",
    "effective_declaration_for",
    "from_japanese",
    "to_japanese",
]
