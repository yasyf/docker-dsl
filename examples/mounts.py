from __future__ import annotations

from docker_dsl import Stage
from docker_dsl import context as ctx

ctx.register("private", bool)

with Stage("python:3.13-slim") as s:
    s.workdir("/app")

    with s.bind(source=".", target="/app"), s.cache("/root/.cache/pip"), s.run() as r:
        r.pip("install", "--requirement", "requirements.txt")

    if ctx.private:
        with s.secret("pypi", target="/root/.netrc"), s.cache("/root/.cache/pip"), s.run() as r:
            r.pip("install", "--requirement", "requirements-private.txt")
