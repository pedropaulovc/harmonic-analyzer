"""Import-time contracts for the cone tip block's hold-down stack in the drive train.

The block (MHA-092), its MHA-141 shim pack and the hold-down hardware are
separate parts whose agreement the drive-train builder asserts when it is
imported. These tests read those asserts and the values they produce.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

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
    compares = _compares_naming(
        tree, {"TIP_SHIM_X", "TIP_SHIM_Z", "TIP_SHIM_NORTH_Z", "TIP_SHIM_SOUTH_Z"}
    )
    assert compares, "the shim footprint check disappeared"
    exact = [
        ast.unparse(node)
        for node in compares
        if any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
    ]
    assert not exact, f"exact float comparison on the shim footprint: {exact}"


def test_heel_relief_is_sized_from_the_worst_case_head_stack() -> None:
    """I31: the nominal 0.2375 gap to the pivot-screw head hid a collision.

    The north face follows the shaft tip (Sec4End .X, 0.8), the head floats
    in the drilled pivot hole, and 0.20 air stays; the height runs from the
    lowest foot (thinnest plate, thinnest shim) to the head top.
    """
    import build_drive_train_assembly as bdt
    import cone_tip_block_spec as block

    assert bdt.HEEL_NOMINAL_GAP == pytest.approx(0.2375, abs=1e-9)
    assert bdt.HEEL_TIP_TRAVEL == pytest.approx(0.8)
    assert bdt.HEEL_HEAD_FLOAT == pytest.approx((6.756 + 0.10 - 6.35) / 2.0, abs=1e-3)
    assert bdt.HEEL_DEPTH_REQUIRED == pytest.approx(1.0155, abs=1e-3)
    assert bdt.HEEL_HEIGHT_REQUIRED == pytest.approx(
        6.35 + 4.7625 - (6.35 - 0.13 + 0.05) + 0.20
    )
    # Without the relief the worst-case face runs into the head.
    assert bdt.HEEL_NOMINAL_GAP < bdt.HEEL_TIP_TRAVEL + bdt.HEEL_HEAD_FLOAT
    assert block.HEEL_RELIEF_DEPTH - 0.51 >= bdt.HEEL_DEPTH_REQUIRED
    assert block.HEEL_RELIEF_HEIGHT - 0.51 >= bdt.HEEL_HEIGHT_REQUIRED


def test_shim_covers_exactly_the_block_foot_face() -> None:
    """I24 as a derived relation: full width, south face to the relief."""
    import build_drive_train_assembly as bdt
    import cone_tip_block_spec as block

    assert bdt.TIP_SHIM_X == pytest.approx(block.BLOCK_X)
    assert bdt.TIP_SHIM_SOUTH_Z == pytest.approx(-block.BLOCK_Z / 2.0)
    assert bdt.TIP_SHIM_NORTH_Z == pytest.approx(
        block.BLOCK_Z / 2.0 - block.HEEL_RELIEF_DEPTH
    )
