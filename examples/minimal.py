from __future__ import annotations

from docker_dsl import Stage
from docker_dsl import context as ctx

ctx.register("tag", str)

with Stage("ubuntu:24.04") as s:
    s.arg("APP_TAG", ctx.tag or "latest", env=True)
    s.workdir("/app")
    with s.run() as r:
        r.echo("hello from docker-dsl") > "/app/greeting.txt"  # pyright: ignore[reportUnusedExpression]
    s.cmd("cat", "/app/greeting.txt")
