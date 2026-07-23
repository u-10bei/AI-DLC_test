"""LC-06 job queue on U-03's optimization_jobs table (U07-H3, DP-03).

Claiming uses a CONDITIONAL update whose rowcount decides the winner:

    UPDATE optimization_jobs SET status='RUNNING' WHERE id=? AND status='QUEUED'

Today there is one worker (A-07), so a SELECT-then-UPDATE would also work. It
would also silently become a double-execution bug the day a second worker appears
-- and the thing being executed twice is a 300-second solve. The conditional
update costs nothing now and cannot break then.

Every function here is a SHORT transaction. The solve deliberately happens between
them, never inside one: SQLite is a single writer and a 300-second write
transaction would stall the API process (U07-H13, shared-infrastructure.md 5).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import Engine, insert, select, update

from data_management import schema
from shared_kernel import EventId, ObjectiveWeights, OptimizationParameters

from .identifiers import JobId
from .jobs import JobState, OptimizationJob, ReoptimizationMode


def _to_stored(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo is not None else value


def _from_stored(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("job timestamp is missing")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _params_to_json(params: OptimizationParameters | None) -> str | None:
    if params is None:
        return None
    return json.dumps(
        {
            "travel_time": params.weights.travel_time,
            "travel_cost": params.weights.travel_cost,
            "inequity": params.weights.inequity,
            "time_limit_seconds": params.time_limit_seconds,
            "department_cap_limit": params.department_cap_limit,
            "random_seed": params.random_seed,
        },
        sort_keys=True,
    )


def _params_from_json(raw: object) -> OptimizationParameters | None:
    if not isinstance(raw, str) or not raw:
        return None
    data = json.loads(raw)
    return OptimizationParameters(
        weights=ObjectiveWeights(
            travel_time=float(data["travel_time"]),
            travel_cost=float(data["travel_cost"]),
            inequity=float(data["inequity"]),
        ),
        time_limit_seconds=int(data["time_limit_seconds"]),
        department_cap_limit=int(data["department_cap_limit"]),
        random_seed=int(data["random_seed"]),
    )


def _row_to_job(mapping: dict[str, object]) -> OptimizationJob:
    return OptimizationJob(
        id=JobId(str(mapping["id"])),
        event_id=EventId(str(mapping["event_id"])),
        mode=ReoptimizationMode(str(mapping["mode"] or ReoptimizationMode.FULL.value)),
        state=JobState(str(mapping["status"])),
        created_at=_from_stored(mapping["created_at"]),
        parameters=_params_from_json(mapping.get("params_json")),
        result_id=None if mapping["result_id"] is None else str(mapping["result_id"]),
        detail=None if mapping["detail"] is None else str(mapping["detail"]),
    )


def enqueue(engine: Engine, job: OptimizationJob) -> None:
    """Add a QUEUED job. Short transaction."""
    with engine.begin() as conn:
        conn.execute(
            insert(schema.optimization_jobs),
            {
                "id": str(job.id),
                "event_id": str(job.event_id),
                "status": job.state.value,
                "created_at": _to_stored(job.created_at),
                "mode": job.mode.value,
                "params_json": _params_to_json(job.parameters),
                "result_id": None,
                "detail": None,
            },
        )


def claim_next(engine: Engine) -> OptimizationJob | None:
    """Claim the oldest QUEUED job by conditional UPDATE, or return None.

    The rowcount is the arbiter: 1 means we took it, 0 means somebody else did.
    """
    with engine.begin() as conn:
        candidate = conn.execute(
            select(schema.optimization_jobs)
            .where(schema.optimization_jobs.c.status == JobState.QUEUED.value)
            .order_by(schema.optimization_jobs.c.created_at)
            .limit(1)
        ).first()
        if candidate is None:
            return None
        job_id = str(candidate._mapping["id"])
        claimed = conn.execute(
            update(schema.optimization_jobs)
            .where(
                schema.optimization_jobs.c.id == job_id,
                schema.optimization_jobs.c.status == JobState.QUEUED.value,  # the guard
            )
            .values(status=JobState.RUNNING.value)
        )
        if claimed.rowcount != 1:
            return None  # someone else claimed it between the select and the update
        row = dict(candidate._mapping)
        row["status"] = JobState.RUNNING.value
        return _row_to_job(row)


def _finish(engine: Engine, job_id: JobId, state: JobState, **fields: object) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(schema.optimization_jobs)
            .where(schema.optimization_jobs.c.id == str(job_id))
            .values(status=state.value, **fields)
        )


def mark_succeeded(engine: Engine, job_id: JobId, result_id: str) -> None:
    _finish(engine, job_id, JobState.SUCCEEDED, result_id=result_id)


def mark_infeasible(engine: Engine, job_id: JobId, detail: str) -> None:
    """Not a failure: the coordinator has something to act on (BR-API15)."""
    _finish(engine, job_id, JobState.INFEASIBLE, detail=detail)


def mark_failed(engine: Engine, job_id: JobId, detail: str) -> None:
    _finish(engine, job_id, JobState.FAILED, detail=detail)


def get_job(engine: Engine, job_id: JobId) -> OptimizationJob | None:
    with engine.connect() as conn:
        row = conn.execute(
            select(schema.optimization_jobs).where(
                schema.optimization_jobs.c.id == str(job_id)
            )
        ).first()
    return None if row is None else _row_to_job(dict(row._mapping))


__all__ = [
    "claim_next",
    "enqueue",
    "get_job",
    "mark_failed",
    "mark_infeasible",
    "mark_succeeded",
]
