from __future__ import annotations

from dataclasses import dataclass, field
from types import TracebackType
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from docker_dsl.builder import RunBuilder


@dataclass
class ShellCommand:
    raw: str
    env: dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        return " ".join((*(f'{k}="{v}"' for k, v in self.env.items()), self.raw))


@dataclass
class RedirectableCmd:
    builder: RunBuilder
    text: str

    def __rshift__(self, path: str) -> None:
        self.builder.append(ShellCommand(raw=f"echo {self.quote(self.text)} >> {path}"))

    def __gt__(self, path: str) -> None:
        self.builder.append(ShellCommand(raw=f"echo {self.quote(self.text)} > {path}"))

    @staticmethod
    def quote(text: str) -> str:
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'


@dataclass
class CmdInvoker:
    builder: RunBuilder
    binary: str

    def __call__(self, *args: str, env: dict[str, str] | None = None, **kwargs: str | bool) -> None:
        flag_args: list[str] = []
        for k, v in kwargs.items():
            flag = f"--{k.replace('_', '-')}"
            match v:
                case True:
                    flag_args.append(flag)
                case False:
                    pass
                case str():
                    flag_args.extend((flag, v))
        self.builder.append(ShellCommand(raw=" ".join((self.binary, *args, *flag_args)), env=env or {}))


@dataclass
class CdScope:
    builder: RunBuilder
    path: str

    def __post_init__(self) -> None:
        self.builder.append(ShellCommand(raw=f"cd {self.path}"))

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.builder.append(ShellCommand(raw="cd -"))


__all__ = ["CdScope", "CmdInvoker", "RedirectableCmd", "ShellCommand"]
