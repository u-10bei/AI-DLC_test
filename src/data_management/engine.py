"""LC-01 Engine / SessionFactory.

One place that builds the Engine, applies the mandatory SQLite PRAGMAs on every
connection, and never turns on SQL echo.

``echo`` is False in every environment (DP-05, SECURITY-03): SQL echo would write
bound parameter values -- staff names, residence districts -- to the log. There
is no development override, because that is exactly the path SECURITY-03 closes.

The PRAGMAs (WAL, busy_timeout, foreign_keys=ON) are issued from the ``connect``
event so they reach every pooled connection (U01-H15). ``foreign_keys=ON`` is the
critical one: without it SQLite ignores ON DELETE CASCADE and every foreign key,
so BR-DM10's cascade delete would silently not happen. They are branched on the
dialect and fire on SQLite only; PostgreSQL enforces foreign keys by default.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry, StaticPool

DEFAULT_URL = "sqlite+pysqlite:///app.db"


def _is_memory_sqlite(url: str) -> bool:
    return url.startswith("sqlite") and (":memory:" in url or url.rstrip("/").endswith("sqlite:"))


def _register_sqlite_pragmas(engine: Engine) -> None:
    """Apply WAL / busy_timeout / foreign_keys=ON on each SQLite connection."""

    @event.listens_for(engine, "connect")
    def _set_pragmas(
        dbapi_connection: DBAPIConnection, _record: ConnectionPoolEntry
    ) -> None:
        if engine.dialect.name != "sqlite":
            return
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def create_db_engine(url: str = DEFAULT_URL) -> Engine:
    """Build the Engine for ``url`` with PRAGMAs registered and echo off.

    Swapping SQLite for PostgreSQL is only a change of ``url`` (U01-H18); the
    PRAGMA hook no-ops on any non-SQLite dialect.

    An in-memory SQLite URL (``sqlite://``) gets a StaticPool so every operation
    shares the one connection -- otherwise each checkout would see a brand-new,
    empty database. This is what makes a fresh in-memory DB per test usable
    (U03-H8) without any test-only code in the persistence layer.
    """
    if _is_memory_sqlite(url):
        engine = create_engine(
            url,
            echo=False,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(url, echo=False, future=True)
    _register_sqlite_pragmas(engine)
    return engine


__all__ = ["DEFAULT_URL", "create_db_engine"]
