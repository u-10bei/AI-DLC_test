"""The one behaviour shared-kernel owns.

Which declaration is in force is a question about entity identity: it depends on
nothing but the declarations themselves -- not on persistence, not on the
optimizer, not on the UI. So it lives here rather than in U-03, which would
otherwise force U-04 and U-05 to depend on the data-management unit just to
learn who is available.
"""

from __future__ import annotations

from collections.abc import Iterable

from .entities import AvailabilityDeclaration
from .exceptions import AmbiguousDeclarationError
from .identifiers import EventId, StaffId


def effective_declaration_for(
    staff_id: StaffId,
    event_id: EventId,
    history: Iterable[AvailabilityDeclaration],
) -> AvailabilityDeclaration | None:
    """Return the declaration in force for ``(staff_id, event_id)``.

    Three outcomes, and the difference between the first two is operational, not
    cosmetic:

    * ``None`` -- the staff member has **not declared**. They are not in the
      optimization. A coordinator should chase them.
    * a declaration with ``is_available=True`` -- in the optimization (FR-04.1).
    * a declaration with ``is_available=False`` -- **declared unavailable**, for
      leave, caregiving or a health accommodation. Not in the optimization, and
      not to be chased.

    Reporting only "20 short" hides the fact that 70 people simply have not
    answered yet, and that chasing them might close the gap. U-03's sufficiency
    view must therefore report three buckets, not two (handoff U01-H10).

    Raises:
        AmbiguousDeclarationError: two declarations share the latest timestamp.
            Rather than pick one arbitrarily we refuse (fail closed). U-03 must
            guarantee timestamp uniqueness on bulk import (handoff U01-H11).
    """
    matching = [
        d for d in history if d.staff_id == staff_id and d.event_id == event_id
    ]
    if not matching:
        return None

    latest = max(d.declared_at for d in matching)
    candidates = [d for d in matching if d.declared_at == latest]
    if len(candidates) > 1:
        raise AmbiguousDeclarationError(
            "two declarations share the latest declared_at",
            violated_rule="effective_declaration_for",
            staff_id=staff_id,
            event_id=event_id,
        )
    return candidates[0]


__all__ = ["effective_declaration_for"]
