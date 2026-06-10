from __future__ import annotations

import ast
from types import FrameType

import executing


class Naming:
    @classmethod
    def infer_with_target(cls, frame: FrameType) -> str | None:
        source = executing.Source.for_frame(frame)
        node = source.executing(frame).node
        if node is None or source.tree is None:
            return None
        for with_node in ast.walk(source.tree):
            if not isinstance(with_node, ast.With):
                continue
            for item in with_node.items:
                if not cls.expression_contains(item.context_expr, node):
                    continue
                if isinstance(item.optional_vars, ast.Name):
                    return item.optional_vars.id
        return None

    @classmethod
    def expression_contains(cls, expr: ast.AST, target: ast.AST) -> bool:
        return any(child is target for child in ast.walk(expr))
