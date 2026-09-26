"""Import-time contracts for the cone tip block's hold-down stack in the drive train.

The block (MHA-092), its MHA-141 shim pack, the MHA-142 post fillisters and
the hold-down hardware are separate parts whose agreement the drive-train
builder asserts when it is imported. These tests read those asserts and the
values they produce.
"""

from __future__ import annotations

from pathlib import Path

import pytest

BUILDER = Path(__file__).with_name("build_drive_train_assembly.py")


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
