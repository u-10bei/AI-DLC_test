"""Property-based tests for U-02 (PBT-03, PBT-05).

INV-07a/07b, INV-08a/b/c, INV-09, and P-D01..P-D06 from
business-logic-model.md section 7. Because U-02 is pure functions, none of these
needs a mock.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from distance_cost import (
    actual_travel_distance_km,
    compute_travel_metrics,
    haversine_distance_km,
    travel_cost_yen,
    travel_time_seconds,
)
from shared_kernel import (
    Coordinates,
    CostModel,
    InvalidCostModelError,
    SchoolDistrict,
    TravelParameters,
)
from tests.distance_cost.oracle_data import ORACLE_PAIRS

# reuse U-01's generators (PBT-07 centralisation, handoff U01-H29)
from tests.shared_kernel.generators import (
    gen_coordinates,
    gen_cost_model,
    gen_non_monotonic_cost_model_kwargs,
    gen_school_district,
    gen_travel_parameters,
)

# ---------------------------------------------------------------------------
# INV-07a: raw Haversine symmetry (tolerance)
# ---------------------------------------------------------------------------


@given(gen_coordinates(), gen_coordinates())
def test_inv07a_haversine_is_symmetric_within_tolerance(a: Coordinates, b: Coordinates) -> None:
    forward = haversine_distance_km(a, b)
    backward = haversine_distance_km(b, a)
    assert abs(forward - backward) < 1e-9


# ---------------------------------------------------------------------------
# INV-08a/b: non-negative, and exactly 0 for identical points
# ---------------------------------------------------------------------------


@given(gen_coordinates(), gen_coordinates())
def test_inv08a_haversine_is_non_negative(a: Coordinates, b: Coordinates) -> None:
    assert haversine_distance_km(a, b) >= 0.0


@given(gen_coordinates())
def test_inv08b_haversine_of_a_point_with_itself_is_zero(a: Coordinates) -> None:
    assert haversine_distance_km(a, a) == 0.0


# ---------------------------------------------------------------------------
# INV-08c: same-district metrics
# ---------------------------------------------------------------------------


@given(gen_school_district(), gen_travel_parameters())
def test_inv08c_same_district_metrics(
    district: SchoolDistrict, params: TravelParameters
) -> None:
    metrics = compute_travel_metrics(district, district, params)
    assert metrics.distance_km == 0.0
    assert metrics.time_seconds == params.same_district_fixed_seconds
    assert metrics.cost_yen == 0.0


# ---------------------------------------------------------------------------
# INV-09: travel time is monotone NON-decreasing in the detour factor
# ---------------------------------------------------------------------------


@given(
    st.floats(min_value=0.1, max_value=500.0, allow_nan=False),
    st.floats(min_value=1.0, max_value=3.0, allow_nan=False),
    st.floats(min_value=1.0, max_value=3.0, allow_nan=False),
    st.floats(min_value=1.0, max_value=120.0, allow_nan=False),
)
def test_inv09_travel_time_monotone_in_detour(
    great_circle_km: float, detour_1: float, detour_2: float, speed_kmh: float
) -> None:
    lo, hi = sorted((detour_1, detour_2))
    t_lo = travel_time_seconds(actual_travel_distance_km(great_circle_km, lo), speed_kmh)
    t_hi = travel_time_seconds(actual_travel_distance_km(great_circle_km, hi), speed_kmh)
    assert t_lo <= t_hi  # non-decreasing, not strictly increasing (ceil rounding)


# ---------------------------------------------------------------------------
# P-D01: cost is monotone non-decreasing in distance
# ---------------------------------------------------------------------------


@given(
    gen_cost_model(),
    st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
    st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
)
def test_pd01_cost_monotone_in_distance(model: CostModel, d1: float, d2: float) -> None:
    lo, hi = sorted((d1, d2))
    params = TravelParameters(cost_model=model)
    assert travel_cost_yen(lo, params) <= travel_cost_yen(hi, params) + 1e-9


# ---------------------------------------------------------------------------
# P-D02/P-D03: cost and time non-negative
# ---------------------------------------------------------------------------


@given(gen_travel_parameters(), st.floats(min_value=0.0, max_value=500.0, allow_nan=False))
def test_pd02_cost_non_negative(params: TravelParameters, distance_km: float) -> None:
    assert travel_cost_yen(distance_km, params) >= 0.0


@given(
    st.floats(min_value=0.0, max_value=500.0, allow_nan=False),
    st.floats(min_value=1.0, max_value=120.0, allow_nan=False),
)
def test_pd03_time_non_negative(distance_km: float, speed_kmh: float) -> None:
    assert travel_time_seconds(distance_km, speed_kmh) >= 0


# ---------------------------------------------------------------------------
# P-D04: travel time is monotone non-increasing in speed
# ---------------------------------------------------------------------------


@given(
    st.floats(min_value=0.1, max_value=500.0, allow_nan=False),
    st.floats(min_value=1.0, max_value=120.0, allow_nan=False),
    st.floats(min_value=1.0, max_value=120.0, allow_nan=False),
)
def test_pd04_time_monotone_in_speed(distance_km: float, s1: float, s2: float) -> None:
    lo, hi = sorted((s1, s2))
    assert travel_time_seconds(distance_km, hi) <= travel_time_seconds(distance_km, lo)


# ---------------------------------------------------------------------------
# P-D05: oracle comparison (PBT-05) - the check symmetry/non-negativity miss
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,a,b,expected_km", ORACLE_PAIRS)
def test_pd05_haversine_matches_known_distances(
    name: str, a: Coordinates, b: Coordinates, expected_km: float
) -> None:
    computed = haversine_distance_km(a, b)
    if expected_km == 0.0:
        assert computed == 0.0
    else:
        assert abs(computed - expected_km) / expected_km < 0.005  # 0.5% tolerance


# ---------------------------------------------------------------------------
# P-D06: CostModel rejects a table whose cost decreases with distance
# ---------------------------------------------------------------------------


@given(gen_non_monotonic_cost_model_kwargs())
def test_pd06_non_monotonic_cost_model_is_refused(kwargs: dict[str, object]) -> None:
    with pytest.raises(InvalidCostModelError):
        CostModel(**kwargs)  # type: ignore[arg-type]


@given(gen_cost_model())
def test_pd06_valid_cost_model_is_accepted(model: CostModel) -> None:
    # It constructed, so it is already monotone; confirm cost_for never goes backwards.
    prev = 0.0
    for distance in [0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]:
        cost = model.cost_for(distance)
        assert cost >= prev - 1e-9
        prev = cost
