from __future__ import annotations

import sys
from contextvars import ContextVar
from types import ModuleType
from typing import Any

from pydantic import BaseModel

from docker_dsl.state import current_graph

current_config: ContextVar[BaseModel | None] = ContextVar("current_config", default=None)


class Registry:
    SCHEMAS: dict[str, dict[str, type]] = {}

    @classmethod
    def set(cls, module_name: str, name: str, type_: type) -> None:
        cls.SCHEMAS.setdefault(module_name, {})[name] = type_

    @classmethod
    def get(cls, module: ModuleType) -> dict[str, type]:
        return cls.SCHEMAS.get(module.__name__, {})


class BuildContext:
    def __getattr__(self, name: str) -> Any:
        return None if (config := current_config.get()) is None else getattr(config, name)

    def register(self, name: str, type_: type) -> None:
        if current_graph.get() is not None:
            return
        Registry.set(sys._getframe(1).f_globals["__name__"], name, type_)


context = BuildContext()


def rendering() -> bool:
    return current_config.get() is not None
