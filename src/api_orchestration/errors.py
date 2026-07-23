"""LC-09 exception -> generic response (DP-02, U01-H14, SECURITY-09).

Every handler returns a generic body. No stack trace, no internal path, no
framework version, and no PII. The detail that a developer needs goes to the
structured log; the detail an attacker would like goes nowhere.

The catch-all matters most: an exception nobody anticipated becomes a generic 500,
never a leaked traceback and never an accidental success (SECURITY-15).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from data_management import CsvImportError
from security import (
    AuthenticationFailedError,
    AuthorizationDeniedError,
    IpNotAllowedError,
    RateLimitExceededError,
)
from shared_kernel import DomainError

from .dto import ErrorResponse, RowErrorResponse

_GENERIC_500 = "internal error"


def _json(status: int, body: ErrorResponse) -> JSONResponse:
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


def error_response_for(exc: BaseException) -> JSONResponse | None:
    """Map a known exception to its generic response, or None if unrecognised.

    Shared by the route exception handlers AND the security middleware. Starlette
    runs custom middleware OUTSIDE the exception-handler middleware, so an
    exception raised in the chain would never reach @app.exception_handler and
    would surface as a bare 500. The middleware therefore converts denials itself,
    using this same function — one mapping, two callers, no drift.
    """
    if isinstance(exc, IpNotAllowedError):
        return _json(403, ErrorResponse(message="forbidden"))
    if isinstance(exc, RateLimitExceededError):
        return _json(429, ErrorResponse(message="too many requests"))
    if isinstance(exc, AuthenticationFailedError):
        # Generic on purpose: never reveal whether the account exists (BR-SEC04).
        return _json(401, ErrorResponse(message="authentication failed"))
    if isinstance(exc, AuthorizationDeniedError):
        return _json(403, ErrorResponse(message="forbidden"))
    if isinstance(exc, CsvImportError):
        # All errors at once, with line numbers, and no PII (BR-DM02, BR-DM14).
        return _json(
            400,
            ErrorResponse(
                message="csv import failed",
                violated_rule=exc.violated_rule,
                errors=[RowErrorResponse(line=e.line, message=e.message) for e in exc.errors],
            ),
        )
    if isinstance(exc, DomainError):
        return _json(400, ErrorResponse(message=str(exc), violated_rule=exc.violated_rule))
    return None


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_request: Request, exc: DomainError) -> JSONResponse:
        mapped = error_response_for(exc)
        return mapped if mapped is not None else _json(400, ErrorResponse(message=str(exc)))

    @app.exception_handler(CsvImportError)
    async def _csv(_request: Request, exc: CsvImportError) -> JSONResponse:
        mapped = error_response_for(exc)
        return mapped if mapped is not None else _json(400, ErrorResponse(message="csv import failed"))

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, _exc: Exception) -> JSONResponse:
        # fail closed: an unanticipated error is a generic 500, never a traceback.
        return _json(500, ErrorResponse(message=_GENERIC_500))


__all__ = ["error_response_for", "register_exception_handlers"]
