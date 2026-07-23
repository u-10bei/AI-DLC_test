"""Stateful test of the job state machine (PBT-06, P-API05).

The claim rule is the interesting one. A job must be claimable exactly once: the
thing behind a second claim is a 300-second solve running twice. Example tests
check the transitions someone thought of; this checks that random sequences of
enqueue/claim/finish never produce a job that leaves a terminal state or gets
claimed twice.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from api_orchestration import JobId, JobState, OptimizationJob, ReoptimizationMode, job_queue
from data_management import create_all, create_db_engine
from shared_kernel import EventId

from .support import DISTRICTS_CSV, FACILITY_CSV, STAFF_CSV


class JobLifecycle(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.engine = create_db_engine("sqlite://")
        create_all(self.engine)
        self._seed_event()
        self.now = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)
        self.counter = 0
        # model: job id -> state
        self.model: dict[str, JobState] = {}

    def _seed_event(self) -> None:
        from data_management import EventService, MasterDataService
        from shared_kernel import Department, DepartmentId, Event, EventType

        master = MasterDataService(self.engine)
        master.save_departments([Department(id=DepartmentId("D1"), name="d")])
        master.import_school_districts(DISTRICTS_CSV)
        master.import_staff(STAFF_CSV)
        master.import_facilities(FACILITY_CSV)
        EventService(self.engine).create_event(
            Event(
                id=EventId("E1"),
                type=EventType.DISASTER_SHELTER_SUPPORT,
                name="e",
                scheduled_date=datetime(2026, 8, 1).date(),
            )
        )

    @rule()
    def enqueue(self) -> None:
        self.counter += 1
        self.now += timedelta(seconds=1)
        job_id = f"J{self.counter}"
        job_queue.enqueue(
            self.engine,
            OptimizationJob(
                id=JobId(job_id),
                event_id=EventId("E1"),
                mode=ReoptimizationMode.FULL,
                state=JobState.QUEUED,
                created_at=self.now,
            ),
        )
        self.model[job_id] = JobState.QUEUED

    @rule()
    def claim(self) -> None:
        claimed = job_queue.claim_next(self.engine)
        queued = [j for j, s in self.model.items() if s is JobState.QUEUED]
        if not queued:
            assert claimed is None  # nothing to take
            return
        assert claimed is not None
        assert self.model[str(claimed.id)] is JobState.QUEUED  # never claimed twice
        self.model[str(claimed.id)] = JobState.RUNNING

    @precondition(lambda self: any(s is JobState.RUNNING for s in self.model.values()))
    @rule()
    def finish_succeeded(self) -> None:
        job_id = next(j for j, s in self.model.items() if s is JobState.RUNNING)
        job_queue.mark_succeeded(self.engine, JobId(job_id), f"R-{job_id}")
        self.model[job_id] = JobState.SUCCEEDED

    @precondition(lambda self: any(s is JobState.RUNNING for s in self.model.values()))
    @rule()
    def finish_infeasible(self) -> None:
        job_id = next(j for j, s in self.model.items() if s is JobState.RUNNING)
        job_queue.mark_infeasible(self.engine, JobId(job_id), "TOTAL_SHORTAGE")
        self.model[job_id] = JobState.INFEASIBLE

    @precondition(lambda self: any(s is JobState.RUNNING for s in self.model.values()))
    @rule()
    def finish_failed(self) -> None:
        job_id = next(j for j, s in self.model.items() if s is JobState.RUNNING)
        job_queue.mark_failed(self.engine, JobId(job_id), "SomeError")
        self.model[job_id] = JobState.FAILED

    @invariant()
    def stored_state_matches_model(self) -> None:
        for job_id, expected in self.model.items():
            stored = job_queue.get_job(self.engine, JobId(job_id))
            assert stored is not None
            assert stored.state is expected

    @invariant()
    def a_terminal_job_is_never_claimable(self) -> None:
        """P-API05: nothing pulls a finished job back into the queue."""
        for job_id, state in self.model.items():
            if state in (JobState.SUCCEEDED, JobState.INFEASIBLE, JobState.FAILED):
                stored = job_queue.get_job(self.engine, JobId(job_id))
                assert stored is not None
                assert stored.state is not JobState.QUEUED


JobLifecycle.TestCase.settings = settings(max_examples=15, stateful_step_count=12, deadline=None)
TestJobLifecycle = JobLifecycle.TestCase
