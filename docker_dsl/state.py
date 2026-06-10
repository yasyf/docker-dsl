from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docker_dsl.stage import Stage


class StageGraph:
    def __init__(self) -> None:
        self.stages: list[Stage] = []
        self.stage_stack: list[Stage] = []

    def push(self, stage: Stage) -> None:
        self.stages.append(stage)
        self.stage_stack.append(stage)

    def pop(self) -> None:
        self.stage_stack.pop()

    @property
    def active(self) -> Stage | None:
        return self.stage_stack[-1] if self.stage_stack else None

    def render(self) -> str:
        return "# syntax=docker/dockerfile:1\n" + "\n\n".join(s.render() for s in self.stages) + "\n"


current_graph: ContextVar[StageGraph | None] = ContextVar("current_graph", default=None)


def current_stage() -> Stage | None:
    """Return the stage of the innermost open `with Stage(...)` block.

    Use it inside a reusable helper that operates on whichever stage is active,
    so callers need not pass the stage explicitly. Returns `None` outside any
    stage block, including during the discovery pass.

    Returns:
        The active stage, or `None` when no stage block is open.
    """
    if (graph := current_graph.get()) is not None:
        return graph.active
    return None
