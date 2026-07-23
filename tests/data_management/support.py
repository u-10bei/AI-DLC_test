"""Test support: a fresh in-memory SQLite database per call (U03-H8).

No mocks. The properties under test (P-DM01..05) are about SQL correctness --
constraints, ON DELETE CASCADE, the uniqueness of the latest declaration -- which
a mock repository cannot exercise. Each call builds a brand-new database with the
production schema and the production PRAGMAs (foreign_keys=ON included, or the
cascade tests would be meaningless).
"""

from __future__ import annotations

from sqlalchemy import Engine

from data_management import create_all, create_db_engine, repositories

from .generators import Dataset


def fresh_engine() -> Engine:
    engine = create_db_engine("sqlite://")
    create_all(engine)
    return engine


def seed_masters(engine: Engine, dataset: Dataset) -> None:
    """Insert a whole master dataset from domain objects, in one transaction."""
    with engine.begin() as conn:
        repositories.insert_departments(conn, dataset.departments)
        repositories.insert_school_districts(conn, dataset.districts)
        repositories.insert_staff(conn, dataset.staff)
        repositories.insert_facilities(conn, dataset.facilities)


__all__ = ["Dataset", "fresh_engine", "seed_masters"]
