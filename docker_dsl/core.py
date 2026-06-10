from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import ModuleType, TracebackType
from typing import Any, Self

from pydantic import create_model

from docker_dsl.context import Registry, current_config
from docker_dsl.state import StageGraph, current_graph


@dataclass
class Dockerfile:
    module: ModuleType

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return

    def render(self, path: str | Path | None = None, **config_values: Any) -> str:
        fields = {name: (type_, ...) for name, type_ in Registry.get(self.module).items()}
        model = create_model("Context", **fields).model_validate(config_values)  # type: ignore

        graph = StageGraph()
        token_cfg = current_config.set(model)
        token_graph = current_graph.set(graph)
        try:
            self.reload_module()
        finally:
            current_graph.reset(token_graph)
            current_config.reset(token_cfg)

        text = graph.render()
        if path is not None:
            Path(path).write_text(text)
        return text

    def reload_module(self) -> None:
        spec = self.module.__spec__
        if spec is None or spec.loader is None:
            raise RuntimeError(f"module {self.module.__name__!r} has no loader; cannot render")
        spec.loader.exec_module(self.module)
