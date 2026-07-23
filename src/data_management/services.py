"""LC-04 services: S-01 EventService, S-02 MasterDataService, S-03 AvailabilityService.

Each service owns its transaction boundary (DP-01). A CSV import is three phases
(business-logic-model.md 2.1): parse, then validate EVERY row accumulating
line-numbered errors (BR-DM02), then -- only if there were none -- persist inside
a single ``engine.begin()`` block. A failure in any phase leaves the database
exactly as it was (BR-DM01, fail closed). Errors carry IDs and line numbers, never
a staff name (BR-DM14).

For a school-district import the distance cache is fully recomputed inside the
SAME transaction as the master write (DP-04): if the recompute fails, the master
write rolls back too, so a committed master can never coexist with a stale cache.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import Engine

from distance_cost import compute_district_distance_matrix
from shared_kernel import (
    AvailabilityDeclaration,
    Coordinates,
    Department,
    DepartmentId,
    DomainError,
    Event,
    EventId,
    EventStatus,
    Facility,
    FacilityId,
    InvalidStateTransitionError,
    JobType,
    Position,
    Qualification,
    QualificationRequirement,
    ReasonCategory,
    SchoolDistrict,
    SchoolDistrictId,
    Staff,
    StaffId,
    from_japanese,
    to_japanese,
)

from . import repositories
from .csv_codec import (
    CsvImportError,
    ImportSummary,
    RowError,
    Sanitizer,
    identity_sanitizer,
    parse_csv,
    serialize_csv,
)

#: Declared timestamps in the CSV are wall-clock JST; stored as UTC (U01-H12).
JST = timezone(timedelta(hours=9))

# CSV column headers (coordinator-facing, Japanese).
_DISTRICT_COLUMNS = ("小学校区ID", "名称", "緯度", "経度")
_STAFF_COLUMNS = ("職員ID", "氏名", "所属部署ID", "職種", "役職", "居住小学校区ID", "資格")
_FACILITY_COLUMNS = ("施設ID", "名称", "小学校区ID", "必要人数", "資格要件")
_DECLARATION_COLUMNS = ("職員ID", "従事可否", "申告日時", "理由区分", "その他理由")

_AVAILABLE_LABEL = "可"
_UNAVAILABLE_LABEL = "不可"


def _requirement_from_japanese(label: str) -> Qualification | Position | JobType:
    """A facility requirement label -> enum, searching all three requirement enums."""
    candidates: list[Qualification | Position | JobType] = [
        *Qualification,
        *Position,
        *JobType,
    ]
    for member in candidates:
        if member.japanese == label:
            return member
    raise ValueError(f"unknown requirement: {label}")


@dataclass(frozen=True, slots=True)
class SufficiencyStatus:
    """Three-way sufficiency (BR-DM08). available+unavailable+undeclared == all_staff."""

    available: int
    unavailable: int
    undeclared: int
    required: int
    shortage: int


# ---------------------------------------------------------------------------
# S-02 MasterDataService
# ---------------------------------------------------------------------------


class MasterDataService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # --- school districts ---------------------------------------------------

    def import_school_districts(self, raw: bytes) -> ImportSummary:
        parsed = parse_csv(raw, required_columns=_DISTRICT_COLUMNS)
        errors: list[RowError] = []
        districts: list[SchoolDistrict] = []
        seen: set[str] = set()
        for line, row in enumerate(parsed.rows, start=2):
            district_id = row["小学校区ID"]
            if district_id in seen:
                errors.append(RowError(line, f"duplicate 小学校区ID {district_id}"))
                continue
            seen.add(district_id)
            try:
                districts.append(
                    SchoolDistrict(
                        id=SchoolDistrictId(district_id),
                        name=row["名称"],
                        representative_point=Coordinates(
                            latitude=float(row["緯度"]),
                            longitude=float(row["経度"]),
                        ),
                    )
                )
            except (ValueError, DomainError) as exc:
                errors.append(RowError(line, f"小学校区 {district_id}: {exc}"))
        if errors:
            raise CsvImportError(errors)

        with self._engine.begin() as conn:
            count = repositories.insert_school_districts(conn, districts)
            # DP-04: recompute the distance cache in the SAME transaction.
            all_districts = repositories.find_all_school_districts(conn)
            entries = compute_district_distance_matrix(all_districts)
            cache = repositories.SqlDistanceCache(conn)
            cache.invalidate_all()
            cache.put_distances(entries)
        return ImportSummary(success_count=count)

    def export_school_districts(self, sanitize: Sanitizer = identity_sanitizer) -> bytes:
        with self._engine.connect() as conn:
            districts = repositories.find_all_school_districts(conn)
        rows = [
            [
                str(d.id),
                d.name,
                str(d.representative_point.latitude),
                str(d.representative_point.longitude),
            ]
            for d in districts
        ]
        return serialize_csv(_DISTRICT_COLUMNS, rows, sanitize=sanitize)

    # --- staff --------------------------------------------------------------

    def import_staff(self, raw: bytes) -> ImportSummary:
        parsed = parse_csv(raw, required_columns=_STAFF_COLUMNS)
        with self._engine.connect() as conn:
            known_districts = repositories.existing_district_ids(conn)
            known_departments = repositories.existing_department_ids(conn)

        errors: list[RowError] = []
        members: list[Staff] = []
        seen: set[str] = set()
        for line, row in enumerate(parsed.rows, start=2):
            staff_id = row["職員ID"]
            if staff_id in seen:
                errors.append(RowError(line, f"duplicate 職員ID {staff_id}"))
                continue
            seen.add(staff_id)
            district_id = row["居住小学校区ID"]
            department_id = row["所属部署ID"]
            if district_id not in known_districts:
                errors.append(RowError(line, f"職員 {staff_id}: unknown 小学校区 {district_id}"))
                continue
            if department_id not in known_departments:
                errors.append(RowError(line, f"職員 {staff_id}: unknown 部署 {department_id}"))
                continue
            try:
                qualifications = frozenset(
                    from_japanese(Qualification, label)
                    for label in _split_list(row["資格"])
                )
                members.append(
                    Staff(
                        id=StaffId(staff_id),
                        name=row["氏名"],
                        department_id=DepartmentId(department_id),
                        job_type=from_japanese(JobType, row["職種"]),
                        position=from_japanese(Position, row["役職"]),
                        residence_district_id=SchoolDistrictId(district_id),
                        qualifications=qualifications,
                    )
                )
            except (ValueError, DomainError) as exc:
                errors.append(RowError(line, f"職員 {staff_id}: {exc}"))
        if errors:
            raise CsvImportError(errors)

        with self._engine.begin() as conn:
            count = repositories.insert_staff(conn, members)
        return ImportSummary(success_count=count)

    def export_staff(self, sanitize: Sanitizer = identity_sanitizer) -> bytes:
        with self._engine.connect() as conn:
            members = repositories.find_all_staff(conn)
        rows: list[list[str]] = []
        for m in members:
            qualifications = ";".join(
                sorted(to_japanese(q) for q in m.qualifications)
            )
            rows.append(
                [
                    str(m.id),
                    m.name,
                    str(m.department_id),
                    to_japanese(m.job_type),
                    to_japanese(m.position),
                    str(m.residence_district_id),
                    qualifications,
                ]
            )
        return serialize_csv(_STAFF_COLUMNS, rows, sanitize=sanitize)

    # --- facilities ---------------------------------------------------------

    def import_facilities(self, raw: bytes) -> ImportSummary:
        parsed = parse_csv(raw, required_columns=_FACILITY_COLUMNS)
        with self._engine.connect() as conn:
            known_districts = repositories.existing_district_ids(conn)

        errors: list[RowError] = []
        facilities: list[Facility] = []
        seen: set[str] = set()
        for line, row in enumerate(parsed.rows, start=2):
            facility_id = row["施設ID"]
            if facility_id in seen:
                errors.append(RowError(line, f"duplicate 施設ID {facility_id}"))
                continue
            seen.add(facility_id)
            district_id = row["小学校区ID"]
            if district_id not in known_districts:
                errors.append(RowError(line, f"施設 {facility_id}: unknown 小学校区 {district_id}"))
                continue
            try:
                requirements = _parse_requirements(row["資格要件"])
                facilities.append(
                    Facility(
                        id=FacilityId(facility_id),
                        name=row["名称"],
                        district_id=SchoolDistrictId(district_id),
                        required_headcount=int(row["必要人数"]),
                        qualification_requirements=requirements,
                    )
                )
            except (ValueError, DomainError) as exc:
                errors.append(RowError(line, f"施設 {facility_id}: {exc}"))
        if errors:
            raise CsvImportError(errors)

        with self._engine.begin() as conn:
            count = repositories.insert_facilities(conn, facilities)
        return ImportSummary(success_count=count)

    def export_facilities(self, sanitize: Sanitizer = identity_sanitizer) -> bytes:
        with self._engine.connect() as conn:
            facilities = repositories.find_all_facilities(conn)
        rows: list[list[str]] = []
        for f in facilities:
            requirement_cell = ";".join(
                f"{to_japanese(req.requirement)}:{req.required_count}"
                for req in f.qualification_requirements
            )
            rows.append(
                [
                    str(f.id),
                    f.name,
                    str(f.district_id),
                    str(f.required_headcount),
                    requirement_cell,
                ]
            )
        return serialize_csv(_FACILITY_COLUMNS, rows, sanitize=sanitize)

    # --- departments (no CSV importer in scope; direct save for setup) ------

    def save_departments(self, departments: Iterable[Department]) -> int:
        with self._engine.begin() as conn:
            return repositories.insert_departments(conn, departments)


# ---------------------------------------------------------------------------
# S-03 AvailabilityService
# ---------------------------------------------------------------------------


class AvailabilityService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def import_declarations(self, event_id: EventId, raw: bytes) -> ImportSummary:
        parsed = parse_csv(raw, required_columns=_DECLARATION_COLUMNS)
        with self._engine.connect() as conn:
            known_staff = repositories.existing_staff_ids(conn)

        errors: list[RowError] = []
        declarations: list[AvailabilityDeclaration] = []
        seen: set[tuple[str, str]] = set()  # (staff_id, declared_at) within the CSV
        for line, row in enumerate(parsed.rows, start=2):
            staff_id = row["職員ID"]
            if staff_id not in known_staff:
                errors.append(RowError(line, f"職員 {staff_id}: not in staff master"))
                continue
            try:
                declared_at = _parse_jst_to_utc(row["申告日時"])
            except ValueError as exc:
                errors.append(RowError(line, f"職員 {staff_id}: {exc}"))
                continue
            key = (staff_id, declared_at.isoformat())
            if key in seen:
                errors.append(
                    RowError(line, f"職員 {staff_id}: duplicate 申告日時 (U01-H11)")
                )
                continue
            seen.add(key)
            try:
                declarations.append(
                    _build_declaration(staff_id, event_id, row, declared_at)
                )
            except (ValueError, DomainError) as exc:
                errors.append(RowError(line, f"職員 {staff_id}: {exc}"))
        if errors:
            raise CsvImportError(errors)

        with self._engine.begin() as conn:
            count = repositories.insert_declarations(conn, event_id, declarations)
        return ImportSummary(success_count=count)

    def effective_declarations(self, event_id: EventId) -> list[AvailabilityDeclaration]:
        with self._engine.connect() as conn:
            return repositories.effective_declarations(conn, event_id)

    def declaration_history(
        self, staff_id: StaffId, event_id: EventId
    ) -> list[AvailabilityDeclaration]:
        with self._engine.connect() as conn:
            return repositories.declaration_history(conn, staff_id, event_id)

    def sufficiency_status(self, event_id: EventId) -> SufficiencyStatus:
        with self._engine.connect() as conn:
            effective = repositories.effective_declarations(conn, event_id)
            total_staff = repositories.all_staff_count(conn)
            required = repositories.total_required_headcount(conn)
        available_ids = {d.staff_id for d in effective if d.is_available}
        unavailable_ids = {d.staff_id for d in effective if not d.is_available}
        undeclared = total_staff - len(available_ids) - len(unavailable_ids)
        return SufficiencyStatus(
            available=len(available_ids),
            unavailable=len(unavailable_ids),
            undeclared=undeclared,
            required=required,
            shortage=max(0, required - len(available_ids)),
        )


# ---------------------------------------------------------------------------
# S-01 EventService
# ---------------------------------------------------------------------------


class EventService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_event(self, event: Event) -> None:
        with self._engine.begin() as conn:
            repositories.insert_event(conn, event)

    def get_event(self, event_id: EventId) -> Event | None:
        with self._engine.connect() as conn:
            return repositories.get_event(conn, event_id)

    def transition(self, event_id: EventId, target: EventStatus) -> Event:
        """Apply a transition, checking DB-dependent preconditions first (BR-DM09)."""
        with self._engine.begin() as conn:
            event = repositories.get_event(conn, event_id)
            if event is None:
                raise InvalidStateTransitionError(
                    "event not found", violated_rule="BR-DM09", event_id=event_id
                )
            if (
                event.status is EventStatus.DRAFT
                and target is EventStatus.COLLECTING_DECLARATIONS
                and repositories.facility_count(conn) < 1
            ):
                raise InvalidStateTransitionError(
                    "cannot start collecting declarations with no facilities registered",
                    violated_rule="BR-DM09",
                    event_id=event_id,
                )
            updated = event.transition_to(target)  # raises on an illegal transition
            repositories.update_event_status(conn, event_id, updated.status.name)
            return updated

    def delete_event(self, event_id: EventId) -> None:
        """Delete an event (cascades to declarations/assignments). Confirmed is refused."""
        with self._engine.begin() as conn:
            event = repositories.get_event(conn, event_id)
            if event is None:
                return
            if event.status is EventStatus.CONFIRMED:
                raise InvalidStateTransitionError(
                    "a confirmed event cannot be deleted",
                    violated_rule="BR-DM10",
                    event_id=event_id,
                )
            repositories.delete_event(conn, event_id)


# ---------------------------------------------------------------------------
# parsing helpers
# ---------------------------------------------------------------------------


def _split_list(cell: str) -> list[str]:
    return [part.strip() for part in cell.split(";") if part.strip()]


def _parse_requirements(cell: str) -> tuple[QualificationRequirement, ...]:
    requirements: list[QualificationRequirement] = []
    for item in _split_list(cell):
        label, _, count_text = item.partition(":")
        if not count_text:
            raise ValueError(f"malformed requirement '{item}' (expected label:count)")
        requirements.append(
            QualificationRequirement(
                requirement=_requirement_from_japanese(label.strip()),
                required_count=int(count_text.strip()),
            )
        )
    return tuple(requirements)


def _parse_jst_to_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"invalid 申告日時 '{value}'") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    return parsed.astimezone(UTC)


def _build_declaration(
    staff_id: str, event_id: EventId, row: dict[str, str], declared_at: datetime
) -> AvailabilityDeclaration:
    label = row["従事可否"].strip()
    if label == _AVAILABLE_LABEL:
        is_available = True
    elif label == _UNAVAILABLE_LABEL:
        is_available = False
    else:
        raise ValueError(f"従事可否 must be '{_AVAILABLE_LABEL}' or '{_UNAVAILABLE_LABEL}'")

    reason_label = row["理由区分"].strip()
    note = row["その他理由"].strip() or None
    reason = from_japanese(ReasonCategory, reason_label) if reason_label else None
    return AvailabilityDeclaration(
        staff_id=StaffId(staff_id),
        event_id=event_id,
        is_available=is_available,
        declared_at=declared_at,
        reason_category=reason,
        other_reason_note=note,
    )


__all__ = [
    "JST",
    "AvailabilityService",
    "EventService",
    "MasterDataService",
    "SufficiencyStatus",
]
