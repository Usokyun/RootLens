"""Minimal local backport for Pydantic on Python 3.9.

Pydantic 2 optionally imports ``eval_type_backport`` when it needs to resolve
annotations like ``str | None`` on older Python versions. RootLens vendors a
small compatible implementation here so the upstream KGTraceVis models can be
imported without patching that repository.
"""

from __future__ import annotations

import ast
import typing
from typing import Any


class _UnionTransformer(ast.NodeTransformer):
    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        node = self.generic_visit(node)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            parts = self._flatten_union(node)
            slice_node: ast.AST
            if len(parts) == 1:
                slice_node = parts[0]
            else:
                slice_node = ast.Tuple(elts=parts, ctx=ast.Load())
            return ast.copy_location(
                ast.Subscript(
                    value=ast.Attribute(
                        value=ast.Name(id="typing", ctx=ast.Load()),
                        attr="Union",
                        ctx=ast.Load(),
                    ),
                    slice=slice_node,
                    ctx=ast.Load(),
                ),
                node,
            )
        return node

    def _flatten_union(self, node: ast.AST) -> list[ast.AST]:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return self._flatten_union(node.left) + self._flatten_union(node.right)
        return [node]


def _expression_from_value(value: Any) -> str:
    if isinstance(value, typing.ForwardRef):
        return value.__forward_arg__
    if isinstance(value, str):
        return value
    return repr(value)


def _rewrite_pep604_union(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    rewritten = _UnionTransformer().visit(tree)
    ast.fix_missing_locations(rewritten)
    return ast.unparse(rewritten)


def eval_type_backport(
    value: Any,
    globalns: dict[str, Any] | None = None,
    localns: dict[str, Any] | None = None,
    try_default: bool = True,
) -> Any:
    expression = _expression_from_value(value)
    transformed = _rewrite_pep604_union(expression)
    namespace = {
        "typing": typing,
        "__builtins__": __builtins__,
    }
    if globalns:
        namespace.update(globalns)
    if localns:
        namespace.update(localns)
    try:
        return eval(transformed, namespace, namespace)
    except Exception:
        if try_default:
            return value
        raise
