from __future__ import annotations

import sys
from dataclasses import dataclass, field
from types import TracebackType
from typing import Self, overload

from docker_dsl.builder import RunBuilder
from docker_dsl.instructions import Arg, Cmd, Copy, Entrypoint, Env, Instruction, Run, Workdir
from docker_dsl.mounts import BindMount, CacheMount, Mount, SecretMount
from docker_dsl.naming import Naming
from docker_dsl.state import StageGraph, current_graph


@dataclass
class Stage:
    base: str
    name: str = "base"
    graph: StageGraph | None = field(default_factory=current_graph.get)
    instructions: list[Instruction] = field(default_factory=list)
    mounts_stack: list[Mount] = field(default_factory=list)
    env_stack: list[dict[str, str]] = field(default_factory=list)
    counter: int = 0

    @property
    def active(self) -> bool:
        return self.graph is not None

    def __enter__(self) -> Self:
        if self.graph is not None:
            self.graph.push(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.graph is None:
            return
        self.graph.pop()

    def arg(self, name: str, value: str, *, env: bool = False) -> None:
        if not self.active:
            return
        self.instructions.append(Arg(name=name, value=value))
        if env:
            self.instructions.append(Env(pairs={name: f"${{{name}}}"}))

    def env(self, mapping: dict[str, str] | dict[str, str | None]) -> EnvScope:
        filtered = {k: v for k, v in mapping.items() if v is not None}
        if self.active and filtered:
            self.instructions.append(Env(pairs=filtered))
        return EnvScope(self, filtered)

    def add_to_path(self, *entries: str) -> None:
        if not self.active:
            return
        self.instructions.append(Env(pairs={"PATH": ":".join([*entries, "$PATH"])}))

    def workdir(self, path: str) -> None:
        if not self.active:
            return
        self.instructions.append(Workdir(path=path))

    def copy(
        self,
        src: str,
        dst: str | None = None,
        *,
        image: str | None = None,
        stage: Stage | None = None,
        from_: str | None = None,
        link: bool | None = None,
    ) -> None:
        if not self.active:
            return
        self.instructions.append(Copy(
            src=src,
            dst=dst or src,
            from_=image if image is not None else (stage.name if stage is not None else from_),
            link=link if link is not None else (image is not None or stage is not None),
        ))

    def entrypoint(self, *cmd: str) -> None:
        if not self.active:
            return
        self.instructions.append(Entrypoint(args=cmd))

    def cmd(self, *args: str) -> None:
        if not self.active:
            return
        self.instructions.append(Cmd(args=args))

    @overload
    def run(self) -> RunBuilder: ...
    @overload
    def run(self, *args: str, env: dict[str, str] | None = None) -> None: ...
    def run(self, *args: str, env: dict[str, str] | None = None) -> RunBuilder | None:
        if args:
            if self.active:
                self.emit_run(" ".join((
                    *(f'{k}="{v}"' for k, v in (env or {}).items()),
                    *args,
                )))
            return None
        return RunBuilder(self) if self.active else Noop()  # type: ignore

    def cache(self, target: str, *, lock: bool = False) -> MountScope:
        if not self.active:
            return Noop()  # type: ignore
        return MountScope(self, CacheMount(target=target, sharing="locked" if lock else "shared"))

    def secret(self, secret_id: str, *, target: str) -> MountScope:
        if not self.active:
            return Noop()  # type: ignore
        return MountScope(self, SecretMount(id=secret_id, target=target))

    def bind(self, *, source: str, target: str) -> MountScope:
        if not self.active:
            return Noop()  # type: ignore
        return MountScope(self, BindMount(source=source, target=target))

    def stage(self, *, name: str | None = None) -> Stage:
        if not self.active:
            return Noop()  # type: ignore
        return Stage(
            self.name,
            name=name or Naming.infer_with_target(sys._getframe(1)) or self.auto_stage_name(),
        )

    def auto_stage_name(self) -> str:
        self.counter += 1
        return f"stage_{self.counter}"

    def emit_run(self, script: str) -> None:
        if stacked := {k: v for scope in self.env_stack for k, v in scope.items()}:
            exports = " ".join(f'{k}="{v}"' for k, v in stacked.items())
            script = f"export {exports} \\\n  && {script}"
        self.instructions.append(Run(script=script, mounts=tuple(self.mounts_stack)))

    def render(self) -> str:
        return "\n".join((f"FROM {self.base} AS {self.name}", *(i.render() for i in self.instructions)))


@dataclass
class MountScope:
    stage: Stage
    mount: Mount

    def __enter__(self) -> Self:
        if self.stage.active:
            self.stage.mounts_stack.append(self.mount)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if not self.stage.active:
            return
        self.stage.mounts_stack.pop()


@dataclass
class EnvScope:
    stage: Stage
    env: dict[str, str]

    def __enter__(self) -> Self:
        if self.stage.active and self.env:
            for i in reversed(range(len(self.stage.instructions))):
                if isinstance(inst := self.stage.instructions[i], Env) and inst.pairs == self.env:
                    self.stage.instructions.pop(i)
                    break
            self.stage.env_stack.append(self.env)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self.stage.active and self.env:
            self.stage.env_stack.pop()


class Noop:
    def __getattr__(self, name: str) -> Noop:
        return self

    def __call__(self, *args: object, **kwargs: object) -> Noop:
        return self

    def __enter__(self) -> Noop:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return

    def __rshift__(self, other: object) -> None:
        return

    def __gt__(self, other: object) -> bool:  # type: ignore[override]
        return False
