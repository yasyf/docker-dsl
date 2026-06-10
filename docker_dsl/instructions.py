from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from docker_dsl.mounts import Mount


class Instruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def render(self) -> str:
        raise NotImplementedError


class Arg(Instruction):
    kind: Literal["arg"] = "arg"
    name: str
    value: str

    def render(self) -> str:
        return f"ARG {self.name}={self.value}"


class Env(Instruction):
    kind: Literal["env"] = "env"
    pairs: dict[str, str]

    def render(self) -> str:
        return "\n".join(f"ENV {k}={v}" for k, v in self.pairs.items())


class Workdir(Instruction):
    kind: Literal["workdir"] = "workdir"
    path: str

    def render(self) -> str:
        return f"WORKDIR {self.path}"


class Copy(Instruction):
    kind: Literal["copy"] = "copy"
    src: str
    dst: str
    from_: str | None = None
    link: bool = False

    def render(self) -> str:
        return " ".join(p for p in (
            "COPY",
            f"--from={self.from_}" if self.from_ is not None else None,
            "--link" if self.link else None,
            self.src,
            self.dst,
        ) if p)


class Run(Instruction):
    kind: Literal["run"] = "run"
    script: str
    mounts: tuple[Mount, ...] = Field(default_factory=tuple)

    def render(self) -> str:
        if not self.mounts:
            return f"RUN {self.script}"
        return f"RUN {' '.join(m.render() for m in self.mounts)} \\\n  {self.script}"


class Entrypoint(Instruction):
    kind: Literal["entrypoint"] = "entrypoint"
    args: tuple[str, ...]

    def render(self) -> str:
        return f"ENTRYPOINT {json.dumps(list(self.args))}"


class Cmd(Instruction):
    kind: Literal["cmd"] = "cmd"
    args: tuple[str, ...]

    def render(self) -> str:
        return f"CMD {json.dumps(list(self.args))}"
