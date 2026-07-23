"""LC-01 helper: the single shared metrics_for function (DP-01/02).

One pure function scores every (staff, facility) pair, and BOTH the replay travel
matrix and the baseline/optimised evaluation use it. That is what makes the
reduction attributable to the assignment rule alone (FR-05.1.4): baseline and
optimised are measured on identical metrics by construction, not by two
implementations that might drift.

Distance/cost reuse U-02's compute_travel_metrics, which already handles the
same-district rule (distance 0, cost 0, fixed time; FR-03.7). U-05 writes no
distance logic of its own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from distance_cost import compute_travel_metrics
from shared_kernel import (
    Facility,
    FacilityId,
    SchoolDistrict,
    SchoolDistrictId,
    Staff,
    StaffId,
    TravelMetrics,
    TravelParameters,
)

MetricsFor = Callable[[StaffId, FacilityId], TravelMetrics]


@dataclass(frozen=True)
class Master:
    """The current master data the comparison evaluates against (FR-05.1.5, A-09)."""

    staff_by_id: dict[StaffId, Staff]
    facilities_by_id: dict[FacilityId, Facility]
    districts_by_id: dict[SchoolDistrictId, SchoolDistrict]


def make_metrics_for(master: Master, params: TravelParameters) -> MetricsFor:
    """Build the shared metrics function, closing over the current master."""

    def metrics_for(staff_id: StaffId, facility_id: FacilityId) -> TravelMetrics:
        staff = master.staff_by_id[staff_id]
        facility = master.facilities_by_id[facility_id]
        return compute_travel_metrics(
            master.districts_by_id[staff.residence_district_id],
            master.districts_by_id[facility.district_id],
            params,
        )

    return metrics_for


__all__ = ["Master", "MetricsFor", "make_metrics_for"]
