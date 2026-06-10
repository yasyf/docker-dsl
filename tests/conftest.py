from __future__ import annotations

import pytest

from docker_dsl.context import current_config
from docker_dsl.state import StageGraph, current_graph


@pytest.fixture(autouse=True)
def reset_dsl_state() -> None:
    current_config.set(None)
    current_graph.set(None)


@pytest.fixture
def graph() -> StageGraph:
    g = StageGraph()
    current_graph.set(g)
    return g
