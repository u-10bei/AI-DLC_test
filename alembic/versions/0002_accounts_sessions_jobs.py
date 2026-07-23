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
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("user_id", sa.String(), primary_key=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
    )
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("user_id", sa.String(), nullable=False, server_default=""))
        batch.add_column(sa.Column("role", sa.String(), nullable=False, server_default=""))
    with op.batch_alter_table("optimization_jobs") as batch:
        batch.add_column(sa.Column("mode", sa.String(), nullable=True))
        batch.add_column(sa.Column("params_json", sa.String(), nullable=True))
        batch.add_column(sa.Column("result_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("detail", sa.String(), nullable=True))


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
