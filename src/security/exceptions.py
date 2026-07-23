"""U-06 exceptions. Every gate signals denial by RAISING (DP-01).

Returning a boolean would mean a caller who forgets to check it lets the request
through -- fail open. Raising makes the failure mode of a forgotten check a
denied request instead.

None of these carry PII (SECURITY-03): the context is an account ID, an action,
a resource ID or a source IP -- never a staff name or residence district.
"""

from __future__ import annotations

from shared_kernel import DomainError

from .identifiers import UserId


class SecurityError(DomainError):
    """Base for U-06's denials. Structured context, no PII."""

    def __init__(
        self,
        message: str,
        *,
        violated_rule: str,
        user_id: UserId | None = None,
        action: str | None = None,
        resource_id: str | None = None,
        source_ip: str | None = None,
    ) -> None:
        super().__init__(message, violated_rule=violated_rule)
        self.user_id = user_id
        self.action = action
        self.resource_id = resource_id
        self.source_ip = source_ip

    def context(self) -> dict[str, str]:
        ctx: dict[str, str] = {"violated_rule": self.violated_rule}
        if self.user_id is not None:
            ctx["user_id"] = self.user_id
        if self.action is not None:
            ctx["action"] = self.action
        if self.resource_id is not None:
            ctx["resource_id"] = self.resource_id
        if self.source_ip is not None:
            ctx["source_ip"] = self.source_ip
        return ctx


class AuthenticationFailedError(SecurityError):
    """Login or session validation failed.

    Deliberately does NOT distinguish "unknown user" from "wrong password" from
    "locked account" (BR-SEC04): the message is generic and the timing is
    equalised (DP-02), so neither reveals whether an account exists. The real
    reason goes to the audit log instead.
    """

    def __init__(self, message: str = "authentication failed", *, user_id: UserId | None = None) -> None:
        super().__init__(message, violated_rule="SECURITY-08", user_id=user_id)


class AuthorizationDeniedError(SecurityError):
    """The principal may not perform this action on this resource (MU-01)."""

    def __init__(
        self,
        message: str = "authorization denied",
        *,
        user_id: UserId | None = None,
        action: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        super().__init__(
            message,
            violated_rule="SECURITY-08",
            user_id=user_id,
            action=action,
            resource_id=resource_id,
        )


class IpNotAllowedError(SecurityError):
    """The source IP is not on the municipal egress allowlist (US-02, NFR-S10.2)."""

    def __init__(self, message: str = "source ip not allowed", *, source_ip: str | None = None) -> None:
        super().__init__(message, violated_rule="SECURITY-07", source_ip=source_ip)


class RateLimitExceededError(SecurityError):
    """Too many requests from this source (NFR-S09, MU-03)."""

    def __init__(self, message: str = "rate limit exceeded", *, source_ip: str | None = None) -> None:
        super().__init__(message, violated_rule="SECURITY-11", source_ip=source_ip)


__all__ = [
    "AuthenticationFailedError",
    "AuthorizationDeniedError",
    "IpNotAllowedError",
    "RateLimitExceededError",
    "SecurityError",
]
