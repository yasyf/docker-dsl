from __future__ import annotations

from docker_dsl.stage import Stage
from docker_dsl.state import StageGraph, current_graph


class TestStageNaming:
    def activate(self) -> None:
        current_graph.set(StageGraph())

    def test_inferred_name_from_with_target(self) -> None:
        self.activate()
        with Stage("ubuntu:24.04") as base, base.stage() as faiss:
            assert isinstance(faiss, Stage)
            assert faiss.name == "faiss"

    def test_explicit_name_wins(self) -> None:
        self.activate()
        with Stage("ubuntu:24.04") as base, base.stage(name="override") as whatever:
            assert isinstance(whatever, Stage)
            assert whatever.name == "override"

    def test_child_stage_base_is_parent_name(self) -> None:
        self.activate()
        with Stage("ubuntu:24.04") as base, base.stage(name="child") as child:
            assert isinstance(child, Stage)
            assert child.base == base.name
