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
        self.append(ShellCommand(raw=raw, env=env or {}))

    def echo(self, text: str) -> RedirectableCmd:
        return RedirectableCmd(self, text)  # type: ignore

    def cd(self, path: str) -> CdScope:
        return CdScope(self, path)  # type: ignore

    def curl_bash(self, url: str, *, args: tuple[str, ...] = ()) -> None:
        tail = f" -- {' '.join(args)}" if args else ""
        self.append(ShellCommand(raw=f"curl --proto '=https' --tlsv1.2 -sSf {url} | bash -s{tail}"))

    def install(self, url: str, *, target: str = "/usr/local/bin", strip: int = 1) -> None:
        self.append(ShellCommand(raw=f"curl -fL {url} | tar xz -C {target} --strip-components={strip}"))

    def fetch_file(self, url: str, dest: str) -> None:
        self.append(ShellCommand(raw=f"mkdir -p $(dirname {dest}) && curl -fsSL {url} -o {dest}"))
