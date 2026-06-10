from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Mount(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def render(self) -> str:
        raise NotImplementedError


class CacheMount(Mount):
    kind: Literal["cache"] = "cache"
    target: str
    sharing: Literal["shared", "locked", "private"] = "shared"

    def render(self) -> str:
        return f"--mount=type=cache,target={self.target},sharing={self.sharing}"


class SecretMount(Mount):
    kind: Literal["secret"] = "secret"
    id: str
    target: str

    def render(self) -> str:
        return f"--mount=type=secret,id={self.id},target={self.target}"


class BindMount(Mount):
    kind: Literal["bind"] = "bind"
    source: str
    target: str

    def render(self) -> str:
        return f"--mount=type=bind,source={self.source},target={self.target}"
