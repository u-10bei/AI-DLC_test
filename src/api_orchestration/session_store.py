"""LC-07 SqlSessionStore — U-06's SessionStorePort, implemented here (U06-H2).

This class lives in U-07 rather than U-06 for a structural reason, not a stylistic
one: U-06's lint contract forbids sqlalchemy, so U-06 physically cannot persist a
session. The port must therefore be implemented outside and injected. The contract
decided where this file goes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Engine, delete, insert, select, update

from data_management import schema
from security import Account, Principal, Role, Session
from security.identifiers import SessionId, UserId


def _to_stored(value: datetime | None) -> datetime | None:
    """Aware UTC -> naive UTC for storage (SQLite drops tzinfo)."""
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo is not None else value


def _from_stored(value: object) -> datetime | None:
    """Naive UTC -> aware UTC on load.

    Without this, comparing a loaded expires_at against an aware `now` raises
    TypeError -- the same trap U-03's mappers handle.
    """
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _require_dt(value: datetime | None) -> datetime:
    if value is None:
        raise ValueError("session timestamp is missing")  # fail closed
    return value


class SqlSessionStore:
    """SessionStorePort backed by U-03's accounts / sessions tables."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_account(self, user_id: UserId) -> Account | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(schema.accounts).where(schema.accounts.c.user_id == str(user_id))
            ).first()
        if row is None:
            return None
        mapping = row._mapping
        return Account(
            user_id=UserId(str(mapping["user_id"])),
            password_hash=str(mapping["password_hash"]),
            role=Role[str(mapping["role"])],
            failed_attempts=int(mapping["failed_attempts"]),
            locked_until=_from_stored(mapping["locked_until"]),
        )

    def save_account(self, account: Account) -> None:
        values = {
            "password_hash": account.password_hash,
            "role": account.role.name,
            "failed_attempts": account.failed_attempts,
            "locked_until": _to_stored(account.locked_until),
        }
        with self._engine.begin() as conn:
            result = conn.execute(
                update(schema.accounts)
                .where(schema.accounts.c.user_id == str(account.user_id))
                .values(**values)
            )
            if result.rowcount == 0:
                conn.execute(
                    insert(schema.accounts), {"user_id": str(account.user_id), **values}
                )

    def save_session(self, session: Session) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(schema.sessions),
                {
                    "id": str(session.id),
                    "user_id": str(session.principal.user_id),
                    "role": session.principal.role.name,
                    "created_at": _to_stored(session.issued_at),
                    "expires_at": _to_stored(session.expires_at),
                },
            )

    def find_session(self, session_id: SessionId) -> Session | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(schema.sessions).where(schema.sessions.c.id == str(session_id))
            ).first()
        if row is None:
            return None
        mapping = row._mapping
        return Session(
            id=SessionId(str(mapping["id"])),
            principal=Principal(
                user_id=UserId(str(mapping["user_id"])), role=Role[str(mapping["role"])]
            ),
            issued_at=_require_dt(_from_stored(mapping["created_at"])),
            expires_at=_require_dt(_from_stored(mapping["expires_at"])),
        )

    def delete_session(self, session_id: SessionId) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(schema.sessions).where(schema.sessions.c.id == str(session_id)))


__all__ = ["SqlSessionStore"]
