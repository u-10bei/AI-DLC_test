"""Property-based tests for U-05 (P-CMP01..05).

  P-CMP01/02  reduction and rate are computed consistently.
  P-CMP03     if the baseline is feasible in the replay, the optimised objective
              is <= the baseline objective (metamorphic).
  P-CMP04     baseline and optimised are scored on the same metrics_for.
  P-CMP05     the report / CSV carry no PII.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from comparison_report import (
    ComparisonReport,
    ComparisonService,
    Master,
    build_replay,
    export_report_csv,
    make_metrics_for,
    objective_of,
)
from optimization_engine import InfeasibilityDiagnosis, OptimizationService
from shared_kernel import HistoricalRecord, OptimizationParameters

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

_SETTINGS = settings(max_examples=30, deadline=None)

# Two districts: SD1 (facility location) and SD2 (far).
_DISTRICTS = (district("SD1", 35.00, 139.00), district("SD2", 35.50, 139.50))


@st.composite
def gen_feasible_scenario(draw: st.DrawFn) -> tuple[HistoricalRecord, Master, OptimizationParameters]:
    n_staff = draw(st.integers(min_value=2, max_value=5))
    residences = [draw(st.sampled_from(["SD1", "SD2"])) for _ in range(n_staff)]
    staff_list = tuple(staff(f"S{i + 1}", residences[i]) for i in range(n_staff))
    headcount = draw(st.integers(min_value=1, max_value=n_staff))
    # actual assignment: the first `headcount` staff (distinct) -> C1/C2 satisfied
    actual = tuple(assignment(f"S{i + 1}", "F1") for i in range(headcount))
    declared = tuple(declaration(f"S{i + 1}") for i in range(n_staff))  # all available
    record = historical(actual, declared)
    mstr = master(staff_list, (facility("F1", "SD1", headcount),), _DISTRICTS)
    weights = draw(
        st.lists(st.floats(min_value=0.0, max_value=3.0, allow_nan=False), min_size=3, max_size=3)
        .filter(lambda ws: any(w > 0.0 for w in ws))  # ObjectiveWeights needs one positive
    )
    params = opt_params(travel_time=weights[0], travel_cost=weights[1], inequity=weights[2])
    return record, mstr, params


@_SETTINGS
@given(gen_feasible_scenario())
def test_reduction_and_rate_are_consistent(scenario: tuple[HistoricalRecord, Master, OptimizationParameters]) -> None:
    record, mstr, params = scenario
    report = ComparisonService().compare(
        record, event(), mstr, optimization_parameters=params, travel_parameters=travel_params(), now=NOW
    )
    assert isinstance(report, ComparisonReport)
    # P-CMP01
    assert report.time_reduction_seconds == report.baseline_time_seconds - report.optimized_time_seconds
    assert abs(report.cost_reduction_yen - (report.baseline_cost_yen - report.optimized_cost_yen)) < 1e-6
    # P-CMP02
    expected_time_rate = (
        report.time_reduction_seconds / report.baseline_time_seconds
        if report.baseline_time_seconds != 0
        else 0.0
    )
    assert abs(report.time_reduction_rate - expected_time_rate) < 1e-9


@_SETTINGS
@given(gen_feasible_scenario())
def test_optimised_objective_dominates_feasible_baseline(
    scenario: tuple[HistoricalRecord, Master, OptimizationParameters]
) -> None:
    """P-CMP03: the optimiser never does worse than the (feasible) baseline."""
    record, mstr, params = scenario
    metrics_for = make_metrics_for(mstr, travel_params())
    problem = build_replay(record, event(), mstr, params, metrics_for)
    result = OptimizationService().optimize(problem, now=NOW)
    assert not isinstance(result, InfeasibilityDiagnosis)  # generator is feasible
    baseline_obj = objective_of(problem, record.actual_assignments)
    optimised_obj = objective_of(problem, result.assignments)
    assert optimised_obj <= baseline_obj + 1e-4


@_SETTINGS
@given(gen_feasible_scenario())
def test_report_csv_has_no_pii(scenario: tuple[HistoricalRecord, Master, OptimizationParameters]) -> None:
    record, mstr, params = scenario
    report = ComparisonService().compare(
        record, event(), mstr, optimization_parameters=params, travel_parameters=travel_params(), now=NOW
    )
    assert isinstance(report, ComparisonReport)
    csv = export_report_csv(report).decode("utf-8")
    for i in range(1, 6):
        assert f"name-S{i}" not in csv
