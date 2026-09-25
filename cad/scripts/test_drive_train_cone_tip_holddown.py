"""Import-time contracts for the cone tip block's hold-down stack in the drive train.

The block (MHA-092), its MHA-141 shim pack and the hold-down hardware are
separate parts whose agreement the drive-train builder asserts when it is
imported. These tests read those asserts and the values they produce.
"""

from __future__ import annotations

import ast
from pathlib import Path

BUILDER = Path(__file__).with_name("build_drive_train_assembly.py")


def _compares_naming(tree: ast.AST, names: set[str]) -> list[ast.Compare]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        if used & names:
            found.append(node)
    return found


def test_shim_footprint_is_not_compared_with_exact_float_equality() -> None:
    """Main's I24 nit: the footprint check uses abs() tolerances per axis,
    like its neighbours, never == / != on floats."""
    tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
    compares = _compares_naming(tree, {"TIP_SHIM_X", "TIP_SHIM_Z"})
    assert compares, "the shim footprint check disappeared"
    exact = [
        ast.unparse(node)
        for node in compares
        if any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
    ]
    assert not exact, f"exact float comparison on the shim footprint: {exact}"
