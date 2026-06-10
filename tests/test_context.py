from __future__ import annotations

from docker_dsl.context import Registry, context, current_config, rendering
from docker_dsl.state import StageGraph, current_graph


class TestBuildContext:
    def test_unset_context_returns_none(self) -> None:
        current_config.set(None)
        assert context.gpu is None
        assert context.anything is None

    def test_rendering_flag_reflects_current_config(self) -> None:
        current_config.set(None)
        assert rendering() is False

        class Stub:
            gpu = True

        current_config.set(Stub())  # type: ignore[arg-type]
        assert rendering() is True
        assert context.gpu is True
        current_config.set(None)


class TestRegistry:
    def test_register_writes_in_discovery_pass(self) -> None:
        current_graph.set(None)
        Registry.SCHEMAS.pop(__name__, None)
        context.register("flag", bool)
        assert Registry.SCHEMAS[__name__] == {"flag": bool}
        Registry.SCHEMAS.pop(__name__, None)

    def test_register_noop_when_graph_is_active(self) -> None:
        current_graph.set(StageGraph())
        Registry.SCHEMAS.pop(__name__, None)
        context.register("flag", bool)
        assert __name__ not in Registry.SCHEMAS
        current_graph.set(None)
