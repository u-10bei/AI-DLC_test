"""LC-06 AuditService and the audit event type (FR-07, SECURITY-13/14).

AuditEvent has no field capable of holding PII (DP-07). That is the point: the
rule "never write a name or a residence district to the audit log" (SECURITY-03)
is not a habit here, it is a property of the type. In particular there is no
place to put ``reason_category`` -- leave, caregiving or a health accommodation
is close to sensitive personal information and must never be logged (U01-H22).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from shared_kernel import EventId, FacilityId, StaffId

from .identifiers import UserId


class AuditAction(Enum):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    AUTH_FAILURE = "AUTH_FAILURE"
    LOGOUT = "LOGOUT"
    AUTHZ_DENIED = "AUTHZ_DENIED"
    PRIVILEGE_ESCALATION_ATTEMPT = "PRIVILEGE_ESCALATION_ATTEMPT"
    IP_REJECTED = "IP_REJECTED"
    RATE_LIMITED = "RATE_LIMITED"
    ASSIGNMENT_CREATED = "ASSIGNMENT_CREATED"
    ASSIGNMENT_CHANGED = "ASSIGNMENT_CHANGED"
    MASTER_CHANGED = "MASTER_CHANGED"
    MASTER_DELETED = "MASTER_DELETED"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One audit record. IDs and enums only -- no field can carry PII (DP-07)."""

    timestamp: datetime  # UTC (BR-SEC19)
    action: AuditAction
    actor: UserId | None = None  # None when unauthenticated
    event_id: EventId | None = None
    staff_id: StaffId | None = None
    facility_id: FacilityId | None = None
    before: dict[str, str] | None = None  # IDs only (FR-07.1)
    after: dict[str, str] | None = None  # IDs only
    source_ip: str | None = None
    detail: str | None = None  # short, PII-free

    def to_json_line(self) -> str:
        record: dict[str, object] = {
            "ts": self.timestamp.isoformat(),
            "action": self.action.value,
        }
        for key, value in (
            ("actor", self.actor),
            ("event_id", self.event_id),
            ("staff_id", self.staff_id),
            ("facility_id", self.facility_id),
            ("source_ip", self.source_ip),
            ("detail", self.detail),
        ):
            if value is not None:
                record[key] = value
        if self.before is not None:
            record["before"] = self.before
        if self.after is not None:
            record["after"] = self.after
        return json.dumps(record, ensure_ascii=False, sort_keys=True)


class AuditLogPort(Protocol):
    """P-04. Append one event. Implemented by A-05 (append-only file)."""

    def append(self, event: AuditEvent) -> None: ...


class AuditService:
    """S-08. Records audit events outside the business transaction (BR-SEC18).

    A rolled-back business transaction must not erase the fact that someone tried
    something -- which is precisely what MU-04 would like to happen.
    """

    def __init__(self, log: AuditLogPort) -> None:
        self._log = log

    def record(self, event: AuditEvent) -> None:
        self._log.append(event)


__all__ = ["AuditAction", "AuditEvent", "AuditLogPort", "AuditService"]
