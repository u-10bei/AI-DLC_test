"""LC-03 DTOs — the API contract (Pydantic lives here and nowhere else).

U-01's NFR Design confined Pydantic to this boundary so the domain layer never
depends on a web framework, and every other unit's lint contract forbids it. These
types are therefore the only Pydantic in the system.

They are also a deliberate translation layer, not a mirror of the domain: the wire
format is a contract with the frontend, and a domain refactor must not be able to
break it silently (BR-API02).
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class EventRequest(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    type: str  # Japanese label (US-05); converted via shared_kernel.from_japanese
    name: str = Field(min_length=1, max_length=100)
    scheduled_date: date


class EventResponse(BaseModel):
    id: str
    type: str
    name: str
    scheduled_date: date
    status: str


class RowErrorResponse(BaseModel):
    line: int
    message: str  # no PII (BR-DM14)


class ImportResultResponse(BaseModel):
    success_count: int


class SufficiencyResponse(BaseModel):
    available: int
    unavailable: int
    undeclared: int
    required: int
    shortage: int


class OptimizationRequest(BaseModel):
    event_id: str = Field(min_length=1, max_length=32)
    mode: str = "FULL"  # FULL | INCREMENTAL (FR-06.6)
    travel_time_weight: float = Field(default=1.0, ge=0.0)
    travel_cost_weight: float = Field(default=1.0, ge=0.0)
    inequity_weight: float = Field(default=0.5, ge=0.0)
    time_limit_seconds: int = Field(default=300, gt=0)
    department_cap_limit: int = Field(default=100, gt=0)


class JobAcceptedResponse(BaseModel):
    job_id: str
    state: str


class ConstraintViolationResponse(BaseModel):
    constraint_id: str
    detail: str
    facility_id: str | None = None
    staff_id: str | None = None


class AssignmentResponse(BaseModel):
    staff_id: str
    facility_id: str
    is_pinned: bool


class JobStatusResponse(BaseModel):
    job_id: str
    state: str
    assignments: list[AssignmentResponse] | None = None
    objective_value: float | None = None
    optimality_gap: float | None = None
    solver_status: str | None = None
    violations: list[ConstraintViolationResponse] | None = None
    detail: str | None = None  # infeasibility cause / failure summary, no PII


class AssignmentPatchRequest(BaseModel):
    staff_id: str = Field(min_length=1, max_length=32)
    facility_id: str = Field(min_length=1, max_length=32)


class ComparisonResponse(BaseModel):
    event_id: str
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


class ErrorResponse(BaseModel):
    """Generic error body. Never carries a stack trace, path or framework version."""

    message: str
    violated_rule: str | None = None
    errors: list[RowErrorResponse] | None = None  # CSV import (BR-DM02)
    violations: list[ConstraintViolationResponse] | None = None  # manual edit (FR-06.3)


class HealthResponse(BaseModel):
    status: str
    checked_at: datetime


__all__ = [
    "AssignmentPatchRequest",
    "AssignmentResponse",
    "ComparisonResponse",
    "ConstraintViolationResponse",
    "ErrorResponse",
    "EventRequest",
    "EventResponse",
    "HealthResponse",
    "ImportResultResponse",
    "JobAcceptedResponse",
    "JobStatusResponse",
    "LoginRequest",
    "OptimizationRequest",
    "RowErrorResponse",
    "SufficiencyResponse",
]
