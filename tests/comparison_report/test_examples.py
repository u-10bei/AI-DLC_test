"""Example-based tests for U-05: reduction, infeasible replay, manual baseline."""

from __future__ import annotations

from comparison_report import (
    ComparisonReport,
    ComparisonService,
    ManualBaseline,
    Master,
    export_report_csv,
    parse_historical_assignments,
)
from optimization_engine import InfeasibilityDiagnosis
from shared_kernel import EventId, HistoricalRecord, OptimizationParameters, StaffId

from .support import (
    NOW,
    assignment,
    declaration,
    district,
    event,
    facility,
    historical,
    master,
    opt_params,
    staff,
    travel_params,
)

# Near district SD1 (where F1 sits) vs far district SD2.
_DISTRICTS = (district("SD1", 35.00, 139.00), district("SD2", 35.50, 139.50))


def _compare(
    record: HistoricalRecord, mstr: Master, params: OptimizationParameters
) -> ComparisonReport | InfeasibilityDiagnosis:
    return ComparisonService().compare(
        record, event(), mstr, optimization_parameters=params, travel_parameters=travel_params(), now=NOW
    )


def test_reduction_when_far_staff_was_assigned() -> None:
    staff_list = (staff("S1", "SD1"), staff("S2", "SD2"))  # S1 near, S2 far
    mstr = master(staff_list, (facility("F1", "SD1", 1),), _DISTRICTS)
    record = historical(
        (assignment("S2", "F1"),),  # baseline assigned the FAR staff
        (declaration("S1"), declaration("S2")),
    )
    report = _compare(record, mstr, opt_params())
    assert isinstance(report, ComparisonReport)
    # optimiser picks the near staff -> positive reduction in both metrics
    assert report.time_reduction_seconds > 0
    assert report.cost_reduction_yen > 0
    assert report.assigned_count == 1


def test_reduction_can_be_negative_when_weights_favour_the_other_metric() -> None:
    """The optimiser minimises the weighted objective, not either metric alone (BR-CMP08)."""
    # S1: short time but high cost; S2: long time but zero cost (same district as F1).
    # With cost weighted heavily the optimiser prefers S2 -> time may rise vs a time baseline.
    staff_list = (staff("S1", "SD2"), staff("S2", "SD1"))
    mstr = master(staff_list, (facility("F1", "SD1", 1),), _DISTRICTS)
    record = historical((assignment("S1", "F1"),), (declaration("S1"), declaration("S2")))
    report = _compare(record, mstr, opt_params(travel_time=0.0, travel_cost=1.0, inequity=0.0))
    assert isinstance(report, ComparisonReport)
    # cost must not increase (that is what is being minimised)
    assert report.cost_reduction_yen >= 0.0


def test_infeasible_replay_returns_diagnosis() -> None:
    # headcount 2 (two actual assignments) but only one staff declared available
    staff_list = (staff("S1", "SD1"),)
    mstr = master(staff_list, (facility("F1", "SD1", 1),), _DISTRICTS)
    record = historical(
        (assignment("S1", "F1"), assignment("S2", "F1")),  # 2 actuals -> headcount 2
        (declaration("S1"),),  # only S1 available
    )
    result = _compare(record, mstr, opt_params())
    assert isinstance(result, InfeasibilityDiagnosis)


def test_report_and_csv_carry_no_pii() -> None:
    staff_list = (staff("S1", "SD1"), staff("S2", "SD2"))
    mstr = master(staff_list, (facility("F1", "SD1", 1),), _DISTRICTS)
    record = historical((assignment("S2", "F1"),), (declaration("S1"), declaration("S2")))
    report = _compare(record, mstr, opt_params())
    assert isinstance(report, ComparisonReport)
    csv = export_report_csv(report).decode("utf-8")
    assert "name-S1" not in csv
    assert "name-S2" not in csv


def test_manual_baseline_to_historical_record() -> None:
    manual = ManualBaseline(
        event_id=EventId("E1"),
        actual_assignments=(assignment("S1", "F1"),),
        availability_declarations=(declaration("S1"),),
    )
    record = manual.to_historical_record()
    assert record.event_id == EventId("E1")
    assert record.actual_assignments == (assignment("S1", "F1"),)


def test_parse_historical_assignments() -> None:
    raw = "職員ID,施設ID\nS1,F1\nS2,F2\n".encode()
    assignments = parse_historical_assignments(EventId("E1"), raw)
    assert len(assignments) == 2
    assert assignments[0].staff_id == StaffId("S1")
