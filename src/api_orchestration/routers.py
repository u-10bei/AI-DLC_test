"""LC-02 routers.

Authentication is NOT written here — the middleware does it for every route that
is not in PUBLIC_ROUTES (DP-01). Authorization IS explicit per route, because only
the route knows which action is being attempted.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from optimization_engine import validate_assignments
from security import Principal
from security.authorization import (
    EXPORT_DATA,
    IMPORT_MASTER,
    MANAGE_DECLARATIONS,
    MANAGE_EVENT,
    RUN_OPTIMIZATION,
    VIEW_ASSIGNMENT,
    VIEW_REPORT,
)
from security.identifiers import SessionId, UserId
from shared_kernel import EventId, StaffId

from . import converters, dto, job_queue
from .identifiers import JobId
from .jobs import JobState, OptimizationJob
from .middleware import SESSION_COOKIE
from .problem_builder import build_problem
from .services import Services


def _principal(request: Request) -> Principal:
    """The middleware put this here. Reaching a non-public route without it is a bug."""
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, Principal):  # pragma: no cover - middleware guarantees it
        from security import AuthenticationFailedError

        raise AuthenticationFailedError()
    return principal


def build_router(services: Services) -> APIRouter:
    router = APIRouter()
    now = services.clock

    # --- health / sessions (the only PUBLIC routes) --------------------------

    @router.get("/health", response_model=dto.HealthResponse)
    def health() -> dto.HealthResponse:
        return dto.HealthResponse(status="ok", checked_at=now())

    # response_model=None: a `-> None` annotation would otherwise be read as
    # NoneType and FastAPI forbids a response body on 204.
    @router.post(
        "/sessions",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        response_model=None,
    )
    def login(body: dto.LoginRequest, response: Response) -> None:
        session = services.authenticator.login(UserId(body.user_id), body.password, now())
        # HttpOnly: JavaScript cannot read it, so XSS cannot steal the session (BR-API21).
        response.set_cookie(
            SESSION_COOKIE,
            str(session.id),
            httponly=True,
            secure=True,
            samesite="strict",
        )

    @router.delete(
        "/sessions",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        response_model=None,
    )
    def logout(request: Request, response: Response) -> None:
        session_id = request.cookies.get(SESSION_COOKIE)
        if session_id is not None:
            services.authenticator.logout(SessionId(session_id), now())
        response.delete_cookie(SESSION_COOKIE)

    # --- events -------------------------------------------------------------

    @router.post("/events", response_model=dto.EventResponse, status_code=201)
    def create_event(request: Request, body: dto.EventRequest) -> dto.EventResponse:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, MANAGE_EVENT, now())
        event = converters.to_domain_event(body)
        services.events.create_event(event)
        return converters.from_domain_event(event)

    @router.get("/events/{event_id}", response_model=dto.EventResponse)
    def get_event(request: Request, event_id: str) -> dto.EventResponse:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, MANAGE_EVENT, now(), event_id)
        event = services.events.get_event(EventId(event_id))
        if event is None:
            raise _not_found("event")
        return converters.from_domain_event(event)

    # --- master data --------------------------------------------------------

    @router.post("/masters/staff/import", response_model=dto.ImportResultResponse)
    async def import_staff(request: Request) -> dto.ImportResultResponse:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, IMPORT_MASTER, now())
        raw = await request.body()
        summary = services.master.import_staff(raw)
        return dto.ImportResultResponse(success_count=summary.success_count)

    @router.get("/masters/staff/export")
    def export_staff(request: Request) -> Response:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, EXPORT_DATA, now())
        # The sanitiser is injected at the composition root (U06-H3, MU-02).
        csv_bytes = services.export_staff_csv()
        return Response(content=csv_bytes, media_type="text/csv")

    # Facilities and school districts are symmetric with staff (U08-H1): the frontend
    # needs them to seed the masters that optimization requires. U-03 already owns the
    # import/export logic; these routes only wire it to the HTTP boundary.

    @router.post("/masters/facilities/import", response_model=dto.ImportResultResponse)
    async def import_facilities(request: Request) -> dto.ImportResultResponse:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, IMPORT_MASTER, now())
        raw = await request.body()
        summary = services.master.import_facilities(raw)
        return dto.ImportResultResponse(success_count=summary.success_count)

    @router.get("/masters/facilities/export")
    def export_facilities(request: Request) -> Response:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, EXPORT_DATA, now())
        return Response(content=services.export_facilities_csv(), media_type="text/csv")

    @router.post("/masters/districts/import", response_model=dto.ImportResultResponse)
    async def import_districts(request: Request) -> dto.ImportResultResponse:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, IMPORT_MASTER, now())
        raw = await request.body()
        summary = services.master.import_school_districts(raw)
        return dto.ImportResultResponse(success_count=summary.success_count)

    @router.get("/masters/districts/export")
    def export_districts(request: Request) -> Response:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, EXPORT_DATA, now())
        return Response(content=services.export_districts_csv(), media_type="text/csv")

    # --- declarations / sufficiency -----------------------------------------

    @router.post("/events/{event_id}/declarations/import", response_model=dto.ImportResultResponse)
    async def import_declarations(request: Request, event_id: str) -> dto.ImportResultResponse:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, MANAGE_DECLARATIONS, now(), event_id)
        raw = await request.body()
        summary = services.availability.import_declarations(EventId(event_id), raw)
        return dto.ImportResultResponse(success_count=summary.success_count)

    @router.get("/events/{event_id}/sufficiency", response_model=dto.SufficiencyResponse)
    def sufficiency(request: Request, event_id: str) -> dto.SufficiencyResponse:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, VIEW_REPORT, now(), event_id)
        return converters.from_domain_sufficiency(
            services.availability.sufficiency_status(EventId(event_id))
        )

    # --- optimization jobs --------------------------------------------------

    @router.post("/optimizations", response_model=dto.JobAcceptedResponse, status_code=202)
    def enqueue_optimization(request: Request, body: dto.OptimizationRequest) -> dto.JobAcceptedResponse:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, RUN_OPTIMIZATION, now(), body.event_id)
        moment = now()
        job = OptimizationJob(
            id=JobId(f"J-{body.event_id}-{int(moment.timestamp())}"),
            event_id=EventId(body.event_id),
            mode=converters.to_domain_mode(body),
            state=JobState.QUEUED,
            created_at=moment,
            parameters=converters.to_domain_parameters(body),
        )
        job_queue.enqueue(services.engine, job)  # returns immediately; the worker solves
        return converters.from_domain_job_accepted(job)

    @router.get("/optimizations/{job_id}", response_model=dto.JobStatusResponse)
    def job_status(request: Request, job_id: str) -> dto.JobStatusResponse:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, RUN_OPTIMIZATION, now())
        job = job_queue.get_job(services.engine, JobId(job_id))
        if job is None:
            raise _not_found("job")
        result = services.load_result(job) if job.state is JobState.SUCCEEDED else None
        return converters.from_domain_job_status(job, result)

    # --- assignments --------------------------------------------------------

    @router.get("/events/{event_id}/assignments", response_model=list[dto.AssignmentResponse])
    def list_assignments(request: Request, event_id: str) -> list[dto.AssignmentResponse]:
        principal = _principal(request)
        services.authorizer.require_authorization(principal, VIEW_ASSIGNMENT, now(), event_id)
        return [
            converters.from_domain_assignment(a)
            for a in services.load_assignments(EventId(event_id))
        ]

    @router.patch("/events/{event_id}/assignments", response_model=list[dto.AssignmentResponse])
    def patch_assignment(
        request: Request, event_id: str, body: dto.AssignmentPatchRequest
    ) -> list[dto.AssignmentResponse]:
        """Manual edit with immediate hard-constraint validation (FR-06.3, US-22)."""
        principal = _principal(request)
        services.authorizer.require_authorization(principal, VIEW_ASSIGNMENT, now(), event_id)

        current = services.load_assignments(EventId(event_id))
        edited = (
            *(a for a in current if a.staff_id != StaffId(body.staff_id)),
            converters.to_domain_assignment(body, EventId(event_id)),
        )

        problem = build_problem(
            services.engine, EventId(event_id), services.config.optimization, services.config.travel
        )
        # U-04 owns the constraints, so U-04 answers (U07-H1). No second interpretation.
        violations = validate_assignments(problem, edited)
        if violations:
            raise _violations_error(violations)

        services.save_assignments(EventId(event_id), edited)
        services.audit_assignment_change(principal, EventId(event_id), body, current)
        return [converters.from_domain_assignment(a) for a in edited]

    # --- comparison ---------------------------------------------------------
    # NOT exposed yet. U-05's ComparisonService is complete and tested, but calling
    # it needs a HistoricalRecord, and persisting a past event's full actuals needs
    # the historical_assignments / historical_declarations tables that U-05 already
    # deferred (U05-H6). Wiring this endpoint is blocked on that, not on U-07.

    return router


def _not_found(what: str) -> Exception:
    from fastapi import HTTPException

    return HTTPException(status_code=404, detail=f"{what} not found")


def _violations_error(violations: tuple[object, ...]) -> Exception:
    from fastapi import HTTPException

    from shared_kernel import ConstraintViolation

    typed = [v for v in violations if isinstance(v, ConstraintViolation)]
    body = dto.ErrorResponse(
        message="assignment violates hard constraints",
        violations=[converters.from_domain_violation(v) for v in typed],
    )
    return HTTPException(status_code=400, detail=body.model_dump(exclude_none=True))


__all__ = ["build_router"]
