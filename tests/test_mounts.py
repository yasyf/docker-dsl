from __future__ import annotations

import pytest

from docker_dsl.mounts import BindMount, CacheMount, SecretMount


class TestMountRender:
    def test_cache_mount_default_sharing_is_shared(self) -> None:
        assert (
            CacheMount(target="/root/.cache/uv").render() == "--mount=type=cache,target=/root/.cache/uv,sharing=shared"
        )

    @pytest.mark.parametrize(
        ("sharing", "expected"),
        [
            ("shared", "--mount=type=cache,target=/root/.cache/uv,sharing=shared"),
            ("locked", "--mount=type=cache,target=/root/.cache/uv,sharing=locked"),
            ("private", "--mount=type=cache,target=/root/.cache/uv,sharing=private"),
        ],
        ids=["shared", "locked", "private"],
    )
    def test_cache_mount_all_sharing_modes(self, sharing: str, expected: str) -> None:
        assert CacheMount(target="/root/.cache/uv", sharing=sharing).render() == expected  # type: ignore[arg-type]

    def test_secret_mount_render(self) -> None:
        assert SecretMount(id="aws", target="/root/.aws/credentials").render() == (
            "--mount=type=secret,id=aws,target=/root/.aws/credentials"
        )

    def test_bind_mount_render(self) -> None:
        assert BindMount(source="uv.lock", target="uv.lock").render() == (
            "--mount=type=bind,source=uv.lock,target=uv.lock"
        )
