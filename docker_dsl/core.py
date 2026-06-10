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
    """Renders a recipe module into Dockerfile text.

    A recipe is an ordinary Python module whose top-level code declares stages
    and instructions. Wrap it in a `Dockerfile` and call `render` to produce the
    text, once per configuration.

    Example:
        >>> import my_recipe
        >>> text = Dockerfile(my_recipe).render(gpu=True)
    """

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
        """Render the recipe into Dockerfile text.

        Rendering runs the recipe module a second time. The first run — the
        import that produced `module` — is the discovery pass, where every DSL
        call is a no-op and only `context.register` fires, declaring the config
        schema. This call validates `config_values` against that schema with
        pydantic, then re-executes the module body so each `Stage` and method
        call accumulates into the active build.

        Args:
            path: Where to write the rendered text. When given, the file is
                written; the text is returned either way.
            **config_values: One value per field the recipe registered with
                `context.register`. Every registered field is required, and
                values are validated before the render pass runs.

        Returns:
            The rendered Dockerfile text.

        Example:
            >>> Dockerfile(my_recipe).render(tag="v1.0.0", path="Dockerfile")
        """
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
