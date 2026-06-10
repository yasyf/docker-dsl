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
