from __future__ import annotations

from docker_dsl.stage import Stage
from docker_dsl.state import StageGraph


def test_inactive_stage_methods_noop() -> None:
    s = Stage("ubuntu:24.04")
    s.arg("X", "y")
    s.workdir("/x")
    assert s.instructions == []


def test_inactive_stage_run_ctxmgr_produces_nothing() -> None:
    s = Stage("ubuntu:24.04")
    with s.run() as r:
        r.echo("hi") >> "/x"  # pyright: ignore[reportUnusedExpression]
        r.git("clone", "repo")
    assert s.instructions == []


def test_active_stage_accumulates_arg_workdir(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        s.arg("PY", "3.13", env=True)
        s.workdir("/root")
    rendered = s.render()
    assert "FROM ubuntu:24.04 AS base" in rendered
    assert "ARG PY=3.13" in rendered
    assert "ENV PY=${PY}" in rendered
    assert "WORKDIR /root" in rendered


def test_env_filters_none_values(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        s.env({"SET": "yes", "UNSET": None})
    rendered = s.render()
    assert "ENV SET=yes" in rendered
    assert "UNSET" not in rendered


def test_copy_from_image_sets_link(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        s.copy("/uv", "/usr/local/bin/uv", image="ghcr.io/astral-sh/uv:latest")
    assert "COPY --from=ghcr.io/astral-sh/uv:latest --link /uv /usr/local/bin/uv" in s.render()


def test_copy_from_stage(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as base:
        base.workdir("/")
    with base.stage(name="other") as other:
        other.run("echo", "x")
    with base.stage(name="release") as release:
        release.copy("/gs", stage=other)
    assert "COPY --from=other --link /gs /gs" in release.render()
    assert base in graph.stages
    assert other in graph.stages
    assert release in graph.stages


def test_cmd_and_entrypoint_json_arrays(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        s.entrypoint("/usr/bin/entrypoint.sh")
        s.cmd("python")
    rendered = s.render()
    assert 'ENTRYPOINT ["/usr/bin/entrypoint.sh"]' in rendered
    assert 'CMD ["python"]' in rendered


def test_scoped_env_exports_for_run(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        with s.env({"CC": "gcc", "CXX": "g++"}), s.run() as r:
            r.make("-j4")
            r.make("install")
    rendered = s.render()
    assert "ENV CC" not in rendered
    assert 'RUN export CC="gcc" CXX="g++" \\\n  && make -j4 \\\n  && make install' in rendered


def test_env_statement_emits_global_env(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        s.env({"KEY": "val"})
    rendered = s.render()
    assert "ENV KEY=val" in rendered


def test_scoped_env_nested_merges(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        with s.env({"A": "1"}):
            with s.env({"B": "2"}), s.run() as r:
                r.echo("hi") > "/tmp/x"  # pyright: ignore[reportUnusedExpression]
    rendered = s.render()
    assert 'RUN export A="1" B="2" \\\n  && echo "hi" > /tmp/x' in rendered


def test_scoped_env_per_command_overrides(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        with s.env({"CC": "gcc"}), s.run() as r:
            r.make("-j4", env={"CC": "clang"})
    rendered = s.render()
    assert 'CC="clang" make -j4' in rendered


def test_scoped_env_with_direct_run(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        with s.env({"CC": "gcc"}):
            s.run("make", "install")
    rendered = s.render()
    assert 'RUN export CC="gcc" \\\n  && make install' in rendered
