"""Distance-matrix precomputation — a pure function (U-02); U-03 persists it."""

from __future__ import annotations

from collections.abc import Iterable

from shared_kernel import SchoolDistrict

from .calculator import haversine_distance_km
from .entities import DistanceCacheEntry, canonical_key


def compute_district_distance_matrix(
    districts: Iterable[SchoolDistrict],
) -> list[DistanceCacheEntry]:
    """Great-circle distance for every district pair, ready to cache.

    Pure function. U-03 calls this and persists the result, and re-runs it when
    the school-district master changes (US-09, handoff U02-H10). U-02 does not
    know *when* to recompute - that is persistence and workflow, which is U-03's.

    Keys are canonicalised (min, max), so a D-district master yields D(D+1)/2
    entries (the diagonal included, at distance 0). For D=200 that is ~20,100
    Haversine calls - a sub-second naive loop, which is why numpy was not needed.
    """
    ordered = list(districts)
    entries: list[DistanceCacheEntry] = []
    for i, first in enumerate(ordered):
        for second in ordered[i:]:
            a, b = canonical_key(first.id, second.id)
            distance = haversine_distance_km(
                first.representative_point, second.representative_point
            )
            entries.append(DistanceCacheEntry(district_a=a, district_b=b, great_circle_km=distance))
    return entries


__all__ = ["compute_district_distance_matrix"]
