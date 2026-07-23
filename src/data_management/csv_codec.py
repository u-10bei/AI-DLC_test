"""P-07 CsvCodec / A-04 CsvAdapter: CSV parsing and serialisation.

Parsing uses the standard-library ``csv`` module (Q1=A) -- 2,000 rows in well
under a second, no pandas. Serialisation takes a ``sanitize`` callable as an
argument (dependency injection, U03-H5): U-03 must NOT depend on U-06, so the
formula-injection defence (BR-DM04, MU-02) is supplied by the caller. U-07 wires
in U-06's ``SEC-05.sanitize_csv_cell``; U-03 defaults to the identity, which is
correct for internal round-trips.

Errors never carry PII (BR-DM14): a ``RowError`` holds a line number and an
ID-only message, never a staff name.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from shared_kernel import DomainError

Sanitizer = Callable[[str], str]


def identity_sanitizer(value: str) -> str:
    """The default: no transform. U-07 injects U-06's escaper for human exports."""
    return value


@dataclass(frozen=True, slots=True)
class RowError:
    """One import problem, tied to its CSV line. No PII (BR-DM14)."""

    line: int
    message: str


@dataclass(frozen=True, slots=True)
class ImportSummary:
    """Outcome of a successful import."""

    success_count: int


class CsvImportError(DomainError):
    """A CSV import failed. Carries every row error, not just the first (BR-DM02).

    fail closed (BR-DM01): when this is raised the database is untouched -- the
    errors were all collected before the persistence phase began.
    """

    def __init__(self, errors: Sequence[RowError]) -> None:
        super().__init__(
            f"CSV import failed with {len(errors)} error(s)",
            violated_rule="BR-DM01",
        )
        self.errors: tuple[RowError, ...] = tuple(errors)


@dataclass(frozen=True, slots=True)
class ParsedCsv:
    """Header plus data rows keyed by column name. Line 1 is the header."""

    fieldnames: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


def parse_csv(raw: bytes, *, required_columns: Sequence[str]) -> ParsedCsv:
    """Decode and parse ``raw``. Raise CsvImportError on a structural problem.

    ``utf-8-sig`` transparently drops the BOM Excel writes. A missing required
    column is a single line-1 error; the caller never sees a half-parsed file.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CsvImportError([RowError(line=1, message="file is not valid UTF-8")]) from None

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = tuple(reader.fieldnames or ())
    missing = [column for column in required_columns if column not in fieldnames]
    if missing:
        raise CsvImportError(
            [RowError(line=1, message=f"missing required column(s): {', '.join(missing)}")]
        )

    rows: list[dict[str, str]] = []
    for record in reader:
        rows.append({key: (value if value is not None else "") for key, value in record.items()})
    return ParsedCsv(fieldnames=fieldnames, rows=tuple(rows))


def serialize_csv(
    header: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    sanitize: Sanitizer = identity_sanitizer,
) -> bytes:
    """Serialise ``rows`` to CSV bytes, passing every cell through ``sanitize``.

    The header is not sanitised (it is fixed, developer-controlled); only data
    cells are, since those originate from imported/user data (BR-DM04).
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(list(header))
    for row in rows:
        writer.writerow([sanitize(cell) for cell in row])
    return buffer.getvalue().encode("utf-8")


__all__ = [
    "CsvImportError",
    "ImportSummary",
    "ParsedCsv",
    "RowError",
    "Sanitizer",
    "identity_sanitizer",
    "parse_csv",
    "serialize_csv",
]
