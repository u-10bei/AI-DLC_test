"""SEC-02 Authorizer (MU-01/IDOR, NFR-S04, DP-01).

Two checks, always in this order: may this role perform this action at all, and
may this principal touch this particular resource. In the PoC the second check is
trivially "yes" for a coordinator -- but the gate exists and every resource access
goes through it. That is the whole point: when staff self-service arrives (A-08)
the narrowing goes in one place, instead of being retrofitted across every call
site, which is how IDOR bugs are born.

``require_authorization`` is the normal entry point and it RAISES. ``authorize``
returns a decision because a denial needs a reason for the audit log -- but a
caller who only calls ``authorize`` and ignores the result is not a code path that
exists in the API's intent (DP-01).
"""

from __future__ import annotations

from datetime import datetime

from .audit import AuditAction, AuditEvent, AuditService
from .entities import AuthorizationDecision, Principal, Role
from .exceptions import AuthorizationDeniedError

# Actions a coordinator may perform. Unknown actions are denied (deny by default).
MANAGE_EVENT = "MANAGE_EVENT"
IMPORT_MASTER = "IMPORT_MASTER"
MANAGE_DECLARATIONS = "MANAGE_DECLARATIONS"
RUN_OPTIMIZATION = "RUN_OPTIMIZATION"
VIEW_ASSIGNMENT = "VIEW_ASSIGNMENT"
EDIT_ASSIGNMENT = "EDIT_ASSIGNMENT"
VIEW_REPORT = "VIEW_REPORT"
EXPORT_DATA = "EXPORT_DATA"

_ROLE_ACTIONS: dict[Role, frozenset[str]] = {
    Role.COORDINATOR: frozenset(
        {
            MANAGE_EVENT,
            IMPORT_MASTER,
            MANAGE_DECLARATIONS,
            RUN_OPTIMIZATION,
            VIEW_ASSIGNMENT,
            EDIT_ASSIGNMENT,
            VIEW_REPORT,
            EXPORT_DATA,
        }
    )
}

#: Roles allowed to reach any resource of the municipality. A coordinator
#: administers all of it; a future STAFF role (A-08) must NOT be added here but
#: narrowed in _authorize_resource. Membership is the explicit extension point.
_UNRESTRICTED_ROLES: frozenset[Role] = frozenset({Role.COORDINATOR})


class Authorizer:
    def __init__(self, audit: AuditService) -> None:
        self._audit = audit

    def authorize(
        self, principal: Principal, action: str, resource_id: str | None = None
    ) -> AuthorizationDecision:
        """Role check, then the object-level gate. Deny by default."""
        permitted = _ROLE_ACTIONS.get(principal.role)
        if permitted is None or action not in permitted:
            return AuthorizationDecision(allowed=False, reason="action not permitted for role")
        return self._authorize_resource(principal, resource_id)

    def require_authorization(
        self,
        principal: Principal,
        action: str,
        now: datetime,
        resource_id: str | None = None,
    ) -> None:
        """The normal entry point: raise on denial (DP-01), and audit it."""
        decision = self.authorize(principal, action, resource_id)
        if not decision.allowed:
            self._audit.record(
                AuditEvent(
                    timestamp=now,
                    action=AuditAction.AUTHZ_DENIED,
                    actor=principal.user_id,
                    detail=f"{action}: {decision.reason}",
                )
            )
            raise AuthorizationDeniedError(
                user_id=principal.user_id, action=action, resource_id=resource_id
            )

    def _authorize_resource(
        self, principal: Principal, resource_id: str | None
    ) -> AuthorizationDecision:
        """Object-level gate (MU-01). The extension point for A-08.

        A coordinator administers the whole municipality's assignments, so every
        resource is in scope. A future STAFF role must be narrowed HERE -- and until
        it is, any role not listed as unrestricted is denied rather than assumed
        harmless.
        """
        if principal.role in _UNRESTRICTED_ROLES:
            return AuthorizationDecision(allowed=True)
        return AuthorizationDecision(allowed=False, reason="object-level access denied")


__all__ = [
    "EDIT_ASSIGNMENT",
    "EXPORT_DATA",
    "IMPORT_MASTER",
    "MANAGE_DECLARATIONS",
    "MANAGE_EVENT",
    "RUN_OPTIMIZATION",
    "VIEW_ASSIGNMENT",
    "VIEW_REPORT",
    "Authorizer",
]
