"""Import-time contracts for the cone tip block's hold-down stack in the drive train.

The block (MHA-092), its MHA-141 shim pack, the MHA-142 post fillisters and
the hold-down hardware are separate parts whose agreement the drive-train
builder asserts when it is imported. These tests read those asserts and the
values they produce.
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
    south end to the heel relief, at the block's nominal pack."""
    import build_drive_train_assembly as bdt
    import cone_tip_block_spec as block

    assert bdt.TIP_SHIM_T == pytest.approx(block.SHIM_NOMINAL)
    assert bdt.TIP_SHIM_X == pytest.approx(block.BLOCK_X)
    assert bdt.TIP_SHIM_SOUTH_Z == pytest.approx(-block.BLOCK_Z / 2.0 - block.FLANGE_LEN)
    assert bdt.TIP_SHIM_NORTH_Z == pytest.approx(
        block.BLOCK_Z / 2.0 - block.HEEL_RELIEF_DEPTH
    )


def test_post_fillisters_engage_the_plate_tap_at_least_090d() -> None:
    """I22: each MHA-142 seats on the post's counterbore floor and runs into
    the MHA-091 tap by its cut length past the post's grip -- never proud of
    the plate underside, and 0.90D of thread after the tap's edge break."""
    import build_drive_train_assembly as bdt
    import cone_swing_platform_spec as platform
    import post_mount_screw_spec as screw

    assert bdt.POST_SCREW_SEAT == pytest.approx(screw.GRIP_MM)
    assert bdt.POST_SCREW_INTO_PLATE == pytest.approx(screw.CUT_LENGTH_MM - screw.GRIP_MM)
    assert bdt.POST_SCREW_INTO_PLATE <= platform.PLATE_THICKNESS
    thread = bdt.POST_SCREW_INTO_PLATE - 2.0 * platform.POST_MOUNT_TAP_EDGE_BREAK
    assert thread >= 0.90 * platform.POST_MOUNT_THREAD_DIA
    assert platform.POST_MOUNT_ENGAGEMENT_WORST_DIAMETERS >= 0.90


@pytest.mark.xfail(
    strict=True,
    reason=(
        "I31 hold-down not placed on #877: MHA-140 (93075A150) through the "
        "block's flange slot into the MHA-146 locknut needs #925's I31 plate "
        "slot under it; it lands in the placement lineage (b), "
        "swing/917-holddown on #917 S1"
    ),
)
def test_i31_hold_down_is_placed() -> None:
    """Placed, the hold-down screw stands at the flange slot's centre, over the
    plate's tip slot, with its nut on the flange; the builder then inserts
    both parts."""
    import build_drive_train_assembly as bdt
    import cone_swing_platform_spec as platform

    source = BUILDER.read_text(encoding="utf-8")
    assert '"cone-tip-block-screw"' in source
    assert '"cone-tip-block-nut"' in source
    assert bdt.TIP_HOLD_STATION - bdt.PIVOT_STATION == pytest.approx(
        platform.TIP_SCREW_LOCAL_Z
    )
