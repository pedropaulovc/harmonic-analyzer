"""Import-free, per-drawing machinist-review declarations.

Only ``MACHINIST_REVIEW = MachinistReviewMode.<member>`` is accepted. An
undeclared (or ``OFF``) drawing gets no review task at all, so no model tokens
are spent on it until its owner opts in with ``LEARN`` or ``ENFORCE``. Graph
loading must not execute a drawing recipe to read its policy. The declaration
never feeds the review cache key.
"""

from __future__ import annotations

import ast
import functools
from enum import StrEnum
from pathlib import Path


class MachinistReviewMode(StrEnum):
    OFF = "off"
    LEARN = "learn"
    ENFORCE = "enforce"


def mode_for_drawing(script: Path) -> MachinistReviewMode:
    """Read a literal module-level enum declaration, rejecting ambiguous bindings.

    The answer is a function of the file's current text alone, so it is
    cached by (path, text): every graph load asks for every drawing, often
    several times per process, and an edited file is simply a new key.
    """
    return _mode_for_source(str(script), script.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def _mode_for_source(script: str, text: str) -> MachinistReviewMode:
    tree = ast.parse(text, filename=script)
    bindings: list[ast.AST] = []

    class Bindings(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            if node.id == "MACHINIST_REVIEW" and isinstance(node.ctx, ast.Store):
                bindings.append(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name == "MACHINIST_REVIEW":
                bindings.append(node)

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if node.name == "MACHINIST_REVIEW":
                bindings.append(node)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                if (alias.asname or alias.name.split(".")[0]) == "MACHINIST_REVIEW":
                    bindings.append(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                if (alias.asname or alias.name) == "MACHINIST_REVIEW":
                    bindings.append(node)

        def visit_Lambda(self, node: ast.Lambda) -> None:
            return

    Bindings().visit(tree)
    declarations = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "MACHINIST_REVIEW"
    ]
    if not bindings:
        return MachinistReviewMode.OFF
    if len(bindings) == len(declarations) == 1:
        value = declarations[0].value
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id == "MachinistReviewMode"
            and value.attr in MachinistReviewMode.__members__
        ):
            return MachinistReviewMode[value.attr]
    raise ValueError(
        f"{script}: MACHINIST_REVIEW must be one module-level assignment to "
        "MachinistReviewMode.OFF, .LEARN or .ENFORCE"
    )
