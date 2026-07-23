"""Stateful test of the Event state machine (PBT-06).

U-03 is the first unit that owns state transitions, so the Event lifecycle is
driven here with Hypothesis's RuleBasedStateMachine: random transition sequences
against a real database. The machine checks that

  * an allowed transition succeeds and the DB reflects it,
  * a disallowed transition is refused (InvalidStateTransitionError) and the DB
    is left untouched,
  * CONFIRMED is terminal,
  * after every step the stored status equals the model's status.
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from data_management import EventService, MasterDataService
from shared_kernel import (
    ALLOWED_EVENT_TRANSITIONS,
    Department,
    DepartmentId,
    Event,
    EventId,
    EventStatus,
    EventType,
    InvalidStateTransitionError,
)

from .support import fresh_engine

_DISTRICTS = "小学校区ID,名称,緯度,経度\nSD1,一,35.0,139.0\n".encode()
_FACILITY = "施設ID,名称,小学校区ID,必要人数,資格要件\nF1,A,SD1,1,\n".encode()
_EVENT_ID = EventId("E")


class EventLifecycle(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.engine = fresh_engine()
        md = MasterDataService(self.engine)
        md.save_departments([Department(id=DepartmentId("D1"), name="課")])
        md.import_school_districts(_DISTRICTS)
        md.import_facilities(_FACILITY)  # so DRAFT->COLLECTING's precondition can pass
        self.events = EventService(self.engine)
        self.events.create_event(
            Event(
                id=_EVENT_ID,
                type=EventType.DISASTER_SHELTER_SUPPORT,
                name="訓練",
                scheduled_date=date(2026, 8, 1),
            )
        )
        self.model = EventStatus.DRAFT

    @rule(target_status=st.sampled_from(list(EventStatus)))
    def try_transition(self, target_status: EventStatus) -> None:
        allowed = target_status in ALLOWED_EVENT_TRANSITIONS[self.model]
        if allowed:
            updated = self.events.transition(_EVENT_ID, target_status)
            assert updated.status is target_status
            self.model = target_status
        else:
            with pytest.raises(InvalidStateTransitionError):
                self.events.transition(_EVENT_ID, target_status)

    @invariant()
    def db_matches_model(self) -> None:
        stored = self.events.get_event(_EVENT_ID)
        assert stored is not None
        assert stored.status is self.model


EventLifecycle.TestCase.settings = settings(max_examples=25, stateful_step_count=12, deadline=None)
TestEventLifecycle = EventLifecycle.TestCase
