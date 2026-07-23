"""Property-based tests for U-07 (P-API01..07)."""

from __future__ import annotations

from datetime import date

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from api_orchestration import converters, dto
from shared_kernel import EventType, to_japanese

from .support import USER, build_harness

_SETTINGS = settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

_safe_text = st.text(
    alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x9FFF, exclude_categories=("Cs", "Cc")),
    min_size=1,
    max_size=20,
)
_ids = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=1, max_size=8)


# --- P-API01: DTO <-> domain round-trip --------------------------------------


@given(
    _ids,
    st.sampled_from(list(EventType)),
    _safe_text,
    st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
)
def test_event_dto_round_trip(
    event_id: str, event_type: EventType, name: str, scheduled: date
) -> None:
    """P-API01: the wire format loses nothing the domain needs, and vice versa."""
    request = dto.EventRequest(
        id=event_id, type=to_japanese(event_type), name=name, scheduled_date=scheduled
    )
    event = converters.to_domain_event(request)
    response = converters.from_domain_event(event)
    assert response.id == request.id
    assert response.type == request.type
    assert response.name == request.name
    assert response.scheduled_date == request.scheduled_date


@given(
    st.floats(min_value=0.0, max_value=5.0, allow_nan=False),
    st.floats(min_value=0.0, max_value=5.0, allow_nan=False),
    st.floats(min_value=0.0, max_value=5.0, allow_nan=False),
    st.integers(min_value=1, max_value=600),
    st.integers(min_value=1, max_value=50),
)
def test_optimization_parameters_round_trip(
    time_w: float, cost_w: float, inequity_w: float, limit: int, cap: int
) -> None:
    """The coordinator's weights survive the DTO boundary unchanged (US-17)."""
    if time_w == cost_w == inequity_w == 0.0:
        return  # ObjectiveWeights requires one positive weight (BR-02)
    request = dto.OptimizationRequest(
        event_id="E1",
        travel_time_weight=time_w,
        travel_cost_weight=cost_w,
        inequity_weight=inequity_w,
        time_limit_seconds=limit,
        department_cap_limit=cap,
    )
    params = converters.to_domain_parameters(request)
    assert params.weights.travel_time == time_w
    assert params.weights.travel_cost == cost_w
    assert params.weights.inequity == inequity_w
    assert params.time_limit_seconds == limit
    assert params.department_cap_limit == cap


# --- P-API02 / P-API03: deny by default --------------------------------------

_PROTECTED = [
    ("GET", "/events/E1"),
    ("GET", "/events/E1/assignments"),
    ("GET", "/events/E1/sufficiency"),
    ("GET", "/masters/staff/export"),
    ("GET", "/optimizations/J1"),
]


@_SETTINGS
@given(st.sampled_from(_PROTECTED))
def test_every_protected_route_is_401_without_a_session(route: tuple[str, str]) -> None:
    """P-API02: DP-01 means this holds for routes nobody remembered to decorate."""
    method, path = route
    harness = build_harness()
    assert harness.client.request(method, path).status_code == 401


@_SETTINGS
@given(st.sampled_from([*_PROTECTED, ("GET", "/health"), ("POST", "/sessions")]))
def test_disallowed_ip_is_403_on_every_route(route: tuple[str, str]) -> None:
    """P-API03: the IP gate runs before everything, including the public routes."""
    method, path = route
    harness = build_harness()
    assert harness.denied_client.request(method, path).status_code == 403


# --- P-API04 / P-API06 -------------------------------------------------------


@_SETTINGS
@given(st.sampled_from(_PROTECTED))
def test_error_responses_never_leak_internals(route: tuple[str, str]) -> None:
    """P-API04 (SECURITY-09)."""
    method, path = route
    harness = build_harness()
    body = harness.client.request(method, path).text
    for leak in ("Traceback", "site-packages", "/home/", "sqlalchemy", "pydantic"):
        assert leak not in body


@_SETTINGS
@given(st.sampled_from([*_PROTECTED, ("GET", "/health")]))
def test_security_headers_are_on_every_response(route: tuple[str, str]) -> None:
    """P-API06: including error responses, which is where they are easiest to forget."""
    method, path = route
    harness = build_harness()
    headers = {k.lower() for k in harness.client.request(method, path).headers}
    assert "content-security-policy" in headers
    assert "x-frame-options" in headers


@_SETTINGS
@given(st.text(min_size=1, max_size=20))
def test_login_never_reveals_whether_an_account_exists(password: str) -> None:
    """The same generic body whether the user exists or not (BR-SEC04)."""
    harness = build_harness()
    unknown = harness.client.post("/sessions", json={"user_id": "NOBODY", "password": password})
    wrong = harness.client.post("/sessions", json={"user_id": USER, "password": password})
    if wrong.status_code == 204:
        return  # the generated password happened to be the real one
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
