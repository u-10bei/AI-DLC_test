"""W-2: the ASGI entry point deployment actually starts.

    uvicorn api_orchestration.asgi:app --host 127.0.0.1 --port 8000

`build_application` takes a config argument, so it cannot be used as a uvicorn
factory directly (`--factory` calls it with no arguments and raises TypeError).
This module supplies the missing piece: read the environment, build the app once
at import.

Bind to 127.0.0.1 in deployment. The reverse proxy is the only thing that should
reach this process (deployment-plan.md §8).
"""

from __future__ import annotations

from fastapi import FastAPI

from .composition import build_application
from .settings import load_config_from_env


def create_app() -> FastAPI:
    """Factory form: `uvicorn api_orchestration.asgi:create_app --factory`."""
    return build_application(load_config_from_env())


#: Module-level app: `uvicorn api_orchestration.asgi:app`.
app = create_app()

__all__ = ["app", "create_app"]
