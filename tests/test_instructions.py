from __future__ import annotations

from docker_dsl.instructions import Arg, Cmd, Copy, Entrypoint, Env, Run, Workdir
from docker_dsl.mounts import CacheMount, SecretMount


class TestInstructions:
    def test_arg_renders(self) -> None:
        assert Arg(name="FOO", value="bar").render() == "ARG FOO=bar"

    def test_env_single(self) -> None:
        assert Env(pairs={"FOO": "bar"}).render() == "ENV FOO=bar"

    def test_env_multiple(self) -> None:
        assert Env(pairs={"A": "1", "B": "2"}).render() == "ENV A=1\nENV B=2"

    def test_workdir(self) -> None:
        assert Workdir(path="/root").render() == "WORKDIR /root"

    def test_copy_simple(self) -> None:
        assert Copy(src="src.txt", dst="dst.txt").render() == "COPY src.txt dst.txt"

    def test_copy_from_image_with_link(self) -> None:
        copy = Copy(src="/uv", dst="/usr/local/bin/uv", from_="ghcr.io/astral-sh/uv:latest", link=True)
        assert copy.render() == "COPY --from=ghcr.io/astral-sh/uv:latest --link /uv /usr/local/bin/uv"

    def test_run_no_mounts(self) -> None:
        assert Run(script="echo hello").render() == "RUN echo hello"

    def test_run_with_cache_mount(self) -> None:
        run = Run(
            script="apt-get update",
            mounts=(CacheMount(target="/var/cache/apt", sharing="locked"),),
        )
        assert run.render() == "RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \\\n  apt-get update"

    def test_run_with_multiple_mounts(self) -> None:
        run = Run(
            script="uv sync",
            mounts=(
                CacheMount(target="/root/.cache/uv"),
                SecretMount(id="aws", target="/root/.aws/credentials"),
            ),
        )
        expected = (
            "RUN --mount=type=cache,target=/root/.cache/uv,sharing=shared "
            "--mount=type=secret,id=aws,target=/root/.aws/credentials \\\n  uv sync"
        )
        assert run.render() == expected

    def test_entrypoint_json(self) -> None:
        assert Entrypoint(args=("python", "-m", "bioqa")).render() == 'ENTRYPOINT ["python", "-m", "bioqa"]'

    def test_cmd_json(self) -> None:
        assert Cmd(args=("python",)).render() == 'CMD ["python"]'
