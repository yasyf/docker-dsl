from __future__ import annotations

import importlib

from inline_snapshot import snapshot

from docker_dsl import Dockerfile


class TestExampleSnapshots:
    def test_minimal_example(self) -> None:
        assert Dockerfile(importlib.import_module("examples.minimal")).render(tag="v1.0.0") == snapshot("""\
# syntax=docker/dockerfile:1
FROM ubuntu:24.04 AS base
ARG APP_TAG=v1.0.0
ENV APP_TAG=${APP_TAG}
WORKDIR /app
RUN echo "hello from docker-dsl" > /app/greeting.txt
CMD ["cat", "/app/greeting.txt"]
""")

    def test_multi_stage_release(self) -> None:
        assert Dockerfile(importlib.import_module("examples.multi_stage")).render(release=True) == snapshot("""\
# syntax=docker/dockerfile:1
FROM golang:1.23 AS base
WORKDIR /src
COPY . .
RUN --mount=type=cache,target=/root/.cache/go-build,sharing=shared \\
  go build -o /bin/server ./cmd/server

FROM gcr.io/distroless/base-debian12 AS release
COPY --from=base --link /bin/server /bin/server
ENV GO_ENV=production
ENTRYPOINT ["/bin/server"]
""")

    def test_multi_stage_staging(self) -> None:
        assert Dockerfile(importlib.import_module("examples.multi_stage")).render(release=False) == snapshot("""\
# syntax=docker/dockerfile:1
FROM golang:1.23 AS base
WORKDIR /src
COPY . .
RUN --mount=type=cache,target=/root/.cache/go-build,sharing=shared \\
  go build -o /bin/server ./cmd/server

FROM gcr.io/distroless/base-debian12 AS release
COPY --from=base --link /bin/server /bin/server
ENV GO_ENV=staging
ENTRYPOINT ["/bin/server"]
""")

    def test_apt_smart_with_intel(self) -> None:
        assert Dockerfile(importlib.import_module("examples.apt_smart")).render(with_intel=True) == snapshot("""\
# syntax=docker/dockerfile:1
FROM ubuntu:24.04 AS base
WORKDIR /root
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked \\
  apt-get update -y \\
  && apt-get install -y --no-install-recommends software-properties-common \\
  && add-apt-repository ppa:apt-fast/stable -y \\
  && apt-get update -y \\
  && apt-fast install -y --no-install-recommends apt-fast curl wget git \\
  && wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null \\
  && echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneapi-archive-keyring.list \\
  && apt-get update -y \\
  && apt-fast install -y --no-install-recommends intel-oneapi-mkl-devel \\
  && rm -rf /tmp/*
CMD ["bash"]
""")

    def test_apt_smart_without_intel(self) -> None:
        assert Dockerfile(importlib.import_module("examples.apt_smart")).render(with_intel=False) == snapshot("""\
# syntax=docker/dockerfile:1
FROM ubuntu:24.04 AS base
WORKDIR /root
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked --mount=type=cache,target=/var/lib/apt,sharing=locked \\
  apt-get update -y \\
  && apt-get install -y --no-install-recommends software-properties-common \\
  && add-apt-repository ppa:apt-fast/stable -y \\
  && apt-get update -y \\
  && apt-fast install -y --no-install-recommends apt-fast curl wget git \\
  && rm -rf /tmp/*
CMD ["bash"]
""")

    def test_run_builder_example(self) -> None:
        assert Dockerfile(importlib.import_module("examples.run_builder")).render(ref="v2.0.0") == snapshot("""\
# syntax=docker/dockerfile:1
FROM ubuntu:24.04 AS base
WORKDIR /src
RUN git clone https://github.com/example/widget.git . \\
  && git checkout v2.0.0 \\
  && cd build \\
  && cmake .. --build-type Release \\
  && make -j$(nproc) \\
  && make install \\
  && cd - \\
  && echo "widget built" >> /var/log/build.txt \\
  && echo "build complete" > /src/STATUS \\
  && rm -rf /src/build
""")

    def test_mounts_private(self) -> None:
        assert Dockerfile(importlib.import_module("examples.mounts")).render(private=True) == snapshot("""\
# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base
WORKDIR /app
RUN --mount=type=bind,source=.,target=/app --mount=type=cache,target=/root/.cache/pip,sharing=shared \\
  pip install --requirement requirements.txt
RUN --mount=type=secret,id=pypi,target=/root/.netrc --mount=type=cache,target=/root/.cache/pip,sharing=shared \\
  pip install --requirement requirements-private.txt
""")

    def test_mounts_public(self) -> None:
        assert Dockerfile(importlib.import_module("examples.mounts")).render(private=False) == snapshot("""\
# syntax=docker/dockerfile:1
FROM python:3.13-slim AS base
WORKDIR /app
RUN --mount=type=bind,source=.,target=/app --mount=type=cache,target=/root/.cache/pip,sharing=shared \\
  pip install --requirement requirements.txt
""")

    def test_helpers_dev(self) -> None:
        assert Dockerfile(importlib.import_module("examples.helpers")).render(dev=True) == snapshot("""\
# syntax=docker/dockerfile:1
FROM rust:1.83-slim AS base
WORKDIR /app
COPY . .
RUN --mount=type=cache,target=/root/.cargo/registry,sharing=shared --mount=type=cache,target=/app/target,sharing=shared \\
  cargo build --release \\
  && cargo test
""")

    def test_helpers_release(self) -> None:
        assert Dockerfile(importlib.import_module("examples.helpers")).render(dev=False) == snapshot("""\
# syntax=docker/dockerfile:1
FROM rust:1.83-slim AS base
WORKDIR /app
COPY . .
RUN --mount=type=cache,target=/root/.cargo/registry,sharing=shared --mount=type=cache,target=/app/target,sharing=shared \\
  cargo build --release
""")
