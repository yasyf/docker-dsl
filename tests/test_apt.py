from __future__ import annotations

from docker_dsl.stage import Stage
from docker_dsl.state import StageGraph


def test_apt_install_inserts_update(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.apt_install("curl", "git")
    rendered = s.render()
    assert "apt-get update -y" in rendered
    assert "apt-get install -y --no-install-recommends curl git" in rendered


def test_ppa_marks_dirty_and_reinserts_update(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.apt_install("software-properties-common")
        r.add_apt_ppa("ppa:apt-fast/stable")
        r.apt_install("apt-fast")
    rendered = s.render()
    assert rendered.count("apt-get update -y") == 2


def test_fast_install_uses_apt_fast(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.apt_install("curl", fast=True)
    assert "apt-fast install -y --no-install-recommends curl" in s.render()


def test_apt_with_cache_mount(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s:
        with s.cache("/var/cache/apt", lock=True), s.run() as r:
            r.apt_install("curl")
    rendered = s.render()
    assert "--mount=type=cache,target=/var/cache/apt,sharing=locked" in rendered
    assert "apt-get install -y --no-install-recommends curl" in rendered


def test_add_repo_writes_keyring_and_sources(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.add_apt_repo(
            "https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB",
            "https://apt.repos.intel.com/oneapi all main",
            name="oneapi-archive-keyring",
        )
        r.apt_install("intel-oneapi-mkl-devel")
    rendered = s.render()
    assert "/usr/share/keyrings/oneapi-archive-keyring.gpg" in rendered
    assert "/etc/apt/sources.list.d/oneapi-archive-keyring.list" in rendered


def test_raw_command_between_apt_installs(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.apt_install("software-properties-common")
        r.add_apt_ppa("ppa:apt-fast/stable")
        r("curl https://example.com/setup.sh | bash -")
        r.apt_install("apt-fast")
    rendered = s.render()
    assert "curl https://example.com/setup.sh | bash -" in rendered
    assert rendered.count("apt-get update -y") == 2


def test_raw_cleanup_at_end(graph: StageGraph) -> None:
    with Stage("ubuntu:24.04") as s, s.run() as r:
        r.apt_install("curl")
        r("rm -rf /tmp/*")
    assert "rm -rf /tmp/*" in s.render()
