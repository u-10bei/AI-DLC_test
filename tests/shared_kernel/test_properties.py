"""Property-based tests for U-01 (PBT-03, PBT-04).

Each test names the property it checks (P-01..P-08 from domain-entities.md
section 7) and the category PBT-01 assigned it.

These do not replace the example-based tests in test_examples.py; PBT-10 forbids
property tests from being the only coverage of a business-critical path.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from shared_kernel import (
    AllWeightsZeroError,
    AmbiguousDeclarationError,
    Assignment,
    AssignmentResult,
    AvailabilityDeclaration,
    ConstraintViolation,
    Coordinates,
    DuplicateAssignmentError,
    EventId,
    EventStatus,
    EventType,
    Facility,
    FacilityId,
    InvalidCoordinatesError,
    InvalidTravelParametersError,
    JobType,
    NegativeWeightError,
    NonDemotableConstraintViolationError,
    ObjectiveWeights,
    Position,
    Qualification,
    QualificationRequirementExceedsHeadcountError,
    ReasonCategory,
    SolverStatus,
    StaffId,
    TravelParameters,
    effective_declaration_for,
    from_japanese,
    to_japanese,
)

from .generators import (
    gen_assignment,
    gen_availability_declaration,
    gen_coordinates,
    gen_event_id,
    gen_facility,
    gen_invalid_facility,
    gen_objective_weights,
    gen_staff_id,
    gen_travel_parameters,
)

# ---------------------------------------------------------------------------
# P-01 (Invariant) / P-02 (Idempotence): effective_declaration_for
#
# The most important properties in this unit. Getting them wrong means a staff
# member on health-related leave is deployed to a shelter during a disaster.
# ---------------------------------------------------------------------------


@st.composite
def _declaration_history(draw: st.DrawFn) -> tuple[StaffId, EventId, list[AvailabilityDeclaration]]:
    """A history for one (staff, event) pair with strictly distinct timestamps."""
    staff_id = draw(gen_staff_id)
    event_id = draw(gen_event_id)
    count = draw(st.integers(min_value=1, max_value=5))
    base = datetime(2026, 1, 1, tzinfo=UTC)

    declarations: list[AvailabilityDeclaration] = []
    for offset in draw(
        st.lists(
            st.integers(min_value=0, max_value=10_000),
            min_size=count,
            max_size=count,
            unique=True,
        )
    ):
        template = draw(gen_availability_declaration(staff_id=staff_id, event_id=event_id))
        declarations.append(
            AvailabilityDeclaration(
                staff_id=template.staff_id,
                event_id=template.event_id,
                is_available=template.is_available,
                declared_at=base + timedelta(seconds=offset),
                reason_category=template.reason_category,
                other_reason_note=template.other_reason_note,
            )
        )
    return staff_id, event_id, declarations


@given(_declaration_history())
def test_p01_effective_declaration_is_the_latest(
    data: tuple[StaffId, EventId, list[AvailabilityDeclaration]],
) -> None:
    """P-01 (Invariant): exactly one declaration is in force, the newest one."""
    staff_id, event_id, history = data

    result = effective_declaration_for(staff_id, event_id, history)

    assert result is not None
    assert result.declared_at == max(d.declared_at for d in history)
    assert result in history


@given(_declaration_history())
def test_p02_effective_declaration_is_idempotent(
    data: tuple[StaffId, EventId, list[AvailabilityDeclaration]],
) -> None:
    """P-02 (Idempotence): calling it twice on the same history gives the same answer."""
    staff_id, event_id, history = data

    first = effective_declaration_for(staff_id, event_id, history)
    second = effective_declaration_for(staff_id, event_id, history)

    assert first == second


@given(gen_staff_id, gen_event_id, st.lists(gen_availability_declaration(), max_size=4))
def test_undeclared_is_distinct_from_unavailable(
    staff_id: StaffId, event_id: EventId, history: list[AvailabilityDeclaration]
) -> None:
    """No declaration -> None. A declaration -> the declaration, whatever it says.

    'Undeclared' and 'declared unavailable' both keep a person out of the
    optimization, but they are different facts and the function must not
    conflate them (handoff U01-H10).
    """
    unrelated = [d for d in history if (d.staff_id, d.event_id) != (staff_id, event_id)]

    assert effective_declaration_for(staff_id, event_id, unrelated) is None


@given(_declaration_history())
def test_ambiguous_history_is_refused(
    data: tuple[StaffId, EventId, list[AvailabilityDeclaration]],
) -> None:
    """Two declarations sharing the newest timestamp -> refuse, do not guess."""
    staff_id, event_id, history = data
    latest = max(d.declared_at for d in history)
    duplicate = AvailabilityDeclaration(
        staff_id=staff_id,
        event_id=event_id,
        is_available=True,
        declared_at=latest,
        reason_category=None,
    )
    contender = next(d for d in history if d.declared_at == latest)
    assume(contender != duplicate)

    with pytest.raises(AmbiguousDeclarationError):
        effective_declaration_for(staff_id, event_id, [*history, duplicate])


# ---------------------------------------------------------------------------
# P-03 (Range constraint): Coordinates
# ---------------------------------------------------------------------------


@given(gen_coordinates())
def test_p03_generated_coordinates_are_in_range(coords: Coordinates) -> None:
    """P-03: the generator only produces constructible coordinates."""
    assert -90.0 <= coords.latitude <= 90.0
    assert -180.0 <= coords.longitude <= 180.0


@given(
    st.floats(allow_nan=True, allow_infinity=True),
    st.floats(allow_nan=True, allow_infinity=True),
)
def test_p03_out_of_range_coordinates_are_refused(latitude: float, longitude: float) -> None:
    """P-03: anything outside the range, NaN or infinite, refuses construction."""
    in_range = (
        not math.isnan(latitude)
        and not math.isnan(longitude)
        and not math.isinf(latitude)
        and not math.isinf(longitude)
        and -90.0 <= latitude <= 90.0
        and -180.0 <= longitude <= 180.0
    )
    assume(not in_range)

    with pytest.raises(InvalidCoordinatesError):
        Coordinates(latitude=latitude, longitude=longitude)


# ---------------------------------------------------------------------------
# P-04 (Range constraint): ObjectiveWeights
# ---------------------------------------------------------------------------


@given(gen_objective_weights())
def test_p04_generated_weights_are_valid(weights: ObjectiveWeights) -> None:
    """P-04: non-negative, and at least one strictly positive."""
    values = (weights.travel_time, weights.travel_cost, weights.inequity)
    assert all(w >= 0.0 for w in values)
    assert any(w > 0.0 for w in values)


def test_p04_all_zero_weights_are_refused() -> None:
    """All-zero weights make the objective a constant; the solver would return anything."""
    with pytest.raises(AllWeightsZeroError):
        ObjectiveWeights(travel_time=0.0, travel_cost=0.0, inequity=0.0)


@given(st.floats(min_value=-100.0, max_value=-1e-9, allow_nan=False))
def test_p04_negative_weight_is_refused(negative: float) -> None:
    with pytest.raises(NegativeWeightError):
        ObjectiveWeights(travel_time=negative, travel_cost=1.0, inequity=1.0)


# ---------------------------------------------------------------------------
# P-05 (Invariant): Facility qualification requirements
# ---------------------------------------------------------------------------


@given(gen_facility())
def test_p05_generated_facility_satisfies_br03(facility: Facility) -> None:
    """P-05: qualification counts never exceed the facility's headcount."""
    total = sum(req.required_count for req in facility.qualification_requirements)
    assert total <= facility.required_headcount

    requirements = [req.requirement for req in facility.qualification_requirements]
    assert len(requirements) == len(set(requirements))


@given(gen_invalid_facility())
def test_p05_overspecified_facility_is_refused(kwargs: dict[str, object]) -> None:
    """P-05: the rejection path.

    gen_facility() only produces valid facilities, so it can never reach this
    branch. The negative generator exists precisely for it.
    """
    with pytest.raises(QualificationRequirementExceedsHeadcountError):
        Facility(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# P-06 (Invariant): assignment uniqueness  /  P-07: only C3 may be violated
# ---------------------------------------------------------------------------


def _result(
    event_id: EventId,
    assignments: tuple[Assignment, ...] = (),
    violations: tuple[ConstraintViolation, ...] = (),
) -> AssignmentResult:
    return AssignmentResult(
        event_id=event_id,
        assignments=assignments,
        objective_value=1.0,
        optimality_gap=0.0,
        solver_status=SolverStatus.OPTIMAL,
        computed_at=datetime(2026, 7, 9, tzinfo=UTC),
        violations=violations,
    )


@given(gen_event_id, gen_staff_id, st.lists(st.text(min_size=1, max_size=4), min_size=2, max_size=2))
def test_p06_duplicate_staff_in_one_event_is_refused(
    event_id: EventId, staff_id: StaffId, facility_names: list[str]
) -> None:
    """P-06 (INV-01): one staff member, one facility, per event."""
    duplicated = tuple(
        Assignment(event_id=event_id, staff_id=staff_id, facility_id=FacilityId(name))
        for name in facility_names
    )

    with pytest.raises(DuplicateAssignmentError):
        _result(event_id, assignments=duplicated)


@given(gen_event_id, st.sampled_from(["C1", "C2", "C4", "C5"]))
def test_p07_non_demotable_violation_is_refused(event_id: EventId, constraint_id: str) -> None:
    """P-07: FR-04.5 demotes C3 and nothing else.

    A result carrying any other violation means the solver is wrong. It fails
    here, at the type boundary, rather than reaching the comparison report.
    """
    violation = ConstraintViolation(constraint_id=constraint_id, detail="x")  # type: ignore[arg-type]

    with pytest.raises(NonDemotableConstraintViolationError):
        _result(event_id, violations=(violation,))


@given(gen_event_id)
def test_p07_c3_violation_is_accepted(event_id: EventId) -> None:
    """C3 is the one constraint a result is allowed to violate (big-M demotion)."""
    result = _result(
        event_id,
        violations=(ConstraintViolation(constraint_id="C3", detail="manager short by 1"),),
    )
    assert result.violations[0].constraint_id == "C3"


# ---------------------------------------------------------------------------
# P-08 (Range constraint): TravelParameters
# ---------------------------------------------------------------------------


@given(gen_travel_parameters())
def test_p08_generated_travel_parameters_are_valid(params: TravelParameters) -> None:
    assert params.detour_factor >= 1.0
    assert params.average_speed_kmh > 0.0


@given(st.floats(min_value=0.0, max_value=0.999, allow_nan=False))
def test_p08_detour_factor_below_one_is_refused(factor: float) -> None:
    """A route shorter than the straight line does not exist."""
    with pytest.raises(InvalidTravelParametersError):
        TravelParameters(detour_factor=factor)


# ---------------------------------------------------------------------------
# Round-trip (PBT-02): the enum conversion table
# ---------------------------------------------------------------------------


@given(
    st.sampled_from(
        [
            *list(JobType),
            *list(Position),
            *list(Qualification),
            *list(EventType),
            *list(EventStatus),
            *list(ReasonCategory),
        ]
    )
)
def test_enum_conversion_round_trips(member: JobType | Position | Qualification) -> None:
    """PBT-02: from_japanese(to_japanese(x)) == x, for every member of every enum."""
    assert from_japanese(type(member), to_japanese(member)) is member


# ---------------------------------------------------------------------------
# Frozen: creation-time validation would be pointless on a mutable object
# ---------------------------------------------------------------------------


@given(gen_coordinates())
def test_value_objects_are_frozen(coords: Coordinates) -> None:
    with pytest.raises(AttributeError):
        coords.latitude = 999.0  # type: ignore[misc]


@given(gen_assignment())
def test_entities_are_frozen(assignment: Assignment) -> None:
    with pytest.raises(AttributeError):
        assignment.is_pinned = True  # type: ignore[misc]
