"""LC-07 / A-05: the append-only file audit log (SECURITY-14, MU-04, DP-03).

One event, one line, opened in append mode, flushed immediately, closed. The
flush is the point: a buffered record lost to a crash is exactly the outcome MU-04
(hiding the trail) wants, and audit volume here is low enough that durability
costs nothing that matters.

Append mode is also what ``chattr +a`` permits -- the OS refuses truncation and
overwrite, so the application cannot rewrite history even with a bug. The file and
its attribute are provisioned by operations (U06-H6, shared-infrastructure.md 3.3);
this adapter deliberately does not create directories or set attributes, because
the application account is not supposed to be able to.
"""

from __future__ import annotations

from pathlib import Path

from .audit import AuditEvent


class AppendOnlyFileAuditLog:
    """AuditLogPort writing JSON Lines to an append-only file."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def append(self, event: AuditEvent) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(event.to_json_line() + "\n")
            handle.flush()


__all__ = ["AppendOnlyFileAuditLog"]
