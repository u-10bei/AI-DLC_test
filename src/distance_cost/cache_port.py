"""P-03 DistanceCachePort — the interface, not the implementation.

U-02 defines this port; U-03 implements it (A-02 PersistenceAdapter). This is
dependency inversion: U-02 states the contract for a distance cache without
knowing it is a database. The dependency runs U-03 -> U-02, never the reverse,
so the graph stays acyclic.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from shared_kernel import SchoolDistrictId

from .entities import DistanceCacheEntry


class DistanceCachePort(Protocol):
    """A cache of great-circle distances keyed on canonicalised district pairs."""

    def get_distance(
        self, district_a: SchoolDistrictId, district_b: SchoolDistrictId
    ) -> float | None:
        """Great-circle km for the pair, or None on a cache miss.

        The implementation must canonicalise the key (see entities.canonical_key)
        so that get_distance(a, b) and get_distance(b, a) return the same value.
        """
        ...

    def put_distances(self, entries: Iterable[DistanceCacheEntry]) -> None:
        """Store entries. Their keys are already canonicalised."""
        ...

    def invalidate_all(self) -> None:
        """Clear the cache. Called only when the school-district master changes."""
        ...


__all__ = ["DistanceCachePort"]
