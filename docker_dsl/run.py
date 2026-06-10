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
    """A pending `echo` awaiting a redirect target.

    Returned by `RunBuilder.echo`. Apply `>>` to append to a file or `>` to
    truncate it, with the path on the right. The echoed text is quoted for you.

    Example:
        >>> r.echo("pillow>=11") >> "/root/overrides.txt"   # append
        >>> r.echo("numpy<3") > "/etc/pip/constraint.txt"    # truncate
    """

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
    """A bound shell binary, produced by `RunBuilder`'s attribute dispatch.

    Accessing `r.<name>` yields one of these for `<name>`; calling it appends
    the command. Positional arguments pass through verbatim. Keyword arguments
    become flags: `depth="1"` adds `--depth 1`, `verbose=True` adds `--verbose`,
    and a `False` value is dropped. Underscores in names become hyphens.

    Example:
        >>> r.git("clone", url, depth="1", recurse_submodules=True)
        ... # git clone <url> --depth 1 --recurse-submodules
    """

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
    """A `cd` that optionally restores the previous directory.

    Returned by `RunBuilder.cd`. As a bare statement it just changes directory.
    As a `with` block it appends `cd -` on exit, so later commands resume where
    they were.

    Example:
        >>> with r.cd("/src/build"):
        ...     r.make("install")
        ... # cd /src/build && make install && cd -
    """

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
