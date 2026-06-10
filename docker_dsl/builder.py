from __future__ import annotations

from dataclasses import dataclass, field
from types import TracebackType
from typing import TYPE_CHECKING, Self

from docker_dsl.apt import AptMixin
from docker_dsl.run import CdScope, RedirectableCmd, ShellCommand

if TYPE_CHECKING:
    from docker_dsl.run import CmdInvoker
    from docker_dsl.stage import Stage


@dataclass
class RunBuilder(AptMixin):
    """Accumulates shell commands into a single `RUN` instruction.

    Obtained from `Stage.run` used as a `with` block. Any attribute you access
    becomes a shell binary: `r.git("clone", url)` emits `git clone <url>`, with
    keyword arguments turned into flags by `CmdInvoker`. The shipped
    `builder.pyi` type stub gives editors completions for the common binaries.
    Use `__call__` for a raw command line, and the apt helpers from `AptMixin`
    for package installs.

    On block exit, the accumulated commands join with ` && ` into one `RUN`;
    nothing is emitted if the block raises or stays empty.

    Example:
        >>> with s.run() as r:
        ...     r.git("clone", "https://example.com/repo.git", ".")
        ...     r.make("-j$(nproc)")
    """

    stage: Stage
    commands: list[ShellCommand] = field(default_factory=list)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None or not self.commands:
            return
        self.stage.emit_run(self.build_script())

    def build_script(self) -> str:
        return " \\\n  && ".join(c.render() for c in self.commands)

    def append(self, command: ShellCommand) -> None:
        self.commands.append(command)

    # The generated builder.pyi shadows this module for type checkers, so
    # `Self` here is a distinct type from the stub's `RunBuilder` that
    # CmdInvoker & co. are annotated against.
    def __getattr__(self, name: str) -> CmdInvoker:
        if name.startswith("_"):
            raise AttributeError(name)
        from docker_dsl.run import CmdInvoker

        return CmdInvoker(self, name)  # type: ignore

    def __call__(self, raw: str, *, env: dict[str, str] | None = None) -> None:
        """Append a raw command line, for anything the dispatch can't express.

        Args:
            raw: The verbatim shell command.
            env: Environment variables prefixed onto the command.
        """
        self.append(ShellCommand(raw=raw, env=env or {}))

    def echo(self, text: str) -> RedirectableCmd:
        """Build an `echo` whose output you redirect to a file.

        Apply `>>` to append or `>` to truncate, with the destination path on
        the right (see `RedirectableCmd`).

        Args:
            text: The text to echo. It is quoted for you.

        Returns:
            A `RedirectableCmd` awaiting a `>>` or `>` redirect.

        Example:
            >>> r.echo("deb ... main") >> "/etc/apt/sources.list.d/extra.list"
        """
        return RedirectableCmd(self, text)  # type: ignore

    def cd(self, path: str) -> CdScope:
        """Change directory, as a statement or a scoped `with` block.

        As a bare call, later commands run from `path`. As a `with` block, the
        directory is restored with `cd -` on exit (see `CdScope`).

        Args:
            path: Directory to change into.

        Returns:
            A `CdScope`, usable as a statement or a `with` block.

        Example:
            >>> with r.cd("/src"):
            ...     r.make("install")
        """
        return CdScope(self, path)  # type: ignore

    def curl_bash(self, url: str, *, args: tuple[str, ...] = ()) -> None:
        """Pipe a remote install script into `bash` over a pinned-TLS curl.

        Args:
            url: Script URL, fetched with `--proto '=https' --tlsv1.2`.
            args: Arguments passed to the script after `-s --`.
        """
        tail = f" -- {' '.join(args)}" if args else ""
        self.append(ShellCommand(raw=f"curl --proto '=https' --tlsv1.2 -sSf {url} | bash -s{tail}"))

    def install(self, url: str, *, target: str = "/usr/local/bin", strip: int = 1) -> None:
        """Download a tarball and extract it into a directory.

        Args:
            url: Tarball URL.
            target: Directory to extract into.
            strip: Leading path components to strip (`tar --strip-components`).
        """
        self.append(ShellCommand(raw=f"curl -fL {url} | tar xz -C {target} --strip-components={strip}"))

    def fetch_file(self, url: str, dest: str) -> None:
        """Download a single file, creating its parent directory first.

        Args:
            url: File URL.
            dest: Destination path; its parent directory is created.
        """
        self.append(ShellCommand(raw=f"mkdir -p $(dirname {dest}) && curl -fsSL {url} -o {dest}"))
