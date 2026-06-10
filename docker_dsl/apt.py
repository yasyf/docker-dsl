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
        """Install apt packages, inserting `apt-get update` only when stale.

        An update runs before the first install and again after anything that
        dirties the package lists (`add_apt_ppa`, `add_apt_repo`), so you never
        write `apt-get update` by hand and never run it redundantly.

        Args:
            *packages: Package names to install.
            fast: Install with `apt-fast` instead of `apt-get` (requires
                apt-fast to be installed first).
        """
        from docker_dsl.run import ShellCommand

        if not self.apt_updated or self.apt_dirty:
            self.append(ShellCommand(raw="apt-get update -y"))
            self.apt_updated = True
            self.apt_dirty = False
        cmd = "apt-fast" if fast else "apt-get"
        self.append(ShellCommand(raw=f"{cmd} install -y --no-install-recommends {' '.join(packages)}"))

    def add_apt_ppa(self, ppa: str) -> None:
        """Add a PPA and mark the package lists stale.

        The next `apt_install` re-runs `apt-get update` so the PPA's packages
        are visible.

        Args:
            ppa: PPA spec, e.g. `ppa:apt-fast/stable`.
        """
        from docker_dsl.run import ShellCommand

        self.append(ShellCommand(raw=f"add-apt-repository {ppa} -y"))
        self.apt_dirty = True

    def add_apt_repo(self, key_url: str, repo_url: str, *, name: str) -> None:
        """Add a third-party apt repository with its signing key.

        Fetches the GPG key, dearmors it into `/usr/share/keyrings`, writes a
        `signed-by` source list, and marks the package lists stale so the next
        `apt_install` re-runs `apt-get update`.

        Args:
            key_url: URL of the repository's GPG key.
            repo_url: The `deb` line's repository and components, e.g.
                `https://example.com/apt stable main`.
            name: Basename for the keyring and source-list files.
        """
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
