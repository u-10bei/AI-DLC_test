"""`alembic upgrade head` must work on a fresh database.

This path had never been exercised. The tests build schemas with `create_all`,
so nothing ran the migrations — and they were broken: revision 0001 runs
`metadata.create_all` against the LIVE schema module (U03-H8), so once U-07 added
`accounts` to `schema.py` in place, 0001 created it and 0002 then failed with
"table accounts already exists". Deployment step 6 could not have completed.

These tests pin the two properties that matter for deployment:
  1. a fresh database can migrate all the way to head, and
  2. what the migrations produce matches what `create_all` produces, so the
     deployed schema and the tested schema cannot drift.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from data_management import create_all, create_db_engine

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_fresh_database_migrates_to_head(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'fresh.db'}"

    command.upgrade(_alembic_config(url), "head")

    engine = create_db_engine(url)
    with engine.connect() as conn:
        revision = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
    assert revision == "0002"


def test_migrated_schema_matches_create_all(tmp_path: Path) -> None:
    """The deployed schema and the tested schema must not drift."""
    migrated_url = f"sqlite:///{tmp_path / 'migrated.db'}"
    command.upgrade(_alembic_config(migrated_url), "head")

    direct_url = f"sqlite:///{tmp_path / 'direct.db'}"
    create_all(create_db_engine(direct_url))

    migrated = sa.inspect(create_db_engine(migrated_url))
    direct = sa.inspect(create_db_engine(direct_url))

    migrated_tables = set(migrated.get_table_names()) - {"alembic_version"}
    direct_tables = set(direct.get_table_names())
    assert migrated_tables == direct_tables

    for table in sorted(direct_tables):
        migrated_columns = {c["name"] for c in migrated.get_columns(table)}
        direct_columns = {c["name"] for c in direct.get_columns(table)}
        assert migrated_columns == direct_columns, f"column drift in {table}"


def test_upgrade_is_idempotent_against_an_already_current_database(tmp_path: Path) -> None:
    """Re-running the deploy step (runbook §13) must not fail."""
    url = f"sqlite:///{tmp_path / 'again.db'}"
    config = _alembic_config(url)
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # second run: no-op, must not raise
