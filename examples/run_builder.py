from __future__ import annotations

from docker_dsl import Stage
from docker_dsl import context as ctx

ctx.register("ref", str)

with Stage("ubuntu:24.04") as s:
    s.workdir("/src")

    with s.run() as r:
        r.git("clone", "https://github.com/example/widget.git", ".")
        r.git("checkout", ctx.ref or "main")

        with r.cd("build"):
            r.cmake("..", build_type="Release")
            r.make("-j$(nproc)")
            r.make("install")

        r.echo("widget built") >> "/var/log/build.txt"  # pyright: ignore[reportUnusedExpression]
        r.echo("build complete") > "/src/STATUS"  # pyright: ignore[reportUnusedExpression]
        r("rm -rf /src/build")
