from __future__ import annotations

from docker_dsl.apt import AptMixin
from docker_dsl.builder import RunBuilder
from docker_dsl.context import BuildContext, context, rendering
from docker_dsl.core import Dockerfile
from docker_dsl.run import CdScope, CmdInvoker, RedirectableCmd
from docker_dsl.stage import EnvScope, MountScope, Stage
from docker_dsl.state import current_stage

# Load-bearing for the docs site: without it, great-docs walks every public
# symbol, including the ~4500 generated methods in builder.pyi.
__all__ = ["Dockerfile", "Stage", "context", "current_stage", "rendering"]

# Not exported, but imported here so the curated great-docs reference can resolve
# them as top-level names (it matches `contents` against docker_dsl's members).
# RunBuilder is documented with an explicit member list — griffe merges
# builder.pyi, so a bare reference would pull in thousands of generated stubs.
__reference_only__ = [AptMixin, BuildContext, CdScope, CmdInvoker, EnvScope, MountScope, RedirectableCmd, RunBuilder]
