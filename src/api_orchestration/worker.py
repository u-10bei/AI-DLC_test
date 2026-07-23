"""LC-08 the job worker (DP-04, U07-H13).

Split into step() and run_forever() so tests drive one job synchronously without
spawning anything (NFR Req Q5=A), and the CLI just loops step().

**The constraint that shapes this file** (shared-infrastructure.md 5, U07-H13):
the solve must run OUTSIDE a write transaction. SQLite is a single writer, so a
300-second write transaction would stall the API process — the exact problem the
worker exists to avoid. Hence the deliberate three-phase shape:

    claim   -> short transaction   (job_queue.claim_next)
    solve   -> NO transaction      (up to 300s)
    record  -> short transaction   (job_queue.mark_*)

Wrapping this in `with engine.begin()` for convenience would silently reintroduce
the stall. It is not done here, and must not be.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import Engine

from optimization_engine import InfeasibilityDiagnosis, OptimizationService, save_assignment_result
from shared_kernel import AssignmentResult

from . import job_queue
from .config import AppConfig
from .jobs import OptimizationJob
from .problem_builder import ProblemBuildError, build_problem


def _result_id(job: OptimizationJob) -> str:
    return f"R-{job.id}"


def step(engine: Engine, config: AppConfig, *, now: datetime | None = None) -> bool:
    """Process at most one job. Returns True if one was processed.

    Phases are deliberately separate transactions with the solve between them
    (U07-H13).
    """
    moment = now if now is not None else datetime.now(UTC)

    job = job_queue.claim_next(engine)  # short transaction
    if job is None:
        return False

    try:
        problem = build_problem(  # reads only
            engine,
            job.event_id,
            # The coordinator's parameters travel with the job; the server defaults
            # are only a fallback for a job that never carried any.
            job.parameters if job.parameters is not None else config.optimization,
            config.travel,
            mode=job.mode,
        )
    except ProblemBuildError as exc:
        job_queue.mark_failed(engine, job.id, str(exc))
        return True

    try:
        # --- NO transaction is open here. This may take 300 seconds. ---
        outcome = OptimizationService().optimize(problem, now=moment)
    except Exception as exc:
        job_queue.mark_failed(engine, job.id, type(exc).__name__)  # no PII, no trace
        return True

    if isinstance(outcome, InfeasibilityDiagnosis):
        # Not a failure: the coordinator has something to act on (BR-API15).
        job_queue.mark_infeasible(engine, job.id, outcome.cause.value)
        return True

    _record_success(engine, job, outcome, moment)
    return True


def _record_success(
    engine: Engine, job: OptimizationJob, result: AssignmentResult, now: datetime
) -> None:
    result_id = _result_id(job)
    save_assignment_result(engine, result, result_id=result_id, created_at=now)  # short tx
    job_queue.mark_succeeded(engine, job.id, result_id)  # short tx


def run_forever(engine: Engine, config: AppConfig) -> None:  # pragma: no cover - CLI loop
    """Poll for jobs. Started by systemd/supervisor as a separate process (A-07)."""
    while True:
        if not step(engine, config):
            time.sleep(config.worker_poll_seconds)


def main() -> None:  # pragma: no cover - CLI entry point
    from data_management import create_db_engine

    config = AppConfig()
    run_forever(create_db_engine(config.database_url), config)


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["main", "run_forever", "step"]
