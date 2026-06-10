from __future__ import annotations

from docker_dsl.context import context, rendering
from docker_dsl.core import Dockerfile
from docker_dsl.stage import Stage
from docker_dsl.state import current_stage

# Load-bearing for the docs site: without it, great-docs walks every public
# symbol, including the ~4500 generated methods in builder.pyi.
__all__ = ["Dockerfile", "Stage", "context", "current_stage", "rendering"]
