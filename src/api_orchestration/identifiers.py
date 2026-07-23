"""U-07's own identifiers (U07-H7)."""

from __future__ import annotations

from typing import NewType

JobId = NewType("JobId", str)

__all__ = ["JobId"]
