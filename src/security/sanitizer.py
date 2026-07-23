"""SEC-05 input sanitisation (MU-02).

CSV formula injection: a cell beginning with =, +, - or @ is executed as a formula
when the exported file is opened in Excel. Prefixing an apostrophe makes the
spreadsheet treat it as text.

This function is INJECTED into U-03's serialize_csv and U-05's export_report_csv by
U-07 (U03-H5, U06-H3). That indirection is why U-03 and U-05 need no dependency on
the security unit at all -- the dependency graph stays as designed while the
defence still applies at every export.
"""

from __future__ import annotations

#: Characters that make a spreadsheet treat a cell as a formula.
DANGEROUS_PREFIXES = frozenset({"=", "+", "-", "@"})


def sanitize_csv_cell(value: str) -> str:
    """Neutralise a formula-injection payload; leave everything else untouched."""
    return "'" + value if value[:1] in DANGEROUS_PREFIXES else value


__all__ = ["DANGEROUS_PREFIXES", "sanitize_csv_cell"]
