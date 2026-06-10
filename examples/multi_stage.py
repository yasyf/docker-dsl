from __future__ import annotations

from docker_dsl import Stage
from docker_dsl import context as ctx

ctx.register("release", bool)

with Stage("golang:1.23") as builder:
    builder.workdir("/src")
    builder.copy(".", ".")
    with builder.cache("/root/.cache/go-build"), builder.run() as r:
        r.go("build", "-o", "/bin/server", "./cmd/server")

with Stage("gcr.io/distroless/base-debian12", name="release") as release:
    release.copy("/bin/server", stage=builder)
    release.env({"GO_ENV": "production" if ctx.release else "staging"})
    release.entrypoint("/bin/server")
