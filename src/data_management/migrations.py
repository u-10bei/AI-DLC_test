"""Schema application helpers.

The schema is defined once, in ``schema.py``. Both the Alembic initial revision
and these helpers build it from the same ``schema.metadata``, so tests exercise
the exact production schema (U03-H8). Alembic remains the mechanism for real
deployments and for the SQLite -> PostgreSQL migration (U01-H18); these helpers
give tests a fast, reliable path against a fresh in-memory database without
booting an Alembic environment per test.
"""

from __future__ import annotations

from sqlalchemy import Engine

from .schema import metadata


def create_all(engine: Engine) -> None:
    """Create every table (equivalent to running migrations to head)."""
    metadata.create_all(engine)


def drop_all(engine: Engine) -> None:
    metadata.drop_all(engine)


__all__ = ["create_all", "drop_all"]
