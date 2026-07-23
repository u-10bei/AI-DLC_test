"""Optimization job types (U07-H7, FD Q4/Q5).

INFEASIBLE is a state of its own, not a flavour of FAILED. An infeasible problem
is something the coordinator acts on -- gather more declarations, revise the
requirements -- whereas FAILED means the system broke. Collapsing them would tell
a coordinator "the system is broken" when the honest answer is "you need twelve
more volunteers".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from shared_kernel import EventId, OptimizationParameters

from .identifiers import JobId


class JobState(Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    INFEASIBLE = "INFEASIBLE"  # a coordinator problem, not a system failure
    FAILED = "FAILED"


#: States a job can never leave.
TERMINAL_STATES: frozenset[JobState] = frozenset(
    {JobState.SUCCEEDED, JobState.INFEASIBLE, JobState.FAILED}
)


class ReoptimizationMode(Enum):
    """FR-06.6 / US-24.

    FULL discards the previous assignment: optimal, but staff who were already
    told where to go may be moved. INCREMENTAL pins the previous assignment and
    only places newly-available staff: nobody is moved, but the result is not
    globally optimal. The coordinator chooses; the trade-off is theirs.
    """

    FULL = "FULL"
    INCREMENTAL = "INCREMENTAL"


@dataclass(frozen=True, slots=True)
class OptimizationJob:
    id: JobId
    event_id: EventId
    mode: ReoptimizationMode
    state: JobState
    created_at: datetime  # UTC
    #: The coordinator's weights and limits, carried WITH the job.
    #:
    #: Not a nicety: the API accepts these per request (US-17), and the worker runs
    #: later in another process. If they were not persisted here the worker would
    #: quietly solve with the server defaults and the request's weights would be a
    #: lie -- worse than not offering them.
    parameters: OptimizationParameters | None = None
    result_id: str | None = None
    detail: str | None = None  # infeasibility/failure summary, no PII


__all__ = ["TERMINAL_STATES", "JobState", "OptimizationJob", "ReoptimizationMode"]
