"""Offline invariants for the recentered alignment-pinion support closure."""

from __future__ import annotations

import math

import build_drive_train_assembly as drive
from pinion_pivot_block_geometry import BLOCK_EAST
from rocker_arm_support_spec import SUPPORT_WORLD_X


def test_alignment_pinion_mesh_gap_stays_at_the_proven_axis() -> None:
    assert drive.APINION_Y == drive.Y_DRIVE
    assert math.isclose(
        drive.APINION_X - drive.X_DRUM,
        drive.TIP_DRUM120 + drive.TIP_APINION + drive.APINION_GAP,
        abs_tol=1e-9,
    )
    # U28 (user, 2026-09-23; 997f3534): the drum parks 2.0 outside the tip
    # circles PLUS the base-chord seat offset, so the engage swing ends where
    # the 120T tips seat on the gap floor (engaged C2C), not at the pitch sum.
    pitch_sum = (120 + drive.APINION_TEETH) / drive.DP_TRAIN * 25.4 / 2.0
    assert math.isclose(
        drive.APINION_GAP, 2.0 + (drive.ENGAGED_C2C - pitch_sum), abs_tol=1e-4
    )


def test_support_rig_keeps_its_proven_outboard_topology() -> None:
    assert drive.X_DRUM < drive.APINION_X < drive.PIVOT_X < drive.LIFT_X
    assert drive.BLOCK_X > drive.APINION_X
    assert drive.LEVER_TILT_DEG == 10.0
    assert drive.HANDLE_TILT_DEG > 0.0

    # U28 datum B: the block origin is its pivot bore and the block is
    # asymmetric (BLOCK_EAST 14 toward the drum, BLOCK_WEST 26), so the near
    # edge is the east end, not BLOCK_X - BLOCK_WIDTH / 2.
    block_near_edge = drive.BLOCK_X - BLOCK_EAST
    cylinder_outboard_tip = drive.X_DRUM + drive.TIP_DRUM120
    assert block_near_edge - cylinder_outboard_tip >= 0.25


def test_lever_sweeps_from_photographed_park_to_cam_solved_engagement() -> None:
    assert -85.0 < drive.CAM_ENGAGE_ROTATION_DEG < -75.0
    assert -80.0 < drive.LEVER_ENGAGED_TILT_DEG < -65.0
    assert math.isclose(
        drive._engaged_cam_gap(drive.CAM_ENGAGE_ROTATION_DEG),
        0.0,
        abs_tol=1e-12,
    )
    assert drive.LEVER_ENGAGED_TILT_DEG < 0.0 < drive.LEVER_TILT_DEG


def test_rederived_cam_and_return_leaf_clearances_are_positive() -> None:
    # The design band the assembly itself asserts (0.10..0.25 of air).  The
    # derived value moved 0.150 -> 0.153 with the U28 re-lay (997f3534) and
    # -> 0.161 with U27's line-to-line follower pin, 4.016 -> 4.000 (c9685fa0).
    assert 0.10 <= drive._PARK_GAP <= 0.25
    assert math.isclose(drive._PARK_GAP, 0.1606, abs_tol=5e-4)
    cam_authority = (drive.FPIN_DIA + drive.CAM_OD) / 2.0 - drive._D_ENG
    assert cam_authority >= 0.25
    assert drive.LIFT_Y - drive._CAM_SWEEP_R - drive.Y_BASE_TOP >= 0.25
    assert (
        math.hypot(
            drive.X_DRUM - drive.SPRING_CREST[0],
            drive.Y_DRIVE - drive.SPRING_CREST[1],
        )
        - drive.SPRING_T
        >= drive.TIP_DRUM120 + 0.25
    )
    assert drive._FPIN_TIP_S - drive._S_CAM >= 2.0


def test_return_spring_foot_clears_the_fixed_rocker_support() -> None:
    rocker_near_face = SUPPORT_WORLD_X - 31.75
    spring_foot_end = drive.SPRING_X - drive.SPR_FOOT_END_L[0]
    assert rocker_near_face - spring_foot_end >= 0.25
    assert (
        rocker_near_face - (drive.SPRING_HOLE_X + drive.FSCREW_HEAD_DIA / 2.0) >= 0.25
    )


def test_base_holes_follow_the_rederived_support() -> None:
    for derived, base in zip(drive._BLOCK_SCREW_XZ, drive.BASE_BLOCK_XZ, strict=True):
        assert math.dist(derived, base) < 1e-9
    for derived, base in zip(drive._FOOT_SCREW_XZ, drive.BASE_FOOT_XZ, strict=True):
        assert math.dist(derived, base) < 1e-9
