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
    """A build stage — one `FROM` and the instructions that follow it.

    Open a stage as a context manager; every method call inside the block
    appends an instruction to it. Derive child stages with `stage` and copy
    artifacts between them with `copy`.

    Args:
        base: The base image, or a parent stage's name for a derived stage.
        name: The stage name used in `FROM ... AS <name>`. Child stages created
            with `stage` infer this from the `as` target.

    Example:
        >>> with Stage("ubuntu:24.04") as s:
        ...     s.workdir("/app")
        ...     s.cmd("./server")
    """

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
        """Emit an `ARG` build argument.

        Args:
            name: Argument name.
            value: Default value.
            env: When `True`, also emit an `ENV` that forwards the argument into
                the image environment.
        """
        if not self.active:
            return
        self.instructions.append(Arg(name=name, value=value))
        if env:
            self.instructions.append(Env(pairs={name: f"${{{name}}}"}))

    def env(self, mapping: dict[str, str] | dict[str, str | None]) -> EnvScope:
        """Emit an `ENV` instruction, and optionally scope it.

        Keys whose value is `None` are dropped, so a conditional value need not
        be guarded at the call site. Used as a plain call, the variables persist
        for the rest of the stage. Used as a `with` block, they apply only to
        the `RUN` commands inside it (see `EnvScope`).

        Args:
            mapping: Environment variables to set. `None` values are skipped.

        Returns:
            An `EnvScope` for optional `with`-block scoping.
        """
        filtered = {k: v for k, v in mapping.items() if v is not None}
        if self.active and filtered:
            self.instructions.append(Env(pairs=filtered))
        return EnvScope(self, filtered)

    def add_to_path(self, *entries: str) -> None:
        """Prepend entries to `PATH` with an `ENV` instruction.

        Args:
            *entries: Directories to prepend, ahead of the existing `$PATH`.
        """
        if not self.active:
            return
        self.instructions.append(Env(pairs={"PATH": ":".join([*entries, "$PATH"])}))

    def workdir(self, path: str) -> None:
        """Emit a `WORKDIR` instruction.

        Args:
            path: The working directory for later instructions.
        """
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
        """Emit a `COPY` instruction.

        Pass `stage` to copy an artifact from another stage (`COPY --from`),
        `image` to copy from a named image, or neither to copy from the build
        context. `--link` is added automatically for cross-stage and
        cross-image copies; override with `link`.

        Args:
            src: Source path.
            dst: Destination path. Defaults to `src`.
            image: Image to copy from.
            stage: Stage to copy from; its name becomes the `--from` value.
            from_: Raw `--from` value, when neither `image` nor `stage` fits.
            link: Force `--link` on or off.
        """
        if not self.active:
            return
        self.instructions.append(
            Copy(
                src=src,
                dst=dst or src,
                from_=image if image is not None else (stage.name if stage is not None else from_),
                link=link if link is not None else (image is not None or stage is not None),
            )
        )

    def entrypoint(self, *cmd: str) -> None:
        """Emit an `ENTRYPOINT` in exec form.

        Args:
            *cmd: The executable and its fixed arguments.
        """
        if not self.active:
            return
        self.instructions.append(Entrypoint(args=cmd))

    def cmd(self, *args: str) -> None:
        """Emit a `CMD` in exec form.

        Args:
            *args: The default command and arguments.
        """
        if not self.active:
            return
        self.instructions.append(Cmd(args=args))

    @overload
    def run(self) -> RunBuilder: ...
    @overload
    def run(self, *args: str, env: dict[str, str] | None = None) -> None: ...
    def run(self, *args: str, env: dict[str, str] | None = None) -> RunBuilder | None:
        """Emit a `RUN` instruction, directly or via a builder.

        Called with arguments, it emits one `RUN` for that single command.
        Called with no arguments, it returns a `RunBuilder` to use as a `with`
        block; the commands accumulated inside it become one `&&`-joined `RUN`,
        picking up any mounts and env scopes open around the block.

        Args:
            *args: A single command's words. Omit to get a `RunBuilder`.
            env: Inline environment variables for the command.

        Returns:
            A `RunBuilder` when called with no arguments; otherwise `None`.

        Example:
            >>> with s.run() as r:
            ...     r.apt_install("git", "curl")
        """
        if args:
            if self.active:
                self.emit_run(
                    " ".join(
                        (
                            *(f'{k}="{v}"' for k, v in (env or {}).items()),
                            *args,
                        )
                    )
                )
            return None
        return RunBuilder(self) if self.active else Noop()  # type: ignore

    def cache(self, target: str, *, lock: bool = False) -> MountScope:
        """Scope a BuildKit cache mount over a `with` block.

        Every `RUN` inside the block mounts a persistent cache at `target`, so
        package and build caches survive between builds.

        Args:
            target: Mount path inside the container.
            lock: Use `sharing=locked` instead of the default `shared`, to
                serialize concurrent builds that write the same cache.

        Returns:
            A `MountScope` to use as a `with` block.
        """
        if not self.active:
            return Noop()  # type: ignore
        return MountScope(self, CacheMount(target=target, sharing="locked" if lock else "shared"))

    def secret(self, secret_id: str, *, target: str) -> MountScope:
        """Scope a BuildKit secret mount over a `with` block.

        The secret is mounted only for `RUN` commands inside the block and never
        lands in an image layer.

        Args:
            secret_id: Secret id, supplied at build time with
                `docker build --secret`.
            target: Mount path inside the container.

        Returns:
            A `MountScope` to use as a `with` block.
        """
        if not self.active:
            return Noop()  # type: ignore
        return MountScope(self, SecretMount(id=secret_id, target=target))

    def bind(self, *, source: str, target: str) -> MountScope:
        """Scope a BuildKit bind mount over a `with` block.

        Mounts a build-context path read-only for `RUN` commands inside the
        block, avoiding a `COPY` when files are only needed during the command.

        Args:
            source: Path in the build context.
            target: Mount path inside the container.

        Returns:
            A `MountScope` to use as a `with` block.
        """
        if not self.active:
            return Noop()  # type: ignore
        return MountScope(self, BindMount(source=source, target=target))

    def stage(self, *, name: str | None = None) -> Stage:
        """Derive a child stage from this one (`FROM <this stage> AS ...`).

        The child's name is taken from the `as` target of the `with` statement
        — `with base.stage() as builder:` names it `builder` — so it need not be
        passed. Override with `name`.

        Args:
            name: Explicit stage name, overriding the inferred one.

        Returns:
            A new `Stage` based on this stage.

        Example:
            >>> with base.stage() as builder:
            ...     builder.run("make")
        """
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
    """A `with` block that applies a mount to the `RUN` commands inside it.

    Returned by `Stage.cache`, `Stage.secret`, and `Stage.bind`. Nest several
    in one `with` to apply them together. You rarely construct this directly.
    """

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
    """A `with` block that confines env variables to the `RUN` commands inside.

    Returned by `Stage.env`. Inside the block, the variables are exported ahead
    of each `RUN` rather than emitted as a stage-wide `ENV`, so they do not leak
    into the image. You rarely construct this directly.
    """

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
