"""Hypothesis profiles (PBT-08).

CI uses a *random* seed on every run. A fixed seed would make the run
deterministic at the cost of exercising the same inputs forever, which defeats
the purpose of property-based testing. Reproducibility comes from Hypothesis
printing the seed on failure, not from freezing it:

    pytest --hypothesis-seed=<seed printed by the failing run>

Shrinking is never disabled.
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, Verbosity, settings

settings.register_profile(
    "dev",
    max_examples=100,
    print_blob=True,
)

settings.register_profile(
    "ci",
    max_examples=500,
    print_blob=True,
    # `derandomize` stays False: a new seed each run, seed printed on failure.
    derandomize=False,
    suppress_health_check=[HealthCheck.too_slow],
    verbosity=Verbosity.normal,
)

settings.load_profile("ci" if os.environ.get("CI") else "dev")
