from __future__ import annotations

from docker_dsl.stage import Stage
from docker_dsl.state import StageGraph


def test_attribute_dispatch_emits_shell(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.git("clone", "repo.git")
        r.make("-C", "build", "-j$(nproc)")
    rendered = s.render()
    assert "RUN git clone repo.git \\\n  && make -C build -j$(nproc)" in rendered


def test_raw_call_fallback(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r("(cd build/faiss/python && python setup.py install)")
    assert "(cd build/faiss/python && python setup.py install)" in s.render()


def test_echo_append_redirect(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.echo("pillow>=11.1.0") >> "/root/overrides.txt"  # pyright: ignore[reportUnusedExpression]
    assert 'echo "pillow>=11.1.0" >> /root/overrides.txt' in s.render()


def test_echo_truncate_redirect(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.echo("numpy<3.0.0") > "/etc/pip/constraint.txt"  # pyright: ignore[reportUnusedExpression]
    assert 'echo "numpy<3.0.0" > /etc/pip/constraint.txt' in s.render()


def test_per_command_env(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.make("-j$(nproc)", env={"CC": "sccache gcc"})
    assert 'CC="sccache gcc" make -j$(nproc)' in s.render()


def test_cd_as_statement_emits_once(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.cd("faiss")
        r.make("-j", "4")
    rendered = s.render()
    assert "cd faiss \\\n  && make -j 4" in rendered


def test_cd_as_context_manager_emits_cd_and_restores(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        with r.cd("build"):
            r.make("-j$(nproc)")
            r.make("install")
    rendered = s.render()
    assert "cd build \\\n  && make -j$(nproc)" in rendered
    assert "&& make install" in rendered
    assert "cd -" in rendered


def test_run_picks_up_cache_mount(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        with s.cache("/root/.cache/uv"), s.run() as r:
            r.uv("pip", "install", "-U", "torch")
    rendered = s.render()
    assert "--mount=type=cache,target=/root/.cache/uv,sharing=shared" in rendered
    assert "uv pip install -U torch" in rendered


def test_install_shortcut(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.install("https://github.com/owner/tool/releases/download/1.0/tool-linux.tar.gz")
    rendered = s.render()
    assert (
        "curl -fL https://github.com/owner/tool/releases/download/1.0/tool-linux.tar.gz"
        " | tar xz -C /usr/local/bin --strip-components=1"
    ) in rendered


def test_curl_bash_shortcut(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.curl_bash("https://sh.rustup.rs", args=("-y",))
    assert "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- -y" in s.render()


def test_positional_run_with_env_prefix(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        s.run("make", "install", env={"CC": "gcc"})
    assert 'RUN CC="gcc" make install' in s.render()


def test_kwargs_render_as_flags(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.git("clone", "url", depth="1", verbose=True)
    assert "git clone url --depth 1 --verbose" in s.render()


def test_kwargs_false_omitted(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.git("status", verbose=False, short=True)
    rendered = s.render()
    assert "--short" in rendered
    assert "--verbose" not in rendered


def test_kwargs_underscore_to_hyphen(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.git("log", no_pager=True)
    assert "--no-pager" in s.render()


def test_kwargs_with_env(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.make("all", jobs="4", env={"CC": "gcc"})
    rendered = s.render()
    assert 'CC="gcc" make all --jobs 4' in rendered
