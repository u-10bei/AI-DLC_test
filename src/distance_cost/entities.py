"""The one type U-02 defines. Everything else it uses comes from shared_kernel."""

from __future__ import annotations

from dataclasses import dataclass

from shared_kernel import SchoolDistrictId


@dataclass(frozen=True, slots=True)
class DistanceCacheEntry:
    """A cached great-circle distance for one pair of school districts.

    ``district_a`` and ``district_b`` are the CANONICALISED key: a is the smaller
    ID, b the larger. Both directions of a lookup therefore resolve to this one
    entry, which makes INV-07b (cached symmetry) exact by construction rather
    than by floating-point luck.

    Only the great-circle distance is stored - not the post-detour distance, not
    time, not cost. Those depend on parameters a coordinator changes from the
    screen (US-14); storing only the great-circle distance means the cache is
    invalidated only when the school-district master changes.
    """

    district_a: SchoolDistrictId
    district_b: SchoolDistrictId
    great_circle_km: float


def canonical_key(
    x: SchoolDistrictId, y: SchoolDistrictId
) -> tuple[SchoolDistrictId, SchoolDistrictId]:
    """Order a district pair so (x, y) and (y, x) map to the same key (U01-H1)."""
    return (x, y) if x <= y else (y, x)


__all__ = ["DistanceCacheEntry", "canonical_key"]
