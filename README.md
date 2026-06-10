# docker-dsl

[![PyPI](https://img.shields.io/pypi/v/docker-dsl.svg)](https://pypi.org/project/docker-dsl/)
[![Python](https://img.shields.io/pypi/pyversions/docker-dsl.svg)](https://pypi.org/project/docker-dsl/)
[![Docs](https://img.shields.io/github/actions/workflow/status/yasyf/docker-dsl/docs.yml?branch=main&label=docs)](https://yasyf.github.io/docker-dsl/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/yasyf/docker-dsl/blob/main/LICENSE)

An imperative, context-manager-based Python DSL for authoring multi-stage
Dockerfiles. Write builds the way you write Python — `with` blocks,
conditionals, comprehensions, and reusable helpers — and render one recipe
into many Dockerfile variants.

## Install

No install needed — run everything through [uvx](https://docs.astral.sh/uv/):

```bash
uvx docker-dsl --help
```

`uvx` fetches docker-dsl into a throwaway environment and runs it. To add it
to a project instead:

```bash
uv add docker-dsl
```

## Quickstart

Write a recipe module — for example `my_recipe.py`:

```python
from docker_dsl import Stage, context as ctx

ctx.register("gpu", bool)

with Stage("nvcr.io/nvidia/pytorch:26.03-py3" if ctx.gpu else "ubuntu:24.04") as s:
    s.arg("PYTHON_VERSION", "3.13", env=True)
    s.path("/root/.local/bin")
    s.workdir("/root")

    with s.cache("/var/cache/apt", lock=True), s.cache("/var/lib/apt", lock=True):
        s.apt_install("software-properties-common")
        s.add_apt_ppa("ppa:apt-fast/stable")
        s.apt_install("curl", "git", "wget", fast=True)

    with s.cache("/root/.cache/uv"), s.run() as r:
        r.uv("pip", "install", "-U", "numpy", "pandas")
```

Render it:

```bash
docker-dsl my_recipe --gpu=true --out Dockerfile
```

Or from Python:

```python
from docker_dsl import Dockerfile
import my_recipe

with Dockerfile(my_recipe) as d:
    gpu_text = d.render(gpu=True)
    cpu_text = d.render(gpu=False)
```

## What problems does this solve?

- **`RUN` chains glued with `&&` are fragile.** The run builder accumulates
  commands in Python — `r.git("clone", url)`, `r.make("-j$(nproc)")` — and
  emits one correct `RUN` instruction, with `cd` scoping restored
  automatically.
- **Variants drift apart.** A GPU and a CPU image usually means two copied
  Dockerfiles diverging over time. Here one recipe takes `--gpu=true|false`
  and renders both from the same code path.
- **No abstraction in raw Dockerfiles.** Recipes are plain Python modules:
  factor repeated setup into context managers and helper functions, loop and
  branch where the build genuinely varies.
- **BuildKit mounts are easy to get wrong.** `s.cache(...)`, `s.secret(...)`,
  and `s.bind(...)` are scoped context managers — every `RUN` inside the
  scope picks up the active mounts, and nothing leaks outside it.

## Core concepts

### Two-pass execution

When a recipe is first imported, docker-dsl is in **discovery pass**: the
module body runs but every DSL call is a no-op. `ctx.register(...)` is used
in this pass to populate a schema of config fields.

When `Dockerfile(module).render(**config)` is called, the DSL enters the
**render pass**: it validates `config` against the registered schema, sets
up ContextVars, and re-executes the module. Every `with Stage(...) as s:`
and `s.<method>(...)` now accumulates into the active graph. `ctx.gpu`
returns the validated config value.

This design lets you write the recipe as plain top-level Python — no magic,
no decorators, no entrypoint functions.

### Config fields

```python
ctx.register("gpu", bool)
ctx.register("tag", str)
```

Every registered field is required at render time. Pydantic validates the
values before the render pass runs, so type errors surface with clear
messages.

### Stages

```python
with Stage("ubuntu:24.04") as base:  # FROM ubuntu:24.04 AS base
    base.workdir("/root")

with base.stage() as builder:         # FROM base AS builder
    builder.run("make", "all")

with base.stage() as release:         # FROM base AS release
    release.copy("/out/bin", stage=builder)
```

Child stage names are inferred from the `as <name>` target via the `executing`
library. Pass `name="..."` to override.

### Run builder

`s.run()` as a context manager accumulates shell commands into a single
`RUN` instruction:

```python
with s.run() as r:
    r.git("clone", "https://example.com/repo.git")
    with r.cd("repo"):
        r.make("-j$(nproc)")
        r.make("install")
    r("(cd subdir && python setup.py install)")  # raw fallback
```

Command methods dispatch via `__getattr__` — any attribute name becomes the
shell binary. `r.cd(path)` works both as a statement (subsequent commands
stay in that directory) and as a context manager (scope-restores on exit via
`cd -`).

Echo redirects compose naturally:

```python
with s.run() as r:
    r.echo("pillow>=11.1.0") >> "/root/overrides.txt"        # append
    r.echo("numpy<3.0.0,>=1.26.4") > "/etc/pip/constraint.txt"  # truncate
```

### Mounts

`s.cache(target, *, lock=False)`, `s.secret(id, *, target=...)`,
`s.bind(source=..., target=...)` return context managers that push a mount
onto the stage's stack. Any `RUN` emitted inside the scope picks up all
active mounts.

```python
with s.cache("/root/.cache/uv"), s.secret("aws", target="/root/.aws/credentials"):
    with s.run() as r:
        r.uv("pip", "install", "-U", "torch")
```

### Smart apt

`r.apt_install(...)`, `r.add_apt_ppa(...)`, and `r.add_apt_repo(...)` are
methods on `RunBuilder` that write directly to the command list.
`apt-get update -y` is inserted automatically before the first install and
again after any dirty-marking operation (new PPA, new repo). Arbitrary
commands (cleanup, setup scripts) are just `r(...)` calls.

```python
with s.cache("/var/cache/apt", lock=True), s.cache("/var/lib/apt", lock=True), s.run() as r:
    r.apt_install("software-properties-common")
    r.add_apt_ppa("ppa:apt-fast/stable")
    r.apt_install("apt-fast", "curl", "wget", fast=True)
    r("rm -rf /tmp/*")
```

### Reusable helpers

Recipes can compose their own context managers:

```python
from contextlib import contextmanager

@contextmanager
def sccache(stage):
    with stage.secret("aws", target="/root/.aws/credentials"):
        yield

with Stage("ubuntu:24.04") as s:
    with sccache(s), s.run() as r:
        r.uv("pip", "install", "-U", "torch")
```

## CLI

```
docker-dsl <module.path> [--<field>=<value> ...] [--out PATH]
```

(`python -m docker_dsl` is equivalent.) Arguments are built dynamically from
the fields registered by the recipe. A `--out` argument is always available;
if omitted, the rendered Dockerfile is written to stdout. Bool fields accept
`true`/`false`/`1`/`0`/`yes`/`no`.

Validation errors surface with structured Pydantic messages naming the
missing or wrong-typed fields.

## Examples

See [`examples/`](examples) for self-contained recipes:

- `minimal.py` — the shortest possible recipe
- `multi_stage.py` — builder + release pattern with `COPY --from`
- `apt_smart.py` — demonstrating the apt buffer flush rules

Run them via the CLI:

```bash
docker-dsl examples.minimal --tag=dev --out Dockerfile.min
docker-dsl examples.multi_stage --release=true --out Dockerfile.ms
```

## Editor completions

`RunBuilder` uses `__getattr__` for dynamic shell-command dispatch, which
means editors have no static information about available commands. To fix
this, docker-dsl ships a generated `builder.pyi` type stub that declares
every system command as a method on `RunBuilder`.

Commands with bash programmable completions get `@overload` stubs with
`Literal` subcommands and typed flag kwargs. Commands without completions
get their flags extracted from man pages. All others get a plain
`*args: str, **kwargs: str | bool` catch-all.

Regenerate after installing new tools:

```bash
python -m docker_dsl.stubgen
```

The generator:
1. Runs `bash -lic 'compgen -c'` to enumerate commands
2. Invokes bash completion functions to extract subcommands + flags
3. Falls back to `man <cmd> | col -b` (parallelized across CPU cores) for commands without bash completions
4. Parses `builder.py` via `ast` to preserve real method signatures
5. Writes `builder.pyi` with `@generated` header

Flags become keyword arguments with underscore-to-hyphen conversion:
`r.git("clone", url, depth="1", verbose=True)` → `git clone <url> --depth 1 --verbose`.

## Docs

[Read the docs](https://yasyf.github.io/docker-dsl/) for the full guide and API reference.
