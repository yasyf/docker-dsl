from __future__ import annotations

from docker_dsl import Stage
from docker_dsl import context as ctx

ctx.register("with_intel", bool)

with Stage("ubuntu:24.04") as s:
    s.workdir("/root")

    with s.cache("/var/cache/apt", lock=True), s.cache("/var/lib/apt", lock=True), s.run() as r:
        r.apt_install("software-properties-common")
        r.add_apt_ppa("ppa:apt-fast/stable")
        r.apt_install("apt-fast", "curl", "wget", "git", fast=True)

        if ctx.with_intel:
            r.add_apt_repo(
                "https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB",
                "https://apt.repos.intel.com/oneapi all main",
                name="oneapi-archive-keyring",
            )
            r.apt_install("intel-oneapi-mkl-devel", fast=True)

        r("rm -rf /tmp/*")

    s.cmd("bash")
