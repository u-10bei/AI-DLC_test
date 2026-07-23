"""Argon2id password hashing (SECURITY-12, U06-H1).

Argon2id over bcrypt: it is memory-hard, so a GPU farm buys far less speedup, and
it has no 72-byte truncation. Parameters default to OWASP's recommendation and are
configurable (SecurityConfig), which is what "adaptive" means -- the cost rises as
hardware does.

``verify`` returns False rather than raising on a wrong password: a mismatch is an
expected outcome, not an error, and the caller's control flow should not depend on
catching library exceptions.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import SecurityConfig


class Argon2PasswordHasher:
    """PasswordHasherPort backed by argon2-cffi."""

    def __init__(self, config: SecurityConfig | None = None) -> None:
        settings = config if config is not None else SecurityConfig()
        self._hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_kib,
            parallelism=settings.argon2_parallelism,
        )

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
        return True


__all__ = ["Argon2PasswordHasher"]
