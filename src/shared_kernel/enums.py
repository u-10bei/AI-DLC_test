"""Enumerations and the Japanese <-> identifier conversion table (LC-03).

The same concept appears in three places: as a code identifier, as a column
value in the CSV a coordinator builds in Excel, and as a JSON value in the API.
Code uses English identifiers; the boundaries convert (NFR Design Q3=A).

The conversion table lives here, in shared-kernel, so that U-03's CsvAdapter and
U-07's DTO layer cannot drift apart -- both read the same table.

Enum *values* are provisional. They are replaced once the real job-title,
position and qualification lists are supplied (NFR Requirements decision 8).
Because these are enums and not free strings, an unrecognised value fails the
import loudly instead of being absorbed.
"""

from __future__ import annotations

from enum import Enum
from typing import TypeVar

from .exceptions import UnknownEnumValueError


class _JapaneseEnum(str, Enum):
    """Enum whose members carry their Japanese label as the member value.

    Inheriting from ``str`` makes the label the member's value *and* keeps the
    member usable wherever a string is expected, without an unchecked cast.
    """

    @property
    def japanese(self) -> str:
        # `self.value` is typed Any by mypy; the member *is* its label because
        # of the `str` base, so read it through str itself.
        return str.__str__(self)


class JobType(_JapaneseEnum):
    CLERICAL = "事務職"
    TECHNICAL = "技術職"
    NURSERY_TEACHER = "保育士"
    PUBLIC_HEALTH_NURSE = "保健師"


class Position(_JapaneseEnum):
    MANAGER = "管理職"
    GENERAL = "一般職"


class Qualification(_JapaneseEnum):
    DISASTER_PREVENTION_SPECIALIST = "防災士"
    EMERGENCY_LIFESAVING_TECHNICIAN = "救急救命士"


class EventType(_JapaneseEnum):
    DISASTER_SHELTER_SUPPORT = "災害時避難所応援"
    ELECTION_ADMINISTRATION = "選挙事務"
    OTHER = "その他"


class EventStatus(_JapaneseEnum):
    DRAFT = "準備中"
    COLLECTING_DECLARATIONS = "申告受付中"
    OPTIMIZED = "割当計算済"
    CONFIRMED = "確定"


class ReasonCategory(_JapaneseEnum):
    LEAVE = "休暇"
    CHILD_OR_ELDER_CARE = "育児・介護"
    HEALTH_CONSIDERATION = "健康上の配慮"
    OTHER = "その他"


class SolverStatus(Enum):
    """Internal only. The UI supplies its own labels."""

    OPTIMAL = "OPTIMAL"
    TIME_LIMIT_REACHED = "TIME_LIMIT_REACHED"
    CANCELLED = "CANCELLED"


# ---------------------------------------------------------------------------
# Event state transitions (business-rules.md section 2.2)
#
# reopen_declarations (OPTIMIZED -> COLLECTING_DECLARATIONS) exists because
# US-24 registers additional availability declarations after an optimization has
# already run. CONFIRMED is terminal: a confirmed assignment is not walked back.
# ---------------------------------------------------------------------------
ALLOWED_EVENT_TRANSITIONS: dict[EventStatus, frozenset[EventStatus]] = {
    EventStatus.DRAFT: frozenset({EventStatus.COLLECTING_DECLARATIONS}),
    EventStatus.COLLECTING_DECLARATIONS: frozenset({EventStatus.OPTIMIZED}),
    EventStatus.OPTIMIZED: frozenset({EventStatus.COLLECTING_DECLARATIONS, EventStatus.CONFIRMED}),
    EventStatus.CONFIRMED: frozenset(),
}

DELETABLE_EVENT_STATUSES: frozenset[EventStatus] = frozenset(
    {EventStatus.DRAFT, EventStatus.COLLECTING_DECLARATIONS, EventStatus.OPTIMIZED}
)


# ---------------------------------------------------------------------------
# Boundary conversion
# ---------------------------------------------------------------------------

E = TypeVar("E", bound=_JapaneseEnum)


def to_japanese(member: _JapaneseEnum) -> str:
    """Identifier -> Japanese label, for CSV export and API responses."""
    return member.japanese


def from_japanese(enum_cls: type[E], label: str) -> E:
    """Japanese label -> identifier, for CSV import and API requests.

    An unknown label raises rather than falling back to OTHER. A job title the
    system has never heard of must stop the import with a row number, not be
    quietly reclassified (SECURITY-15, fail closed).
    """
    for member in enum_cls:
        if member.japanese == label:
            return member
    raise UnknownEnumValueError(
        f"unknown {enum_cls.__name__} value",
        violated_rule="LC-03",
    )


__all__ = [
    "ALLOWED_EVENT_TRANSITIONS",
    "DELETABLE_EVENT_STATUSES",
    "EventStatus",
    "EventType",
    "JobType",
    "Position",
    "Qualification",
    "ReasonCategory",
    "SolverStatus",
    "from_japanese",
    "to_japanese",
]
