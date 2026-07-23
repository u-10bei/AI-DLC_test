"""Domain generators (PBT-07).

PBT-07 forbids driving domain-typed parameters with bare primitive strategies.
`st.floats()` for a latitude produces mostly nonsense; `st.text()` for a staff ID
produces nothing a real import would ever contain. These generators respect the
business constraints, so a failing example is a failure that could actually
happen.

They are centralised here and reused by U-02 through U-07's tests, which is the
other half of what PBT-07 asks for.

Note ``gen_invalid_facility``: every other generator produces *valid* objects, so
none of them can exercise a rejection path. Testing that BR-03 actually rejects
an over-specified facility needs a generator that deliberately violates it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from hypothesis import strategies as st

from shared_kernel import (
    Assignment,
    AssignmentProblem,
    AvailabilityDeclaration,
    Coordinates,
    CostBand,
    CostModel,
    CostRule,
    Department,
    DepartmentId,
    Event,
    EventId,
    EventStatus,
    EventType,
    Facility,
    FacilityId,
    JobType,
    ObjectiveWeights,
    OptimizationParameters,
    Position,
    Qualification,
    QualificationRequirement,
    ReasonCategory,
    SchoolDistrict,
    SchoolDistrictId,
    Staff,
    StaffId,
    TravelMetrics,
    TravelParameters,
)

# --- identifiers ------------------------------------------------------------

_ID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _id_text() -> st.SearchStrategy[str]:
    return st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=8)


gen_staff_id = _id_text().map(StaffId)
gen_facility_id = _id_text().map(FacilityId)
gen_school_district_id = _id_text().map(SchoolDistrictId)
gen_department_id = _id_text().map(DepartmentId)
gen_event_id = _id_text().map(EventId)


# --- value objects ----------------------------------------------------------


@st.composite
def gen_coordinates(draw: st.DrawFn) -> Coordinates:
    """Valid coordinates, with the poles, the antimeridian and the origin included."""
    latitude = draw(
        st.one_of(
            st.sampled_from([-90.0, 0.0, 90.0]),
            st.floats(min_value=-90.0, max_value=90.0, allow_nan=False, allow_infinity=False),
        )
    )
    longitude = draw(
        st.one_of(
            st.sampled_from([-180.0, 0.0, 180.0]),
            st.floats(min_value=-180.0, max_value=180.0, allow_nan=False, allow_infinity=False),
        )
    )
    return Coordinates(latitude=latitude, longitude=longitude)


@st.composite
def gen_travel_metrics(draw: st.DrawFn) -> TravelMetrics:
    return TravelMetrics(
        distance_km=draw(st.floats(min_value=0.0, max_value=500.0, allow_nan=False)),
        time_seconds=draw(st.integers(min_value=0, max_value=86_400)),
        cost_yen=draw(st.floats(min_value=0.0, max_value=200_000.0, allow_nan=False)),
    )


@st.composite
def gen_objective_weights(draw: st.DrawFn) -> ObjectiveWeights:
    """BR-02: all non-negative, at least one positive."""
    weights = draw(
        st.lists(
            st.floats(min_value=0.0, max_value=10.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=3,
        ).filter(lambda ws: any(w > 0.0 for w in ws))
    )
    return ObjectiveWeights(travel_time=weights[0], travel_cost=weights[1], inequity=weights[2])


@st.composite
def gen_cost_model(draw: st.DrawFn) -> CostModel:
    """A valid, monotone-non-decreasing distance-band cost model (BR-D02, BR-D04).

    Built so it cannot violate monotonicity: bounds strictly increase, each band
    charges at least as much as the one below can reach at their shared boundary.
    """
    n_bounded = draw(st.integers(min_value=0, max_value=3))

    # Strictly increasing boundaries.
    boundaries = sorted(
        draw(
            st.lists(
                st.floats(min_value=0.5, max_value=50.0, allow_nan=False),
                min_size=n_bounded,
                max_size=n_bounded,
                unique=True,
            )
        )
    )

    bands: list[CostBand] = []
    running_cost = 0.0  # the cost the previous band reaches at the boundary
    for boundary in boundaries:
        # A FLAT band that does not undercut the running cost.
        amount = draw(st.floats(min_value=running_cost, max_value=running_cost + 500.0,
                                allow_nan=False))
        bands.append(CostBand(upper_bound_km=boundary, rule=CostRule.FLAT, amount_yen=amount))
        running_cost = amount

    # Final unbounded band: FLAT (>= running_cost) or PER_KM whose value at the
    # last boundary is >= running_cost. A small margin above the exact minimum
    # keeps slope*boundary safely above running_cost despite float rounding, so
    # the generated model never lands on the validator's tolerance boundary.
    if boundaries:
        last_boundary = boundaries[-1]
        min_slope = (running_cost / last_boundary) * 1.001 + 0.001 if last_boundary > 0 else 0.0
    else:
        min_slope = 0.0
    if draw(st.booleans()):
        amount = draw(st.floats(min_value=running_cost, max_value=running_cost + 1000.0,
                                allow_nan=False))
        bands.append(CostBand(upper_bound_km=None, rule=CostRule.FLAT, amount_yen=amount))
    else:
        slope = draw(st.floats(min_value=min_slope, max_value=min_slope + 500.0, allow_nan=False))
        bands.append(CostBand(upper_bound_km=None, rule=CostRule.PER_KM, amount_yen=slope))

    return CostModel(bands=tuple(bands))


@st.composite
def gen_non_monotonic_cost_model_kwargs(draw: st.DrawFn) -> dict[str, object]:
    """Constructor arguments for a cost model that VIOLATES BR-D04.

    Returned as kwargs, not a CostModel: the point is that CostModel(**kwargs)
    raises. A flat band followed by a PER_KM band whose value at the boundary is
    strictly lower - "300 yen flat, then cheaper per-km beyond" - makes the
    further trip cost less, which the optimizer would exploit.

    gen_cost_model never produces this, so the rejection path needs its own
    generator (the same pattern as gen_invalid_facility for U-01).
    """
    boundary = draw(st.floats(min_value=5.0, max_value=20.0, allow_nan=False))
    flat_amount = draw(st.floats(min_value=200.0, max_value=1000.0, allow_nan=False))
    # slope small enough that slope * boundary < flat_amount
    max_slope = (flat_amount - 1.0) / boundary
    slope = draw(st.floats(min_value=0.0, max_value=max_slope, allow_nan=False))
    return {
        "bands": (
            CostBand(upper_bound_km=boundary, rule=CostRule.FLAT, amount_yen=flat_amount),
            CostBand(upper_bound_km=None, rule=CostRule.PER_KM, amount_yen=slope),
        ),
    }


@st.composite
def gen_travel_parameters(draw: st.DrawFn) -> TravelParameters:
    """BR-D03: detour_factor >= 1.0, average_speed_kmh > 0. Carries a cost model."""
    return TravelParameters(
        detour_factor=draw(st.floats(min_value=1.0, max_value=3.0, allow_nan=False)),
        average_speed_kmh=draw(
            st.floats(min_value=1.0, max_value=120.0, allow_nan=False, allow_infinity=False)
        ),
        same_district_fixed_seconds=draw(st.integers(min_value=0, max_value=7200)),
        cost_model=draw(gen_cost_model()),
    )


@st.composite
def gen_optimization_parameters(draw: st.DrawFn) -> OptimizationParameters:
    return OptimizationParameters(
        weights=draw(gen_objective_weights()),
        time_limit_seconds=draw(st.integers(min_value=1, max_value=600)),
        department_cap_limit=draw(st.integers(min_value=1, max_value=50)),
        allow_c3_demotion=draw(st.booleans()),
        random_seed=draw(st.integers(min_value=0, max_value=2**31 - 1)),
    )


# --- entities ---------------------------------------------------------------


@st.composite
def gen_department(draw: st.DrawFn) -> Department:
    return Department(
        id=draw(gen_department_id),
        name=draw(st.text(min_size=1, max_size=20)),
        concurrent_assignment_cap=draw(st.none() | st.integers(min_value=1, max_value=20)),
    )


@st.composite
def gen_school_district(draw: st.DrawFn) -> SchoolDistrict:
    return SchoolDistrict(
        id=draw(gen_school_district_id),
        name=draw(st.text(min_size=1, max_size=20)),
        representative_point=draw(gen_coordinates()),
    )


@st.composite
def gen_staff(
    draw: st.DrawFn,
    department_ids: list[DepartmentId] | None = None,
    district_ids: list[SchoolDistrictId] | None = None,
) -> Staff:
    """One job type, one position, zero or more qualifications (Q8=A).

    ``name`` is never empty (BR-06).
    """
    return Staff(
        id=draw(gen_staff_id),
        name=draw(st.text(min_size=1, max_size=20)),
        department_id=(
            draw(st.sampled_from(department_ids)) if department_ids else draw(gen_department_id)
        ),
        job_type=draw(st.sampled_from(list(JobType))),
        position=draw(st.sampled_from(list(Position))),
        residence_district_id=(
            draw(st.sampled_from(district_ids)) if district_ids else draw(gen_school_district_id)
        ),
        qualifications=frozenset(draw(st.sets(st.sampled_from(list(Qualification)), max_size=2))),
    )


@st.composite
def gen_facility(
    draw: st.DrawFn, district_ids: list[SchoolDistrictId] | None = None
) -> Facility:
    """BR-03: distinct requirements whose counts sum to at most required_headcount."""
    required_headcount = draw(st.integers(min_value=1, max_value=20))

    requirement_pool: list[Qualification | Position | JobType] = [
        *list(Qualification),
        *list(Position),
    ]
    chosen = draw(
        st.lists(st.sampled_from(requirement_pool), max_size=3, unique=True)
    )

    requirements: list[QualificationRequirement] = []
    remaining = required_headcount
    for requirement in chosen:
        if remaining <= 0:
            break
        count = draw(st.integers(min_value=1, max_value=remaining))
        requirements.append(QualificationRequirement(requirement=requirement, required_count=count))
        remaining -= count

    return Facility(
        id=draw(gen_facility_id),
        name=draw(st.text(min_size=1, max_size=20)),
        district_id=(
            draw(st.sampled_from(district_ids)) if district_ids else draw(gen_school_district_id)
        ),
        required_headcount=required_headcount,
        qualification_requirements=tuple(requirements),
    )


@st.composite
def gen_invalid_facility(draw: st.DrawFn) -> dict[str, object]:
    """Constructor arguments that BR-03 must reject.

    Returned as kwargs, not as a ``Facility``: the whole point is that
    ``Facility(**kwargs)`` raises. The qualification counts sum to strictly more
    than ``required_headcount`` -- a facility needing 5 people but 6 managers.
    """
    required_headcount = draw(st.integers(min_value=1, max_value=10))
    overflow = draw(st.integers(min_value=1, max_value=5))
    return {
        "id": draw(gen_facility_id),
        "name": draw(st.text(min_size=1, max_size=20)),
        "district_id": draw(gen_school_district_id),
        "required_headcount": required_headcount,
        "qualification_requirements": (
            QualificationRequirement(
                requirement=Position.MANAGER,
                required_count=required_headcount + overflow,
            ),
        ),
    }


@st.composite
def gen_event(draw: st.DrawFn, status: EventStatus | None = None) -> Event:
    return Event(
        id=draw(gen_event_id),
        type=draw(st.sampled_from(list(EventType))),
        name=draw(st.text(min_size=1, max_size=20)),
        scheduled_date=draw(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))),
        status=status if status is not None else draw(st.sampled_from(list(EventStatus))),
    )


@st.composite
def gen_availability_declaration(
    draw: st.DrawFn,
    staff_id: StaffId | None = None,
    event_id: EventId | None = None,
) -> AvailabilityDeclaration:
    """BR-05: reason_category present iff unavailable; note present iff OTHER."""
    is_available = draw(st.booleans())
    reason: ReasonCategory | None = None
    note: str | None = None
    if not is_available:
        reason = draw(st.sampled_from(list(ReasonCategory)))
        if reason is ReasonCategory.OTHER:
            note = draw(st.text(min_size=1, max_size=30))

    return AvailabilityDeclaration(
        staff_id=staff_id if staff_id is not None else draw(gen_staff_id),
        event_id=event_id if event_id is not None else draw(gen_event_id),
        is_available=is_available,
        declared_at=draw(
            st.datetimes(
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2030, 12, 31),
            ).map(lambda d: d.replace(tzinfo=UTC))
        ),
        reason_category=reason,
        other_reason_note=note,
    )


@st.composite
def gen_assignment_problem(draw: st.DrawFn) -> AssignmentProblem:
    """A structurally valid problem: every staff/facility pair has travel metrics."""
    districts = draw(st.lists(gen_school_district(), min_size=1, max_size=4, unique_by=lambda d: d.id))
    district_ids = [d.id for d in districts]

    staff = draw(
        st.lists(gen_staff(district_ids=district_ids), min_size=1, max_size=6, unique_by=lambda s: s.id)
    )
    facilities = draw(
        st.lists(
            gen_facility(district_ids=district_ids), min_size=1, max_size=3, unique_by=lambda f: f.id
        )
    )

    travel_matrix = {
        (s.id, f.id): draw(gen_travel_metrics()) for s in staff for f in facilities
    }

    return AssignmentProblem(
        event=draw(gen_event(status=EventStatus.COLLECTING_DECLARATIONS)),
        facilities=tuple(facilities),
        available_staff=tuple(staff),
        travel_matrix=travel_matrix,
        parameters=draw(gen_optimization_parameters()),
    )


@st.composite
def gen_assignment(
    draw: st.DrawFn, event_id: EventId | None = None, staff_id: StaffId | None = None
) -> Assignment:
    return Assignment(
        event_id=event_id if event_id is not None else draw(gen_event_id),
        staff_id=staff_id if staff_id is not None else draw(gen_staff_id),
        facility_id=draw(gen_facility_id),
        is_pinned=draw(st.booleans()),
    )


__all__ = [
    "gen_assignment",
    "gen_assignment_problem",
    "gen_availability_declaration",
    "gen_coordinates",
    "gen_cost_model",
    "gen_department",
    "gen_department_id",
    "gen_event",
    "gen_event_id",
    "gen_facility",
    "gen_facility_id",
    "gen_invalid_facility",
    "gen_non_monotonic_cost_model_kwargs",
    "gen_objective_weights",
    "gen_optimization_parameters",
    "gen_school_district",
    "gen_school_district_id",
    "gen_staff",
    "gen_staff_id",
    "gen_travel_metrics",
    "gen_travel_parameters",
]
