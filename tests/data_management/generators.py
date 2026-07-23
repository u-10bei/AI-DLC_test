"""Generators for U-03 (PBT-07).

Builds a referentially-consistent master dataset: staff reference existing
departments and districts, facilities reference existing districts. Names use a
CSV-safe alphabet (no surrogates or control characters, which cannot survive a
UTF-8 CSV round-trip) so a failing example is a real persistence failure, not a
Unicode edge case unrelated to the property.
"""

from __future__ import annotations

from dataclasses import dataclass

from hypothesis import strategies as st

from shared_kernel import (
    Coordinates,
    Department,
    DepartmentId,
    Facility,
    FacilityId,
    JobType,
    Position,
    Qualification,
    QualificationRequirement,
    SchoolDistrict,
    SchoolDistrictId,
    Staff,
    StaffId,
)

_ID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def _id(prefix: str) -> st.SearchStrategy[str]:
    return st.text(alphabet=_ID_ALPHABET, min_size=1, max_size=6).map(lambda s: f"{prefix}{s}")


def _safe_text(max_size: int = 12) -> st.SearchStrategy[str]:
    return st.text(
        alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x9FFF, exclude_categories=("Cs", "Cc")),
        min_size=1,
        max_size=max_size,
    )


@dataclass(frozen=True)
class Dataset:
    departments: tuple[Department, ...]
    districts: tuple[SchoolDistrict, ...]
    staff: tuple[Staff, ...]
    facilities: tuple[Facility, ...]


@st.composite
def gen_master_dataset(draw: st.DrawFn) -> Dataset:
    districts = draw(
        st.lists(
            st.builds(
                SchoolDistrict,
                id=_id("SD").map(SchoolDistrictId),
                name=_safe_text(),
                representative_point=st.builds(
                    Coordinates,
                    latitude=st.floats(min_value=-90, max_value=90, allow_nan=False),
                    longitude=st.floats(min_value=-180, max_value=180, allow_nan=False),
                ),
            ),
            min_size=1,
            max_size=4,
            unique_by=lambda d: d.id,
        )
    )
    departments = draw(
        st.lists(
            st.builds(
                Department,
                id=_id("D").map(DepartmentId),
                name=_safe_text(),
                concurrent_assignment_cap=st.none() | st.integers(min_value=1, max_value=10),
            ),
            min_size=1,
            max_size=3,
            unique_by=lambda d: d.id,
        )
    )
    district_ids = [d.id for d in districts]
    department_ids = [d.id for d in departments]

    staff = draw(
        st.lists(
            gen_staff_for(department_ids, district_ids),
            min_size=0,
            max_size=6,
            unique_by=lambda s: s.id,
        )
    )
    facilities = draw(
        st.lists(
            gen_facility_for(district_ids),
            min_size=0,
            max_size=4,
            unique_by=lambda f: f.id,
        )
    )
    return Dataset(
        departments=tuple(departments),
        districts=tuple(districts),
        staff=tuple(staff),
        facilities=tuple(facilities),
    )


@st.composite
def gen_staff_for(
    draw: st.DrawFn,
    department_ids: list[DepartmentId],
    district_ids: list[SchoolDistrictId],
) -> Staff:
    return Staff(
        id=StaffId(draw(_id("S"))),
        name=draw(_safe_text()),
        department_id=draw(st.sampled_from(department_ids)),
        job_type=draw(st.sampled_from(list(JobType))),
        position=draw(st.sampled_from(list(Position))),
        residence_district_id=draw(st.sampled_from(district_ids)),
        qualifications=frozenset(
            draw(st.sets(st.sampled_from(list(Qualification)), max_size=2))
        ),
    )


@st.composite
def gen_facility_for(
    draw: st.DrawFn, district_ids: list[SchoolDistrictId]
) -> Facility:
    required_headcount = draw(st.integers(min_value=1, max_value=10))
    pool: list[Qualification | Position | JobType] = [*Qualification, *Position]
    chosen = draw(st.lists(st.sampled_from(pool), max_size=2, unique=True))
    requirements: list[QualificationRequirement] = []
    remaining = required_headcount
    for requirement in chosen:
        if remaining <= 0:
            break
        count = draw(st.integers(min_value=1, max_value=remaining))
        requirements.append(
            QualificationRequirement(requirement=requirement, required_count=count)
        )
        remaining -= count
    return Facility(
        id=FacilityId(draw(_id("F"))),
        name=draw(_safe_text()),
        district_id=draw(st.sampled_from(district_ids)),
        required_headcount=required_headcount,
        qualification_requirements=tuple(requirements),
    )


__all__ = ["Dataset", "gen_facility_for", "gen_master_dataset", "gen_staff_for"]
