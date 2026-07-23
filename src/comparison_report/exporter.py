"""LC-04 ReportExporter: ComparisonReport -> CSV (DP-05).

Reuses U-03's serialize_csv with an injected sanitiser (U03-H5). The report is
aggregates only -- no PII (SECURITY-03, BR-CMP11).
"""

from __future__ import annotations

from data_management.csv_codec import Sanitizer, identity_sanitizer, serialize_csv

from .report import ComparisonReport

_HEADER = ("指標", "ベースライン", "最適化", "削減量", "削減率")


def export_report_csv(
    report: ComparisonReport, *, sanitize: Sanitizer = identity_sanitizer
) -> bytes:
    rows = [
        [
            "総移動時間(秒)",
            str(report.baseline_time_seconds),
            str(report.optimized_time_seconds),
            str(report.time_reduction_seconds),
            f"{report.time_reduction_rate:.4f}",
        ],
        [
            "総移動費用(円)",
            f"{report.baseline_cost_yen:.2f}",
            f"{report.optimized_cost_yen:.2f}",
            f"{report.cost_reduction_yen:.2f}",
            f"{report.cost_reduction_rate:.4f}",
        ],
    ]
    return serialize_csv(_HEADER, rows, sanitize=sanitize)


__all__ = ["export_report_csv"]
