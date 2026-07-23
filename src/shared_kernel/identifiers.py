"""Identifier types.

All identifiers are natural keys carried over from existing systems (staff
numbers, shelter management numbers, administrative school-district codes).
They are all strings, which makes them trivially interchangeable at runtime --
`Assignment(staff_id=facility_id, ...)` would be accepted silently.

`NewType` makes mypy reject that mix-up at zero runtime cost. It only works
under `strict = true`, which pyproject.toml enforces in CI.
"""

from typing import NewType

StaffId = NewType("StaffId", str)
FacilityId = NewType("FacilityId", str)
SchoolDistrictId = NewType("SchoolDistrictId", str)
DepartmentId = NewType("DepartmentId", str)
EventId = NewType("EventId", str)

__all__ = [
    "DepartmentId",
    "EventId",
    "FacilityId",
    "SchoolDistrictId",
    "StaffId",
]
