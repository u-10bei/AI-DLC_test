"""U-06's own identifiers (U06-H8).

U-01 knows nothing about login accounts, so the account and session identifiers
live here rather than in shared_kernel. NewType keeps a UserId from being passed
where a SessionId belongs, at zero runtime cost.
"""

from __future__ import annotations

from typing import NewType

UserId = NewType("UserId", str)
SessionId = NewType("SessionId", str)

__all__ = ["SessionId", "UserId"]
