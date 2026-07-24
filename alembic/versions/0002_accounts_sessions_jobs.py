"""fill in the skeleton tables U-03 deferred to their owning units

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-17

U-03 created sessions and optimization_jobs as SKELETONS, explicitly deferring
their logic to the unit that owns them (U03-H3). U-07 now implements both, which
needs columns the skeletons never had:

  * accounts: did not exist at all - login needs one
  * sessions: only had id/created_at/expires_at, with no user or role
  * optimization_jobs: no mode (FR-06.6), no params_json, no result_id, no detail

params_json matters more than it looks: without it the API would accept a
coordinator's objective weights and then silently solve with the defaults.

Adding them here rather than editing revision 0001 keeps the migration history
honest: 0001 is what U-03 shipped, 0002 is what U-07 needed.

IDEMPOTENCE (fixed 2026-07-24). Revision 0001 runs ``metadata.create_all`` against
the LIVE schema module rather than a frozen copy (U03-H8, so the migration and the
test helper cannot drift). The consequence only appeared once U-07 edited
``schema.py`` in place: on a FRESH database 0001 now already creates accounts and
the new columns, and this revision then failed with "table accounts already
exists" - so ``alembic upgrade head`` could not complete at all. The gates never
caught it because the tests call ``create_all`` directly and never run alembic.

Each step below is therefore applied only if it is actually missing. That makes
this revision correct for both a fresh database (nothing to do) and a database
created before U-07 (everything to do).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing_columns(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "accounts" not in tables:
        op.create_table(
            "accounts",
            sa.Column("user_id", sa.String(), primary_key=True),
            sa.Column("password_hash", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("failed_attempts", sa.Integer(), nullable=False),
            sa.Column("locked_until", sa.DateTime(), nullable=True),
        )

    session_columns = _existing_columns(inspector, "sessions")
    missing_session = [
        sa.Column(name, sa.String(), nullable=False, server_default="")
        for name in ("user_id", "role")
        if name not in session_columns
    ]
    if missing_session:
        with op.batch_alter_table("sessions") as batch:
            for column in missing_session:
                batch.add_column(column)

    job_columns = _existing_columns(inspector, "optimization_jobs")
    missing_jobs = [
        sa.Column(name, sa.String(), nullable=True)
        for name in ("mode", "params_json", "result_id", "detail")
        if name not in job_columns
    ]
    if missing_jobs:
        with op.batch_alter_table("optimization_jobs") as batch:
            for column in missing_jobs:
                batch.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("optimization_jobs") as batch:
        batch.drop_column("detail")
        batch.drop_column("result_id")
        batch.drop_column("params_json")
        batch.drop_column("mode")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("role")
        batch.drop_column("user_id")
    op.drop_table("accounts")
