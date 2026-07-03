# ![docker-dsl](https://github.com/yasyf/docker-dsl/raw/main/docs/assets/readme-banner.webp)

**Delete your Dockerfile.gpu.** docker-dsl renders both GPU and CPU Dockerfiles from one Python recipe, where a flag flips the variant and `run()` collapses each chain into a single RUN.

[![CI](https://github.com/yasyf/docker-dsl/actions/workflows/ci.yml/badge.svg)](https://github.com/yasyf/docker-dsl/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/docker-dsl)](https://pypi.org/project/docker-dsl/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/yasyf/docker-dsl/blob/main/LICENSE)

## Get started

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

<img src="https://github.com/yasyf/docker-dsl/raw/main/docs/assets/demo.png" alt="Terminal running 'uvx docker-dsl minimal --tag=v1.0.0 --out Dockerfile' — cat Dockerfile shows the rendered Dockerfile" width="700">

Driving with an agent? Paste this:

```text
Install docker-dsl in this repo with `uv add docker-dsl`.
Port my existing Dockerfile to a recipe module: one Stage per build stage, run() blocks for RUN chains, cache mounts on the apt/pip steps.
Render it with `uvx docker-dsl <module.path> --out Dockerfile` and diff against the original.
Docs: https://yasyf.github.io/docker-dsl/
```

---

## Use cases

### Ship GPU and CPU images from one recipe

Your `Dockerfile.gpu` started life as a copy of your `Dockerfile`, and the two have drifted ever since. Register a bool and branch in Python instead:

```python
ctx.register("gpu", bool)

base = "nvidia/cuda:12.4.1-runtime-ubuntu22.04" if ctx.gpu else "ubuntu:24.04"
```

```bash
uvx docker-dsl train --gpu=true --out Dockerfile.gpu
uvx docker-dsl train --gpu=false --out Dockerfile
```

Both files render from the same recipe: the GPU variant gets the CUDA base image and `pip install torch`, the CPU variant gets `ubuntu:24.04` and the CPU wheel index, and the diff between them is a Python `if` you can read.

### Turn a 10-command build into one correct RUN

A long `RUN` chain means a `&&` and a trailing backslash on every line, and a `cd` that silently leaks into the rest of the chain. Write the commands as method calls — `r.cd()` scopes the directory change:

```bash
uvx docker-dsl run_builder --ref=v2.0.0
```

<details>
<summary>The nine calls in <code>run_builder.py</code> emit one RUN</summary>

```dockerfile
RUN git clone https://github.com/example/widget.git . \
  && git checkout v2.0.0 \
  && cd build \
  && cmake .. --build-type Release \
  && make -j$(nproc) \
  && make install \
  && cd - \
  && echo "widget built" >> /var/log/build.txt \
  && echo "build complete" > /src/STATUS \
  && rm -rf /src/build
```

</details>

### Keep secrets and caches scoped to the RUNs that need them

A BuildKit `--mount` flag lives on one `RUN` instruction, so refactoring the chain means re-plumbing every mount by hand. In a recipe, `cache`, `secret`, and `bind` are context managers — every `run()` inside the block picks them up, and nothing leaks past it:

```bash
uvx docker-dsl mounts --private=true
```

```dockerfile
RUN --mount=type=secret,id=pypi,target=/root/.netrc --mount=type=cache,target=/root/.cache/pip,sharing=shared \
  pip install --requirement requirements-private.txt
```

Render with `--private=false` and the secret-mounted `RUN` disappears entirely — the `.netrc` never touches the public variant.

## More in the docs

- **Multi-stage builds** — build in one stage, `copy(..., stage=builder)` the artifact into a slim final image — [guide](https://yasyf.github.io/docker-dsl/docs/guide/multi-stage-builds.html)
- **Smart apt** — `apt_install` inserts `apt-get update` exactly where package lists change, PPAs and third-party repos included — [guide](https://yasyf.github.io/docker-dsl/docs/guide/smart-apt.html)
- **The run builder** — any shell command as a method call, with redirects and directory scoping — [guide](https://yasyf.github.io/docker-dsl/docs/guide/run-builder.html)
- **Reusable helpers** — factor repeated setup into plain Python context managers — [guide](https://yasyf.github.io/docker-dsl/docs/guide/reusable-helpers.html)
- **Render from the CLI or from Python** — every recipe gets typed `--flag`s for free — [guide](https://yasyf.github.io/docker-dsl/docs/guide/render-from-the-cli.html)

Status: alpha — the DSL surface may still shift before 1.0.

Read the [docs](https://yasyf.github.io/docker-dsl/) for the full guide. Licensed under [MIT](LICENSE).
