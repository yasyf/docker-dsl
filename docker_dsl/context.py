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
    """Recipe-facing handle for config fields, exported as `context`.

    Read a registered field as an attribute: `context.gpu` returns the
    validated value during a render pass, and `None` during discovery. Declare
    fields with `register`.

    Example:
        >>> from docker_dsl import context as ctx
        >>> ctx.register("gpu", bool)
        >>> base = "nvidia/cuda:12.4.0-base" if ctx.gpu else "ubuntu:24.04"
    """

    def __getattr__(self, name: str) -> Any:
        return None if (config := current_config.get()) is None else getattr(config, name)

    def register(self, name: str, type_: type) -> None:
        """Declare a required config field.

        Call this in the recipe body, once per field the recipe accepts. It
        takes effect only during the discovery pass; on the render pass it is a
        no-op, so the schema is fixed by what the import declared. pydantic
        validates the field's value against `type_` before rendering.

        Args:
            name: Field name, passed to `Dockerfile.render` and exposed as
                `context.<name>`.
            type_: The field's type, used to validate the supplied value.
        """
        if current_graph.get() is not None:
            return
        Registry.set(sys._getframe(1).f_globals["__name__"], name, type_)


context = BuildContext()


def rendering() -> bool:
    """Report whether a render pass is in progress.

    Returns `True` while `Dockerfile.render` is re-executing a recipe, and
    `False` during the discovery import. Use it to guard code that should run
    only when the build is live.

    Returns:
        `True` during the render pass, `False` during discovery.
    """
    return current_config.get() is not None
