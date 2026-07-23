"""SQLAlchemy Core table definitions for the whole backend schema.

U-03 owns the master and operational tables (departments .. distance_cache). It
also creates the *skeletons* of the tables other units own (assignment_results,
optimization_jobs, sessions, historical_*), so the initial Alembic migration
builds one coherent schema (domain-entities.md section 3.9, Q6=A). The owning
unit fills in each skeleton's business logic and any extra columns via a later
migration; U-03 never reads or writes them.

No SQLite-specific SQL: every type and constraint is expressed through Core so
the same schema migrates to PostgreSQL by a connection-string change (U01-H18).
Times are UTC except ``events.scheduled_date``, a JST calendar date (U01-H12).
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

# --- master data ------------------------------------------------------------

departments = Table(
    "departments",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("concurrent_assignment_cap", Integer, nullable=True),
)

school_districts = Table(
    "school_districts",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("latitude", Float, nullable=False),
    Column("longitude", Float, nullable=False),
)

staff = Table(
    "staff",
    metadata,
    Column("id", String, primary_key=True),
    # name and residence_district_id are PII (SECURITY-01/03).
    Column("name", String, nullable=False),
    Column("department_id", String, ForeignKey("departments.id"), nullable=False),
    Column("job_type", String, nullable=False),  # English identifier (U01-H24)
    Column("position", String, nullable=False),  # English identifier
    Column(
        "residence_district_id",
        String,
        ForeignKey("school_districts.id"),
        nullable=False,
    ),
)

staff_qualifications = Table(
    "staff_qualifications",
    metadata,
    Column(
        "staff_id",
        String,
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("qualification", String, nullable=False),  # English identifier
    PrimaryKeyConstraint("staff_id", "qualification"),
)

facilities = Table(
    "facilities",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("district_id", String, ForeignKey("school_districts.id"), nullable=False),
    Column("required_headcount", Integer, nullable=False),
    CheckConstraint("required_headcount >= 1", name="ck_facilities_headcount"),
)

facility_qualification_requirements = Table(
    "facility_qualification_requirements",
    metadata,
    Column(
        "facility_id",
        String,
        ForeignKey("facilities.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("requirement", String, nullable=False),  # English identifier
    Column("required_count", Integer, nullable=False),
    PrimaryKeyConstraint("facility_id", "requirement"),
)

# --- events and declarations ------------------------------------------------

events = Table(
    "events",
    metadata,
    Column("id", String, primary_key=True),
    Column("type", String, nullable=False),
    Column("name", String, nullable=False),
    Column("scheduled_date", Date, nullable=False),  # JST calendar date (U01-H12)
    Column("status", String, nullable=False),
)

availability_declarations = Table(
    "availability_declarations",
    metadata,
    Column("staff_id", String, ForeignKey("staff.id"), nullable=False),
    Column(
        "event_id",
        String,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("is_available", Boolean, nullable=False),
    Column("reason_category", String, nullable=True),
    Column("other_reason_note", String, nullable=True),
    Column("declared_at", DateTime, nullable=False),  # UTC
    # BR-DM05 / U01-H11: at most one declaration per (staff, event, instant).
    # This is what makes AmbiguousDeclarationError impossible at the DB level.
    UniqueConstraint(
        "staff_id", "event_id", "declared_at", name="uq_declaration_instant"
    ),
    # Speeds the correlated MAX(declared_at) lookup of the effective declaration.
    Index("ix_declaration_latest", "staff_id", "event_id", "declared_at"),
)

assignments = Table(
    "assignments",
    metadata,
    Column(
        "event_id",
        String,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("staff_id", String, ForeignKey("staff.id"), nullable=False),
    Column("facility_id", String, ForeignKey("facilities.id"), nullable=False),
    Column("is_pinned", Boolean, nullable=False),
    # PK(event_id, staff_id) enforces INV-01 (one facility per person per event).
    PrimaryKeyConstraint("event_id", "staff_id"),
)

# --- distance cache (U-02's port, U-03's table) -----------------------------

distance_cache = Table(
    "distance_cache",
    metadata,
    Column("district_a", String, nullable=False),  # canonical: smaller ID
    Column("district_b", String, nullable=False),  # canonical: larger ID
    Column("great_circle_km", Float, nullable=False),  # great-circle only (U02-H4)
    PrimaryKeyConstraint("district_a", "district_b"),
    # Rejects a non-canonical entry at the DB level (BR-DM11, U02-H3).
    CheckConstraint("district_a <= district_b", name="ck_distance_cache_canonical"),
)

# --- skeletons owned by other units (Q6=A) ----------------------------------
# Created here so the initial migration yields one coherent schema. The owning
# unit implements the logic and may extend these via later migrations. U-03
# never reads or writes them.

optimization_jobs = Table(  # queue owned by U-07 (worker), solving logic from U-04
    "optimization_jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("event_id", String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime, nullable=False),
    # Filled in by U-07 (the skeleton deferred the logic to the owning unit, U03-H3).
    Column("mode", String, nullable=True),  # FULL / INCREMENTAL (FR-06.6)
    Column("params_json", String, nullable=True),  # the coordinator's weights/limits
    Column("result_id", String, nullable=True),  # -> assignment_results.id on success
    Column("detail", String, nullable=True),  # infeasibility/failure summary, no PII
)

assignment_results = Table(  # U-04
    "assignment_results",
    metadata,
    Column("id", String, primary_key=True),
    Column("event_id", String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
    Column("objective_value", Float, nullable=True),
    Column("solver_status", String, nullable=True),
    Column("created_at", DateTime, nullable=False),
)

constraint_violations = Table(  # U-04
    "constraint_violations",
    metadata,
    Column("id", String, primary_key=True),
    Column(
        "result_id",
        String,
        ForeignKey("assignment_results.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("constraint_id", String, nullable=False),
    Column("detail", String, nullable=True),
)

historical_records = Table(  # U-05
    "historical_records",
    metadata,
    Column("id", String, primary_key=True),
    Column("event_id", String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
    Column("recorded_at", DateTime, nullable=False),
)

# Login accounts and sessions. U-06 owns the LOGIC but is forbidden sqlalchemy by
# its lint contract, so U-07 implements SessionStorePort against these tables and
# injects it (U06-H2). The tables live here because U-03 owns the schema.
accounts = Table(
    "accounts",
    metadata,
    Column("user_id", String, primary_key=True),
    Column("password_hash", String, nullable=False),  # Argon2id, never a password
    Column("role", String, nullable=False),
    Column("failed_attempts", Integer, nullable=False),
    Column("locked_until", DateTime, nullable=True),
)

sessions = Table(
    "sessions",
    metadata,
    Column("id", String, primary_key=True),  # opaque CSPRNG value
    Column("user_id", String, ForeignKey("accounts.user_id", ondelete="CASCADE"), nullable=False),
    Column("role", String, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("expires_at", DateTime, nullable=False),
)

__all__ = [
    "accounts",
    "assignment_results",
    "assignments",
    "availability_declarations",
    "constraint_violations",
    "departments",
    "distance_cache",
    "events",
    "facilities",
    "facility_qualification_requirements",
    "historical_records",
    "metadata",
    "optimization_jobs",
    "school_districts",
    "sessions",
    "staff",
    "staff_qualifications",
]
