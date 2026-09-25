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
    """I24 as a derived relation: full width, from the I31 foot flange's
    south end to the relief."""
    import build_drive_train_assembly as bdt
    import cone_tip_block_spec as block

    assert bdt.TIP_SHIM_X == pytest.approx(block.BLOCK_X)
    assert bdt.TIP_SHIM_SOUTH_Z == pytest.approx(-block.BLOCK_Z / 2.0 - block.FLANGE_LEN)
    assert bdt.TIP_SHIM_NORTH_Z == pytest.approx(
        block.BLOCK_Z / 2.0 - block.HEEL_RELIEF_DEPTH
    )


def test_hold_down_sits_under_the_flange_slot_with_a_nut_on_the_flange() -> None:
    """I31: the screw stands at the flange slot's centre, 16.7 south of the
    block centre, and the modelled stack leaves it inside the block spec's
    printed-limit protrusion range (a pitch at the thick end)."""
    import build_drive_train_assembly as bdt
    import cone_tip_block_spec as block

    assert bdt.TIP_HOLD_STATION == pytest.approx(
        bdt.TIP_BLOCK_STATION - (block.BLOCK_Z / 2.0 + block.FLANGE_SLOT_Z)
    )
    assert bdt.TIP_HOLD_STATION - bdt.PIVOT_STATION == pytest.approx(-27.7)
    # 6.35 plate, 3.00 counterbore, 1.10 shim, 3.50 flange, 11/64 nut, 5/8 screw.
    assert bdt.TIP_HOLD_PROTRUSION == pytest.approx(
        3.00 + 15.875 - (6.35 + 1.10 + 3.50 + 11.0 / 64.0 * 25.4)
    )
    low, high = block.HOLDDOWN_PROTRUSION_MM
    assert low <= bdt.TIP_HOLD_PROTRUSION <= high
    assert low >= 25.4 / 32.0


def test_hold_down_clears_the_small_cone_gears() -> None:
    """Main, I31 item 2: the flange, the nut and the screw end stay >= 2.0
    under T006, T012 and every other gear over the flange, and the bushing."""
    import build_drive_train_assembly as bdt

    gaps = bdt.TIP_HOLD_GEAR_CLEARANCES
    assert {"T006", "T012", "tip bushing"} <= set(gaps)
    assert min(gaps.values()) >= bdt.TIP_GEAR_CLEARANCE_MIN == 2.0
    assert min(gaps.values()) == pytest.approx(15.23, abs=0.01)  # T018


def test_hold_down_placement_turns_the_hex_flats_onto_the_slot_walls() -> None:
    """The recipe's hex flats face part +/-X; placed, they must face along the
    cone axis (the counterbored slot's walls) with the head down."""
    import build_drive_train_assembly as bdt

    x_row, y_row, _z_row = bdt.TIP_SCREW_ROWS
    axis = (bdt.SIN_I, 0.0, bdt.COS_I)
    assert abs(sum(a * b for a, b in zip(x_row, axis))) == pytest.approx(1.0)
    assert y_row == pytest.approx([0.0, -1.0, 0.0], abs=1e-12)
    nut_x, nut_y, _ = bdt.TIP_NUT_ROWS
    assert abs(sum(a * b for a, b in zip(nut_x, axis))) == pytest.approx(1.0)
    assert nut_y == pytest.approx([0.0, 1.0, 0.0], abs=1e-12)


def test_widened_west_edge_is_proven_over_the_whole_swing() -> None:
    """Main, I31 item 8: the NW-widened edge keeps the arbor pedestals, the
    base lip and every other base seat clear from engaged to disengaged."""
    import build_drive_train_assembly as bdt

    assert bdt.SWING_ANGLES[0] == 0.0
    assert bdt.SWING_ANGLES[-1] == pytest.approx(bdt.DISENGAGE_DEG)
    sweep = bdt.SWING_SWEEP
    assert sweep["south arbor pedestal"] >= 2.0
    assert sweep["north arbor pedestal"] >= 0.25
    assert min(v for k, v in sweep.items() if k.endswith("inside the lip")) >= 0.0
    assert sweep["nearest other base seat"][0] >= bdt.SWING_FEATURE_CLEARANCE
    # The north pedestal gap closes as the plate swings out: the engaged pose
    # alone would not have found its minimum.
    engaged = bdt.west_edge_arbor_gaps(0.0)[1]
    assert sweep["north arbor pedestal"] < engaged
