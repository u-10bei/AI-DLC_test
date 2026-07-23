"""Example-based tests for U-01 (PBT-10).

PBT-10: property tests must not be the only coverage of a business-critical
path. These pin concrete behaviour with concrete values, and several of them are
lifted straight from a story's acceptance criteria.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from shared_kernel import (
    REDACTED,
    AmbiguousDeclarationError,
    AvailabilityDeclaration,
    Coordinates,
    DepartmentId,
    DuplicateQualificationRequirementError,
    Event,
    EventId,
    EventStatus,
    EventType,
    Facility,
    FacilityId,
    InconsistentDeclarationError,
    InvalidCoordinatesError,
    InvalidStateTransitionError,
    JobType,
    Position,
    QualificationRequirement,
    QualificationRequirementExceedsHeadcountError,
    ReasonCategory,
    SchoolDistrictId,
    Staff,
    StaffId,
    UnknownEnumValueError,
    effective_declaration_for,
    from_japanese,
)

STAFF_ID = StaffId("S001")
EVENT_ID = EventId("E001")
T0 = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
T1 = datetime(2026, 7, 2, 9, 0, tzinfo=UTC)


def _event(status: EventStatus = EventStatus.DRAFT) -> Event:
    return Event(
        id=EVENT_ID,
        type=EventType.DISASTER_SHELTER_SUPPORT,
        name="令和8年7月豪雨 避難所開設",
        scheduled_date=date(2026, 7, 15),
        status=status,
    )


# ---------------------------------------------------------------------------
# US-09 acceptance criterion: latitude 95.0 is rejected
# ---------------------------------------------------------------------------


def test_us09_latitude_95_is_rejected() -> None:
    with pytest.raises(InvalidCoordinatesError) as exc:
        Coordinates(latitude=95.0, longitude=139.0)
    assert exc.value.context() == {"violated_rule": "BR-01"}


def test_coordinates_at_the_poles_are_accepted() -> None:
    assert Coordinates(latitude=90.0, longitude=180.0).latitude == 90.0


# ---------------------------------------------------------------------------
# US-08 acceptance criterion: a facility needing 5 people cannot need 6 managers
# ---------------------------------------------------------------------------


def test_us08_qualification_requirement_exceeding_headcount_is_rejected() -> None:
    with pytest.raises(QualificationRequirementExceedsHeadcountError):
        Facility(
            id=FacilityId("F001"),
            name="第一小学校",
            district_id=SchoolDistrictId("SD01"),
            required_headcount=5,
            qualification_requirements=(
                QualificationRequirement(requirement=Position.MANAGER, required_count=6),
            ),
        )


def test_facility_with_duplicate_requirement_is_rejected() -> None:
    with pytest.raises(DuplicateQualificationRequirementError):
        Facility(
            id=FacilityId("F001"),
            name="第一小学校",
            district_id=SchoolDistrictId("SD01"),
            required_headcount=5,
            qualification_requirements=(
                QualificationRequirement(requirement=Position.MANAGER, required_count=1),
                QualificationRequirement(requirement=Position.MANAGER, required_count=1),
            ),
        )


def test_facility_with_requirements_summing_to_headcount_is_accepted() -> None:
    facility = Facility(
        id=FacilityId("F001"),
        name="第一小学校",
        district_id=SchoolDistrictId("SD01"),
        required_headcount=5,
        qualification_requirements=(
            QualificationRequirement(requirement=Position.MANAGER, required_count=2),
        ),
    )
    assert facility.required_headcount == 5


# ---------------------------------------------------------------------------
# SECURITY-03: Staff.__repr__ redacts the name and the residence district
# ---------------------------------------------------------------------------


def test_staff_repr_redacts_personal_information() -> None:
    staff = Staff(
        id=STAFF_ID,
        name="鈴木太郎",
        department_id=DepartmentId("D01"),
        job_type=JobType.CLERICAL,
        position=Position.GENERAL,
        residence_district_id=SchoolDistrictId("SD03"),
    )

    rendered = repr(staff)

    assert "鈴木太郎" not in rendered
    assert "SD03" not in rendered
    assert rendered.count(REDACTED) == 2
    # The staff ID stays: it is needed for debugging and identifies no person
    # on its own.
    assert "S001" in rendered


def test_staff_str_also_redacts() -> None:
    staff = Staff(
        id=STAFF_ID,
        name="鈴木太郎",
        department_id=DepartmentId("D01"),
        job_type=JobType.CLERICAL,
        position=Position.GENERAL,
        residence_district_id=SchoolDistrictId("SD03"),
    )
    assert "鈴木太郎" not in f"{staff}"


# ---------------------------------------------------------------------------
# US-12: effective_declaration_for — four concrete cases
# ---------------------------------------------------------------------------


def test_no_declaration_returns_none() -> None:
    """Undeclared. Not the same as unavailable: this person should be chased."""
    assert effective_declaration_for(STAFF_ID, EVENT_ID, []) is None


def test_available_declaration_is_returned() -> None:
    declaration = AvailabilityDeclaration(
        staff_id=STAFF_ID, event_id=EVENT_ID, is_available=True, declared_at=T0
    )
    result = effective_declaration_for(STAFF_ID, EVENT_ID, [declaration])
    assert result is not None
    assert result.is_available is True


def test_unavailable_declaration_is_returned() -> None:
    declaration = AvailabilityDeclaration(
        staff_id=STAFF_ID,
        event_id=EVENT_ID,
        is_available=False,
        declared_at=T0,
        reason_category=ReasonCategory.HEALTH_CONSIDERATION,
    )
    result = effective_declaration_for(STAFF_ID, EVENT_ID, [declaration])
    assert result is not None
    assert result.is_available is False
    assert result.reason_category is ReasonCategory.HEALTH_CONSIDERATION


def test_redeclaration_supersedes_the_earlier_one() -> None:
    """US-12: 'unavailable' at T0, 'available' at T1 -> the person is available."""
    earlier = AvailabilityDeclaration(
        staff_id=STAFF_ID,
        event_id=EVENT_ID,
        is_available=False,
        declared_at=T0,
        reason_category=ReasonCategory.OTHER,
        other_reason_note="出張予定",
    )
    later = AvailabilityDeclaration(
        staff_id=STAFF_ID, event_id=EVENT_ID, is_available=True, declared_at=T1
    )

    result = effective_declaration_for(STAFF_ID, EVENT_ID, [earlier, later])

    assert result is later
    assert result.is_available is True


def test_two_declarations_at_the_same_instant_are_refused() -> None:
    """Fail closed. U-03 must guarantee timestamp uniqueness on import (U01-H11)."""
    first = AvailabilityDeclaration(
        staff_id=STAFF_ID, event_id=EVENT_ID, is_available=True, declared_at=T0
    )
    second = AvailabilityDeclaration(
        staff_id=STAFF_ID,
        event_id=EVENT_ID,
        is_available=False,
        declared_at=T0,
        reason_category=ReasonCategory.LEAVE,
    )

    with pytest.raises(AmbiguousDeclarationError):
        effective_declaration_for(STAFF_ID, EVENT_ID, [first, second])


def test_declarations_for_other_events_are_ignored() -> None:
    """The same person, available for one event and unavailable for another."""
    other = AvailabilityDeclaration(
        staff_id=STAFF_ID, event_id=EventId("E002"), is_available=True, declared_at=T1
    )
    assert effective_declaration_for(STAFF_ID, EVENT_ID, [other]) is None


# ---------------------------------------------------------------------------
# BR-05: is_available and reason_category must agree
# ---------------------------------------------------------------------------


def test_available_declaration_with_a_reason_is_rejected() -> None:
    with pytest.raises(InconsistentDeclarationError):
        AvailabilityDeclaration(
            staff_id=STAFF_ID,
            event_id=EVENT_ID,
            is_available=True,
            declared_at=T0,
            reason_category=ReasonCategory.LEAVE,
        )


def test_unavailable_declaration_without_a_reason_is_rejected() -> None:
    with pytest.raises(InconsistentDeclarationError):
        AvailabilityDeclaration(
            staff_id=STAFF_ID, event_id=EVENT_ID, is_available=False, declared_at=T0
        )


def test_reason_other_requires_a_note() -> None:
    with pytest.raises(InconsistentDeclarationError):
        AvailabilityDeclaration(
            staff_id=STAFF_ID,
            event_id=EVENT_ID,
            is_available=False,
            declared_at=T0,
            reason_category=ReasonCategory.OTHER,
        )


def test_note_without_reason_other_is_rejected() -> None:
    with pytest.raises(InconsistentDeclarationError):
        AvailabilityDeclaration(
            staff_id=STAFF_ID,
            event_id=EVENT_ID,
            is_available=False,
            declared_at=T0,
            reason_category=ReasonCategory.LEAVE,
            other_reason_note="不要な補足",
        )


# ---------------------------------------------------------------------------
# Event state machine: the four allowed transitions, and refusals
# ---------------------------------------------------------------------------


def test_the_four_allowed_transitions() -> None:
    draft = _event()

    collecting = draft.start_collecting_declarations()
    assert collecting.status is EventStatus.COLLECTING_DECLARATIONS

    optimized = collecting.mark_optimized()
    assert optimized.status is EventStatus.OPTIMIZED

    # US-24: additional declarations after an optimization has already run.
    reopened = optimized.reopen_declarations()
    assert reopened.status is EventStatus.COLLECTING_DECLARATIONS

    confirmed = optimized.confirm()
    assert confirmed.status is EventStatus.CONFIRMED


def test_draft_cannot_be_confirmed_directly() -> None:
    with pytest.raises(InvalidStateTransitionError):
        _event().confirm()


def test_confirmed_is_terminal() -> None:
    """A confirmed assignment is not walked back; make a new event instead."""
    confirmed = _event(EventStatus.CONFIRMED)
    with pytest.raises(InvalidStateTransitionError):
        confirmed.reopen_declarations()


def test_transition_returns_a_new_event_and_leaves_the_original_alone() -> None:
    draft = _event()
    collecting = draft.start_collecting_declarations()

    assert draft.status is EventStatus.DRAFT
    assert collecting is not draft


# ---------------------------------------------------------------------------
# LC-03: enum conversion refuses unknown values instead of coercing to OTHER
# ---------------------------------------------------------------------------


def test_unknown_japanese_position_is_refused() -> None:
    """課長補佐 is not in the table. It must stop the import, not become OTHER."""
    with pytest.raises(UnknownEnumValueError):
        from_japanese(Position, "課長補佐")


def test_known_japanese_position_converts() -> None:
    assert from_japanese(Position, "管理職") is Position.MANAGER


def test_unknown_value_is_not_coerced_to_other() -> None:
    """ReasonCategory has an OTHER member; an unknown label must still be refused."""
    with pytest.raises(UnknownEnumValueError):
        from_japanese(ReasonCategory, "私用")
