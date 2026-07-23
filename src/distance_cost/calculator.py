"""Distance, time and cost — pure functions, standard library only.

Nothing here touches a database, the network, the clock, or a random source.
That is not a promise in a docstring; lint contract R-3 and the
standard-library-only contract enforce it. The payoff is that INV-07..INV-09 are
property-testable with no mocks at all.
"""

from __future__ import annotations

import math

from shared_kernel import Coordinates, SchoolDistrict, TravelMetrics, TravelParameters

#: IUGG mean Earth radius. Fixed as a named constant so property tests reproduce;
#: the choice shifts results by tens of metres (BR-D05).
EARTH_RADIUS_KM = 6371.0088


def haversine_distance_km(a: Coordinates, b: Coordinates) -> float:
    """Great-circle distance between two points, in kilometres.

    INV-07a: symmetric to within a tolerance (floating-point rounding depends on
    argument order). INV-08a: non-negative. INV-08b: exactly 0 for a == b.
    """
    lat1 = math.radians(a.latitude)
    lat2 = math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)

    h = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    # clamp guards against h drifting a hair above 1.0 from rounding
    central_angle = 2.0 * math.asin(math.sqrt(min(1.0, h)))
    return EARTH_RADIUS_KM * central_angle


def actual_travel_distance_km(great_circle_km: float, detour_factor: float) -> float:
    """Approximate real travel distance by inflating the straight line (A-03)."""
    return great_circle_km * detour_factor


def travel_time_seconds(distance_km: float, average_speed_kmh: float) -> int:
    """Travel time in whole seconds.

    Rounded UP (BR-D06): never underestimate travel time. In a disaster the
    consequence of underestimating is a late arrival, so the safe side is to
    overestimate. Because of the rounding, INV-09 is monotone NON-decreasing,
    not strictly increasing.
    """
    return math.ceil(distance_km / average_speed_kmh * 3600.0)


def travel_cost_yen(distance_km: float, params: TravelParameters) -> float:
    """Cost by the distance-band model (FR-03.5). Linear scan (BR-D08)."""
    return params.cost_model.cost_for(distance_km)


def compute_travel_metrics(
    from_district: SchoolDistrict,
    to_district: SchoolDistrict,
    params: TravelParameters,
) -> TravelMetrics:
    """Distance, time and cost between two districts.

    Same district is a special case (FR-03.7, BR-D07): distance 0, cost 0, and
    time is the fixed same-district value rather than 0. Treating same-district
    time as 0 would make the optimizer prefer same-district assignments
    unconditionally, when in reality there is still a short walk.
    """
    if from_district.id == to_district.id:
        return TravelMetrics(
            distance_km=0.0,
            time_seconds=params.same_district_fixed_seconds,
            cost_yen=0.0,
        )

    great_circle = haversine_distance_km(
        from_district.representative_point,
        to_district.representative_point,
    )
    distance = actual_travel_distance_km(great_circle, params.detour_factor)
    return TravelMetrics(
        distance_km=distance,
        time_seconds=travel_time_seconds(distance, params.average_speed_kmh),
        cost_yen=travel_cost_yen(distance, params),
    )


__all__ = [
    "EARTH_RADIUS_KM",
    "actual_travel_distance_km",
    "compute_travel_metrics",
    "haversine_distance_km",
    "travel_cost_yen",
    "travel_time_seconds",
]
