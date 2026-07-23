"""Value objects.

Every type here is ``frozen=True`` and validates in ``__post_init__``.

Those two decisions are inseparable. Creation-time validation on a *mutable*
object is theatre::

    c = Coordinates(latitude=35.0, longitude=139.0)   # validated
    c.latitude = 999.0                                # invariant broken

Frozen + validate-on-construct together give downstream units the guarantee they
actually rely on: if the value exists, its invariant holds, for its whole life.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from itertools import pairwise

from .enums import JobType, Position, Qualification
from .exceptions import (
    AllWeightsZeroError,
    InvalidCoordinatesError,
    InvalidCostModelError,
    InvalidTravelParametersError,
    NegativeWeightError,
)

# Default travel parameters. Externalised as configuration in production
# (NFR-M03); these are the defaults a fresh install starts from.
DEFAULT_DETOUR_FACTOR = 1.3
DEFAULT_AVERAGE_SPEED_KMH = 30.0
DEFAULT_SAME_DISTRICT_FIXED_SECONDS = 900  # 15 minutes
DEFAULT_TIME_LIMIT_SECONDS = 300  # NFR-P02


@dataclass(frozen=True, slots=True)
class Coordinates:
    """A point on the earth. BR-01."""

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        for name, value in (("latitude", self.latitude), ("longitude", self.longitude)):
            if math.isnan(value) or math.isinf(value):
                raise InvalidCoordinatesError(
                    f"{name} is not a finite number", violated_rule="BR-01"
                )
        if not -90.0 <= self.latitude <= 90.0:
            raise InvalidCoordinatesError("latitude outside [-90, 90]", violated_rule="BR-01")
        if not -180.0 <= self.longitude <= 180.0:
            raise InvalidCoordinatesError("longitude outside [-180, 180]", violated_rule="BR-01")


@dataclass(frozen=True, slots=True)
class TravelMetrics:
    """Distance, time and cost between one staff member and one facility.

    ``time_seconds`` is an integer count of *seconds*, not minutes. Rounding each
    staff member's travel time to whole minutes and then summing across 2,000
    people accumulates up to ~1,000 minutes of error in the total; seconds makes
    that error negligible (NFR-U01-R04).

    ``cost_yen`` stays a float internally and is rounded to whole yen only at
    display and export, for the same reason.
    """

    distance_km: float
    time_seconds: int
    cost_yen: float


@dataclass(frozen=True, slots=True)
class QualificationRequirement:
    """A facility requires ``required_count`` people holding ``requirement``."""

    requirement: Qualification | Position | JobType
    required_count: int


@dataclass(frozen=True, slots=True)
class ObjectiveWeights:
    """Weights of the three objective terms. BR-02.

    ``inequity`` weights the *maximum* travel time (minimax), not the variance.
    Minimising a maximum is linear -- one auxiliary variable T_max with
    ``T_max >= t_i`` for all i -- so it stays inside a MILP. Minimising variance
    is quadratic and a MILP solver cannot express it directly (handoff U01-H5).
    """

    travel_time: float
    travel_cost: float
    inequity: float

    def __post_init__(self) -> None:
        weights = (self.travel_time, self.travel_cost, self.inequity)
        if any(w < 0.0 for w in weights):
            raise NegativeWeightError("objective weights must be >= 0", violated_rule="BR-02")
        if all(w == 0.0 for w in weights):
            # With every weight zero the objective is a constant and the solver
            # would return an arbitrary feasible assignment.
            raise AllWeightsZeroError(
                "at least one objective weight must be positive", violated_rule="BR-02"
            )


#: Tolerance for the cost-model monotonicity check (BR-D04). A boundary drop
#: smaller than this is floating-point noise, not a real decrease. Well below one
#: yen, so no genuine "further is cheaper" table slips through.
_MONOTONIC_TOLERANCE_YEN = 1e-6


class CostRule(Enum):
    """How a distance band computes its cost."""

    FLAT = "FLAT"  # a fixed amount, independent of distance
    PER_KM = "PER_KM"  # amount_yen per kilometre


@dataclass(frozen=True, slots=True)
class CostBand:
    """One band of the distance-band cost model. BR-D01.

    ``upper_bound_km`` is EXCLUSIVE; ``None`` means unbounded (the top band).
    """

    upper_bound_km: float | None
    rule: CostRule
    amount_yen: float

    def __post_init__(self) -> None:
        if self.upper_bound_km is not None:
            if math.isnan(self.upper_bound_km) or math.isinf(self.upper_bound_km):
                raise InvalidCostModelError(
                    "upper_bound_km is not finite", violated_rule="BR-D01"
                )
            if self.upper_bound_km <= 0.0:
                raise InvalidCostModelError("upper_bound_km <= 0", violated_rule="BR-D01")
        if self.amount_yen < 0.0:
            raise InvalidCostModelError("amount_yen < 0", violated_rule="BR-D01")

    def cost_at(self, distance_km: float) -> float:
        """Cost this band charges for ``distance_km`` (caller ensures membership)."""
        if self.rule is CostRule.FLAT:
            return self.amount_yen
        return distance_km * self.amount_yen


@dataclass(frozen=True, slots=True)
class CostModel:
    """Distance-band cost model. FR-03.5. BR-D02, BR-D04.

    The band model is a step function, but the optimization stays linear: the
    cost of each (staff, facility) pair is a constant computed before the solve,
    so it is only a coefficient c_ij in the objective's linear term.

    The subtle rule is BR-D04. A band table can accidentally make cost DECREASE
    with distance - e.g. "2-10 km flat 300 yen" then "10 km+ at 20 yen/km" makes
    10 km cost 200 yen, less than 9.9 km. The optimizer minimises total cost, so
    it would then prefer sending someone FURTHER. That is refused at construction.
    """

    bands: tuple[CostBand, ...]

    def __post_init__(self) -> None:
        if not self.bands:
            raise InvalidCostModelError("cost model has no bands", violated_rule="BR-D02")

        # BR-D02: exactly one unbounded band, and it is last.
        unbounded = [i for i, b in enumerate(self.bands) if b.upper_bound_km is None]
        if len(unbounded) != 1:
            raise InvalidCostModelError(
                "cost model must have exactly one unbounded (final) band",
                violated_rule="BR-D02",
            )
        if unbounded[0] != len(self.bands) - 1:
            raise InvalidCostModelError(
                "the unbounded band must be last", violated_rule="BR-D02"
            )

        # BR-D02: strictly increasing upper bounds among the bounded bands.
        bounded = [b.upper_bound_km for b in self.bands[:-1]]
        for lower, upper in pairwise(bounded):
            # lower and upper are non-None for bounded bands.
            if upper is not None and lower is not None and upper <= lower:
                raise InvalidCostModelError(
                    "band upper bounds must be strictly increasing",
                    violated_rule="BR-D02",
                )

        self._validate_monotonic()

    def _validate_monotonic(self) -> None:
        """BR-D04: cost must be monotone non-decreasing in distance.

        Cost is monotone within each band by construction (FLAT is constant,
        PER_KM has a non-negative slope), so only the boundaries can break it.
        At each boundary b_k, the cost just below it (band k, at b_k) must not
        exceed the cost just at it (band k+1, at b_k).

        The comparison uses a small tolerance. A boundary meant to be continuous
        -- e.g. public transit flat 300 yen then taxi at 30 yen/km, which is
        exactly 300 yen at a 10 km boundary -- can land a sub-nano-yen above the
        at-value through floating-point rounding. That is not a real decrease and
        must not be rejected; a coordinator can legitimately configure such a
        boundary.
        """
        for lower_band, upper_band in pairwise(self.bands):
            boundary = lower_band.upper_bound_km
            if boundary is None:  # pragma: no cover - only the last band is None
                continue
            cost_below = lower_band.cost_at(boundary)
            cost_above = upper_band.cost_at(boundary)
            if cost_below - cost_above > _MONOTONIC_TOLERANCE_YEN:
                raise InvalidCostModelError(
                    f"cost decreases at the {boundary} km boundary "
                    f"({cost_below} -> {cost_above})",
                    violated_rule="BR-D04",
                )

    def cost_for(self, distance_km: float) -> float:
        """Cost for ``distance_km``. Linear scan over bands (BR-D08)."""
        for band in self.bands:
            if band.upper_bound_km is None or distance_km < band.upper_bound_km:
                return band.cost_at(distance_km)
        # Unreachable: BR-D02 guarantees a final unbounded band.
        raise InvalidCostModelError(  # pragma: no cover
            "no band matched", violated_rule="BR-D02"
        )


#: Default distance-band cost model (FR-03.5). Coordinator-configurable.
DEFAULT_COST_MODEL = CostModel(
    bands=(
        CostBand(upper_bound_km=2.0, rule=CostRule.FLAT, amount_yen=0.0),  # walking
        CostBand(upper_bound_km=10.0, rule=CostRule.FLAT, amount_yen=300.0),  # public transit
        CostBand(upper_bound_km=None, rule=CostRule.PER_KM, amount_yen=400.0),  # taxi
    )
)


@dataclass(frozen=True, slots=True)
class TravelParameters:
    """Tunables for the distance/time/cost calculation. BR-D03.

    All externalised as configuration; never hardcoded (NFR-M03).
    """

    detour_factor: float = DEFAULT_DETOUR_FACTOR
    average_speed_kmh: float = DEFAULT_AVERAGE_SPEED_KMH
    same_district_fixed_seconds: int = DEFAULT_SAME_DISTRICT_FIXED_SECONDS
    cost_model: CostModel = field(default_factory=lambda: DEFAULT_COST_MODEL)

    def __post_init__(self) -> None:
        if self.detour_factor < 1.0:
            # A route shorter than the straight line does not exist.
            raise InvalidTravelParametersError("detour_factor < 1.0", violated_rule="BR-D03")
        if self.average_speed_kmh <= 0.0:
            raise InvalidTravelParametersError("average_speed_kmh <= 0", violated_rule="BR-D03")
        if self.same_district_fixed_seconds < 0:
            raise InvalidTravelParametersError(
                "same_district_fixed_seconds < 0", violated_rule="BR-D03"
            )


@dataclass(frozen=True, slots=True)
class OptimizationParameters:
    """Solver-facing knobs for one optimization run."""

    weights: ObjectiveWeights
    time_limit_seconds: int = DEFAULT_TIME_LIMIT_SECONDS
    department_cap_limit: int = 1
    allow_c3_demotion: bool = False
    random_seed: int = 0

    def __post_init__(self) -> None:
        if self.time_limit_seconds <= 0:
            raise InvalidTravelParametersError("time_limit_seconds <= 0", violated_rule="BR-04")
        if self.department_cap_limit <= 0:
            raise InvalidTravelParametersError("department_cap_limit <= 0", violated_rule="BR-04")


__all__ = [
    "DEFAULT_AVERAGE_SPEED_KMH",
    "DEFAULT_COST_MODEL",
    "DEFAULT_DETOUR_FACTOR",
    "DEFAULT_SAME_DISTRICT_FIXED_SECONDS",
    "DEFAULT_TIME_LIMIT_SECONDS",
    "Coordinates",
    "CostBand",
    "CostModel",
    "CostRule",
    "ObjectiveWeights",
    "OptimizationParameters",
    "QualificationRequirement",
    "TravelMetrics",
    "TravelParameters",
]
