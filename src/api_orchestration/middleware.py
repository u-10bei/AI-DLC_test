"""LC-01 middleware: the security chain (DP-01/02, U06-H4).

Order (Application Design): headers -> SEC-03 IP -> SEC-04 rate -> SEC-01 authn.
Cheap, broad rejections first; the expensive checks only for requests that got past
them. Authorization (SEC-02) is called per-route, because only the route knows what
action is being attempted.

**Why authentication is middleware and not Depends()** (DP-01, Q1=A): FastAPI's
idiom is a per-route dependency, and its failure mode is that a route someone
forgot to decorate is PUBLIC. Here every request is authenticated unless its path
is in PUBLIC_ROUTES, so the failure mode of forgetting is a 401. Publishing an
endpoint requires editing an allowlist that a reviewer will see.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from fastapi import FastAPI, Request, Response

from security import (
    AuthenticationFailedError,
    Authenticator,
    IpAllowlist,
    IpNotAllowedError,
    RateLimiter,
    RateLimitExceededError,
)
from security.identifiers import SessionId
from security.rate_limit import GENERAL, LOGIN

from .errors import error_response_for

SESSION_COOKIE = "session_id"

#: The ONLY routes reachable without a session (U07-H11). Adding to this list is a
#: security decision and should be reviewed as one.
PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/sessions"),  # login itself cannot require a session
        ("GET", "/health"),
    }
)

_SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}

_Handler = Callable[[Request], Awaitable[Response]]


def source_ip(request: Request, trusted_proxies: tuple[str, ...], header: str) -> str:
    """The address NFR-S10.2 should judge — not necessarily the socket's peer.

    Behind the existing exposure platform (TLS termination, WAF), the peer address
    is the proxy's, so allowlisting it would be meaningless. The municipal egress
    address is in the forwarded-for header.

    That header is trivially spoofable, so it is honoured ONLY when the peer is a
    proxy the operator listed in trusted_proxies. Otherwise the peer address is
    used, and an unparseable or absent value is denied downstream by IpAllowlist
    (SECURITY-15).
    """
    peer = request.client.host if request.client is not None else ""
    if peer not in trusted_proxies:
        return peer  # not a trusted hop: the header, if any, is not evidence
    forwarded = request.headers.get(header)
    if not forwarded:
        return ""  # trusted proxy that did not forward one -> deny, do not guess
    return forwarded.split(",")[0].strip()


def register_middleware(
    app: FastAPI,
    *,
    ip_allowlist: IpAllowlist,
    rate_limiter: RateLimiter,
    authenticator: Authenticator,
    trusted_proxies: tuple[str, ...] = (),
    client_ip_header: str = "x-forwarded-for",
    clock: Callable[[], datetime] | None = None,
) -> None:
    """Register the chain. Starlette runs middleware in reverse-registration order,
    so these are added last-first to execute as: headers -> ip -> rate -> authn.

    Each gate converts its own denial with error_response_for: exceptions raised in
    middleware never reach @app.exception_handler (see errors.py).

    `clock` is the SAME injected clock the routes use. Session expiry (authenticate)
    and the rate-limit window must be judged on one clock; taking real time here while
    the routes stamp a frozen test clock makes every session look expired the moment
    wall-clock passes the frozen instant's TTL. Defaults to real time in production.
    """
    _now = clock if clock is not None else (lambda: datetime.now(UTC))

    @app.middleware("http")
    async def _authenticate(request: Request, call_next: _Handler) -> Response:
        route = (request.method, request.url.path)
        if route in PUBLIC_ROUTES:
            return await call_next(request)
        try:
            session_id = request.cookies.get(SESSION_COOKIE)
            if session_id is None:
                raise AuthenticationFailedError()
            principal = authenticator.authenticate(SessionId(session_id), _now())
        except AuthenticationFailedError as exc:
            return _denied(exc)
        request.state.principal = principal  # routes read this for authorization
        return await call_next(request)

    @app.middleware("http")
    async def _rate_limit(request: Request, call_next: _Handler) -> Response:
        kind = LOGIN if (request.method, request.url.path) == ("POST", "/sessions") else GENERAL
        try:
            rate_limiter.check(source_ip(request, trusted_proxies, client_ip_header), kind, _now())
        except RateLimitExceededError as exc:
            return _denied(exc)
        return await call_next(request)

    @app.middleware("http")
    async def _ip_check(request: Request, call_next: _Handler) -> Response:
        try:
            ip_allowlist.check(source_ip(request, trusted_proxies, client_ip_header))
        except IpNotAllowedError as exc:
            return _denied(exc)
        return await call_next(request)

    @app.middleware("http")
    async def _security_headers(request: Request, call_next: _Handler) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


def _denied(exc: Exception) -> Response:
    mapped = error_response_for(exc)
    if mapped is None:  # pragma: no cover - only known denials reach here
        raise exc
    return mapped


__all__ = ["PUBLIC_ROUTES", "SESSION_COOKIE", "register_middleware"]
