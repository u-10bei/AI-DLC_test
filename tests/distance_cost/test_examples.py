"""Example-based tests for U-02 (PBT-10)."""

from __future__ import annotations

import pytest

from distance_cost import (
    compute_district_distance_matrix,
    compute_travel_metrics,
    travel_cost_yen,
    travel_time_seconds,
)
from shared_kernel import (
    Coordinates,
    CostBand,
    CostModel,
    CostRule,
    InvalidCostModelError,
    SchoolDistrict,
    SchoolDistrictId,
    TravelParameters,
)

TOKYO = Coordinates(35.681236, 139.767125)
OSAKA = Coordinates(34.702485, 135.495951)


def _district(id_: str, point: Coordinates) -> SchoolDistrict:
    return SchoolDistrict(id=SchoolDistrictId(id_), name=id_, representative_point=point)


# ---------------------------------------------------------------------------
# US-15: distance / time / cost with the default parameters
# ---------------------------------------------------------------------------


def test_us15_metrics_for_two_districts() -> None:
    a = _district("SD1", TOKYO)
    b = _district("SD2", OSAKA)
    metrics = compute_travel_metrics(a, b, TravelParameters())

    # great circle ~403 km, detour 1.3 -> ~524 km
    assert 520.0 < metrics.distance_km < 528.0
    # >10 km, so taxi band: distance * 400 yen/km
    assert metrics.cost_yen == pytest.approx(metrics.distance_km * 400.0)
    # 524 km / 30 kmh -> ~62,880 s
    assert metrics.time_seconds > 60_000


def test_us15_same_district() -> None:
    a = _district("SD1", TOKYO)
    metrics = compute_travel_metrics(a, a, TravelParameters())
    assert metrics.distance_km == 0.0
    assert metrics.time_seconds == 900  # 15 minutes, not 0 (FR-03.7)
    assert metrics.cost_yen == 0.0


# ---------------------------------------------------------------------------
# Distance-band boundaries (the taxi-threshold step)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "distance_km,expected_yen",
    [
        (0.0, 0.0),  # walking
        (1.9, 0.0),  # walking, just below the 2 km boundary
        (2.0, 300.0),  # public transit, the boundary is inclusive on the lower side
        (9.9, 300.0),  # public transit, just below 10 km
        (10.0, 4000.0),  # taxi: 10 * 400
        (25.0, 10000.0),  # taxi: 25 * 400
    ],
)
def test_default_cost_bands(distance_km: float, expected_yen: float) -> None:
    assert travel_cost_yen(distance_km, TravelParameters()) == pytest.approx(expected_yen)


def test_the_taxi_threshold_is_a_real_step() -> None:
    """9.9 km costs 300 yen, 10.0 km costs 4000 yen. That jump is the point.

    A linear model would make these nearly equal, and the optimizer would have no
    reason to keep anyone below the taxi threshold - which is problem item (2).
    """
    params = TravelParameters()
    assert travel_cost_yen(9.9, params) == 300.0
    assert travel_cost_yen(10.0, params) == 4000.0


# ---------------------------------------------------------------------------
# BR-D04: a cost table that decreases with distance is refused
# ---------------------------------------------------------------------------


def test_non_monotonic_cost_model_is_refused() -> None:
    """300 yen flat to 10 km, then 20 yen/km. At 10 km that is 200 yen - cheaper.

    The optimizer would send people further to save money. Refused at construction.
    """
    with pytest.raises(InvalidCostModelError, match="decreases"):
        CostModel(
            bands=(
                CostBand(upper_bound_km=10.0, rule=CostRule.FLAT, amount_yen=300.0),
                CostBand(upper_bound_km=None, rule=CostRule.PER_KM, amount_yen=20.0),
            )
        )


def test_cost_model_without_unbounded_final_band_is_refused() -> None:
    """Every band bounded -> a large distance belongs to no band (BR-D02)."""
    with pytest.raises(InvalidCostModelError):
        CostModel(bands=(CostBand(upper_bound_km=10.0, rule=CostRule.FLAT, amount_yen=0.0),))


def test_cost_model_with_two_unbounded_bands_is_refused() -> None:
    with pytest.raises(InvalidCostModelError):
        CostModel(
            bands=(
                CostBand(upper_bound_km=None, rule=CostRule.FLAT, amount_yen=100.0),
                CostBand(upper_bound_km=None, rule=CostRule.FLAT, amount_yen=200.0),
            )
        )


# ---------------------------------------------------------------------------
# travel time rounds up (BR-D06)
# ---------------------------------------------------------------------------


def test_travel_time_rounds_up() -> None:
    # 1 km at 30 km/h = 120.0 s exactly
    assert travel_time_seconds(1.0, 30.0) == 120
    # 1.001 km at 30 km/h = 120.12 s -> ceil 121
    assert travel_time_seconds(1.001, 30.0) == 121


# ---------------------------------------------------------------------------
# distance matrix
# ---------------------------------------------------------------------------


def test_distance_matrix_has_triangular_entry_count() -> None:
    districts = [
        _district("SD1", TOKYO),
        _district("SD2", OSAKA),
        _district("SD3", Coordinates(35.170915, 136.881537)),
    ]
    entries = compute_district_distance_matrix(districts)
    # D(D+1)/2 for D=3 -> 6 (includes the diagonal)
    assert len(entries) == 6


def test_distance_matrix_keys_are_canonicalised() -> None:
    a = _district("SDB", TOKYO)
    b = _district("SDA", OSAKA)  # deliberately out of order
    entries = compute_district_distance_matrix([a, b])
    cross = [e for e in entries if e.district_a != e.district_b]
    assert len(cross) == 1
    # canonicalised: smaller ID first
    assert cross[0].district_a == "SDA"
    assert cross[0].district_b == "SDB"
