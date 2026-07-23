"""U-05 comparison-report — replay a past event and quantify the reduction.

Composes U-02 (distance/cost), U-03 (persistence/CSV) and U-04 (optimisation) to
compare the current workplace-unit assignment against the optimised one, under
identical conditions (FR-05). Zero new production dependencies.

Layers:
  * metrics     — the single shared metrics_for function (DP-01)
  * report      — ComparisonReport / ManualBaseline
  * replay      — ReplayBuilder (HistoricalRecord -> AssignmentProblem)
  * evaluator   — BaselineEvaluator (totals + objective via U-04)
  * service     — ComparisonService (orchestration, fail closed)
  * exporter    — ReportExporter (U-03 serialize_csv)
  * repository  — HistoricalRepository (ingest actuals)
"""

from __future__ import annotations

from .evaluator import evaluate_totals, objective_of
from .exporter import export_report_csv
from .metrics import Master, MetricsFor, make_metrics_for
from .replay import build_replay
from .report import ComparisonReport, ManualBaseline
from .repository import parse_historical_assignments, save_historical_marker
from .service import ComparisonService

__all__ = [
    "ComparisonReport",
    "ComparisonService",
    "ManualBaseline",
    "Master",
    "MetricsFor",
    "build_replay",
    "evaluate_totals",
    "export_report_csv",
    "make_metrics_for",
    "objective_of",
    "parse_historical_assignments",
    "save_historical_marker",
]
