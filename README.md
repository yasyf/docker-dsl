# docker-dsl

![docker-dsl banner](https://github.com/yasyf/docker-dsl/raw/main/docs/assets/readme-banner.webp)

[![PyPI](https://img.shields.io/pypi/v/docker-dsl.svg)](https://pypi.org/project/docker-dsl/)
[![Python](https://img.shields.io/pypi/pyversions/docker-dsl.svg)](https://pypi.org/project/docker-dsl/)
[![Docs](https://img.shields.io/github/actions/workflow/status/yasyf/docker-dsl/docs.yml?branch=main&label=docs)](https://yasyf.github.io/docker-dsl/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/yasyf/docker-dsl/blob/main/LICENSE)

An imperative, context-manager-based Python DSL for authoring multi-stage
Dockerfiles. Write builds with `with` blocks, conditionals, comprehensions, and
reusable helpers, then render one recipe into many Dockerfile variants.

## Install

Run it through [uvx](https://docs.astral.sh/uv/), no install needed:

```bash
uvx docker-dsl --help
```

To add it to a project:

```bash
uv add docker-dsl
```

## Quickstart

Write a recipe module, `minimal.py`:

```python
from docker_dsl import Stage
from docker_dsl import context as ctx

ctx.register("tag", str)

with Stage("ubuntu:24.04") as s:
    s.arg("APP_TAG", ctx.tag or "latest", env=True)
    s.workdir("/app")
    with s.run() as r:
        r.echo("hello from docker-dsl") > "/app/greeting.txt"
    s.cmd("cat", "/app/greeting.txt")
```

Render it:

```bash
uvx docker-dsl minimal --tag=v1.0.0 --out Dockerfile
```

`Dockerfile` now holds:

```dockerfile
# syntax=docker/dockerfile:1
FROM ubuntu:24.04 AS base
ARG APP_TAG=v1.0.0
ENV APP_TAG=${APP_TAG}
WORKDIR /app
RUN echo "hello from docker-dsl" > /app/greeting.txt
CMD ["cat", "/app/greeting.txt"]
```

Change `--tag` and render again for a different Dockerfile from the same recipe.

## Why

- **`RUN` chains glued with `&&` are fragile.** The run builder accumulates
  commands in Python and emits one correct `RUN`, with `cd` scoping restored for
  you.
- **Variants drift apart.** One recipe takes `--gpu=true|false` and renders both
  a GPU and a CPU image from the same code path, instead of two Dockerfiles that
  diverge over time.
- **BuildKit mounts are easy to get wrong.** `cache`, `secret`, and `bind` are
  scoped context managers, so every `RUN` inside the block picks them up and
  nothing leaks out.

## Docs

The [documentation](https://yasyf.github.io/docker-dsl/) has a
[tutorial](https://yasyf.github.io/docker-dsl/getting-started/), task-focused
[guides](https://yasyf.github.io/docker-dsl/guide/) (multi-stage builds, mounts,
smart apt, the run builder, reusable helpers, and the CLI), and the full API
[reference](https://yasyf.github.io/docker-dsl/reference/).

## License

This project is licensed under the MIT License; see [LICENSE](LICENSE).
