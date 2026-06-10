from __future__ import annotations

from docker_dsl.stage import Stage


def test_discovery_skips_stage_methods() -> None:
    s = Stage("ubuntu:24.04")
    assert not s.active
    s.arg("A", "1")
    s.workdir("/x")
    s.entrypoint("sh")
    s.cmd("python")
    s.copy("/a", "/b")
    assert s.instructions == []


def test_inactive_run_ctxmgr_absorbs_all_calls() -> None:
    s = Stage("ubuntu:24.04")
    with s.run() as r:
        r.anything("arg")
        r.echo("x") >> "/tmp/y"  # pyright: ignore[reportUnusedExpression]
        r.git("clone", "repo")
    assert s.instructions == []


def test_inactive_mount_ctxmgrs_absorb() -> None:
    s = Stage("ubuntu:24.04")
    with s.cache("/var"), s.secret("aws", target="/x"), s.bind(source="a", target="b"):
        pass
    assert s.instructions == []


def test_inactive_env_ctxmgr_absorbs() -> None:
    s = Stage("ubuntu:24.04")
    with s.env({"KEY": "val"}):
        pass
    assert s.instructions == []
