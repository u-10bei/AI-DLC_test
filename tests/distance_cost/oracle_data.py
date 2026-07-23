"""Oracle data for P-D05: known coordinate pairs and their great-circle distances.

Symmetry and non-negativity hold even for a WRONG Haversine implementation - swap
latitude and longitude, or reverse the atan2 arguments, and both still pass. Only
comparison against independently-known distances catches that class of bug. A few
distant pairs suffice: a lat/lon swap turns Tokyo-Osaka's 403 km into something
wildly different, so the error shows up immediately.

Great-circle distances below are computed for the spherical model (IUGG mean
radius). Tolerance in the test is 0.5%, the spherical-vs-ellipsoidal gap.
"""

from __future__ import annotations

from shared_kernel import Coordinates

# (name, point A, point B, approx great-circle km)
ORACLE_PAIRS: list[tuple[str, Coordinates, Coordinates, float]] = [
    (
        "Tokyo-Osaka",
        Coordinates(35.681236, 139.767125),
        Coordinates(34.702485, 135.495951),
        403.0,
    ),
    (
        "Tokyo-Sendai",
        Coordinates(35.681236, 139.767125),
        Coordinates(38.260132, 140.882314),
        304.8,
    ),
    (
        "Tokyo-Nagoya",
        Coordinates(35.681236, 139.767125),
        Coordinates(35.170915, 136.881537),
        267.0,
    ),
    (
        "Sapporo-Fukuoka",
        Coordinates(43.068661, 141.350755),
        Coordinates(33.589691, 130.420685),
        1418.0,
    ),
    (
        "identical-point",
        Coordinates(35.681236, 139.767125),
        Coordinates(35.681236, 139.767125),
        0.0,
    ),
]

__all__ = ["ORACLE_PAIRS"]
