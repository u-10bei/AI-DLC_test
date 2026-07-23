"""U-03 data-management — persistence for the whole backend.

The first unit with real persistence and the first to add production
dependencies (SQLAlchemy, Alembic). It depends only on U-01 shared_kernel and
U-02 distance_cost.

Layers (NFR Design logical components):
  * engine     — LC-01 Engine/SessionFactory (PRAGMAs, echo off)
  * schema     — Core table definitions (owned + skeletons)
  * mappers    — LC-03 row <-> frozen domain type, fail-closed on load
  * repositories — LC-02 P-02/P-03 implementations (parameterised queries)
  * csv_codec  — P-07 parse/serialise (formula-injection sanitiser injected)
  * services   — LC-04 S-01/S-02/S-03, transaction boundaries, fail-closed import

Domain types are never redefined here; U-03 persists U-01's types.
"""

from __future__ import annotations

from .csv_codec import (
    CsvImportError,
    ImportSummary,
    RowError,
    Sanitizer,
    identity_sanitizer,
)
from .engine import DEFAULT_URL, create_db_engine
from .migrations import create_all, drop_all
from .schema import metadata
from .services import (
    AvailabilityService,
    EventService,
    MasterDataService,
    SufficiencyStatus,
)

__all__ = [
    "DEFAULT_URL",
    "AvailabilityService",
    "CsvImportError",
    "EventService",
    "ImportSummary",
    "MasterDataService",
    "RowError",
    "Sanitizer",
    "SufficiencyStatus",
    "create_all",
    "create_db_engine",
    "drop_all",
    "identity_sanitizer",
    "metadata",
]
