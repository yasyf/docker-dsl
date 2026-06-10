from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docker_dsl.run import ShellCommand


@dataclass(kw_only=True)
class AptMixin:
    apt_updated: bool = False
    apt_dirty: bool = True

    def append(self, command: ShellCommand) -> None: ...

    def apt_install(self, *packages: str, fast: bool = False) -> None:
        from docker_dsl.run import ShellCommand

        if not self.apt_updated or self.apt_dirty:
            self.append(ShellCommand(raw="apt-get update -y"))
            self.apt_updated = True
            self.apt_dirty = False
        cmd = "apt-fast" if fast else "apt-get"
        self.append(ShellCommand(raw=f"{cmd} install -y --no-install-recommends {' '.join(packages)}"))

    def add_apt_ppa(self, ppa: str) -> None:
        from docker_dsl.run import ShellCommand

        self.append(ShellCommand(raw=f"add-apt-repository {ppa} -y"))
        self.apt_dirty = True

    def add_apt_repo(self, key_url: str, repo_url: str, *, name: str) -> None:
        from docker_dsl.run import ShellCommand

        self.append(
            ShellCommand(raw=f"wget -O- {key_url} | gpg --dearmor | tee /usr/share/keyrings/{name}.gpg > /dev/null")
        )
        self.append(
            ShellCommand(
                raw=f'echo "deb [signed-by=/usr/share/keyrings/{name}.gpg] {repo_url}" '
                f"| tee /etc/apt/sources.list.d/{name}.list"
            )
        )
        self.apt_dirty = True
