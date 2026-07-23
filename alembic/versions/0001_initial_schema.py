"""initial schema — all backend tables (owned + skeletons)

Revision ID: 0001
Revises:
Create Date: 2026-07-16

The schema is defined once in data_management.schema; this revision materialises
it via metadata.create_all against the migration's bind, so the migration and the
test helper (data_management.migrations.create_all) can never drift (U03-H8).
Later units add their own revisions for any extra columns on the skeleton tables.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from data_management.schema import metadata

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind())
