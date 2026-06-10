from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from docker_dsl import Stage
from docker_dsl import context as ctx
from docker_dsl.stage import Stage as StageType

ctx.register("dev", bool)


@contextmanager
def cargo(stage: StageType) -> Iterator[None]:
    with stage.cache("/root/.cargo/registry"), stage.cache("/app/target"):
        yield


with Stage("rust:1.83-slim") as s:
    s.workdir("/app")
    s.copy(".", ".")

    with cargo(s), s.run() as r:
        r.cargo("build", "--release")
        if ctx.dev:
            r.cargo("test")
