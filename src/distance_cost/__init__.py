"""U-02 distance-cost — distance, travel time and travel cost.

Pure functions, standard library plus shared_kernel only, enforced by two lint
contracts (R-3 and standard-library-only). The distance cache is DEFINED here
(DistanceCachePort) but PERSISTED by U-03.
"""

from .cache_port import DistanceCachePort
from .calculator import (
    EARTH_RADIUS_KM,
    actual_travel_distance_km,
    compute_travel_metrics,
    haversine_distance_km,
    travel_cost_yen,
    travel_time_seconds,
)
from .entities import DistanceCacheEntry, canonical_key
from .matrix import compute_district_distance_matrix

__all__ = [
    "EARTH_RADIUS_KM",
    "DistanceCacheEntry",
    "DistanceCachePort",
    "actual_travel_distance_km",
    "canonical_key",
    "compute_district_distance_matrix",
    "compute_travel_metrics",
    "haversine_distance_km",
    "travel_cost_yen",
    "travel_time_seconds",
]
