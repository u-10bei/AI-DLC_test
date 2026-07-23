"""U-04 exceptions (U04-H7). Inherit U-01's DomainError; never carry PII.

Context is a constraint ID / facility ID / department ID / staff ID only -- never
a name or residence district (SECURITY-03, BR-OPT17).
"""

from __future__ import annotations

from shared_kernel import DomainError


class ModelConstructionError(DomainError):
    """The AssignmentProblem cannot be turned into a model.

    Raised when the travel matrix is missing an entry a variable needs, or a
    parameter is inconsistent. fail closed: no partial model is solved.
    """


class PinnedAssignmentInfeasibleError(DomainError):
    """A pinned assignment violates a hard constraint (FR-06.4, BR-OPT12).

    Raised BEFORE solving. The coordinator must unpin and rerun. The context
    names the violated constraint and the facility/department only.
    """


__all__ = ["ModelConstructionError", "PinnedAssignmentInfeasibleError"]
