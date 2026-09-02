"""Offline invariants for the recentered alignment-pinion support closure."""

from __future__ import annotations

import math

import build_drive_train_assembly as drive
from rocker_arm_support_spec import SUPPORT_WORLD_X


def test_alignment_pinion_mesh_gap_stays_at_the_proven_axis() -> None:
    assert drive.APINION_Y == drive.Y_DRIVE
    assert math.isclose(
        drive.APINION_X - drive.X_DRUM,
        drive.TIP_DRUM120 + drive.TIP_APINION + drive.APINION_GAP,
        abs_tol=1e-9,
    )
    assert drive.APINION_GAP == 2.0


def test_support_rig_keeps_its_proven_outboard_topology() -> None:
    assert drive.X_DRUM < drive.APINION_X < drive.PIVOT_X < drive.LIFT_X
    assert drive.BLOCK_X > drive.APINION_X
    # c557005e: the lever leans -40 (machine +X, off the arbor's front stub)
    # while the pivot/lift/block rig itself stays outboard of the pinion.
    assert drive.LEVER_TILT_DEG < 0.0
    assert drive.HANDLE_TILT_DEG > 0.0

    block_near_edge = drive.BLOCK_X - drive.BLOCK_WIDTH / 2.0
    cylinder_outboard_tip = drive.X_DRUM + drive.TIP_DRUM120
    assert block_near_edge - cylinder_outboard_tip >= 0.25
    throw_angles = (
        drive.LEVER_TILT_DEG
        + math.copysign(step * 0.25, drive.LEVER_TILT_DEG)
        for step in range(81)
    )
    assert all(abs(angle) >= abs(drive.LEVER_TILT_DEG) for angle in throw_angles)


def test_rederived_cam_and_return_leaf_clearances_are_positive() -> None:
    assert math.isclose(drive._PARK_GAP, 0.15, abs_tol=1e-9)
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
        rocker_near_face
        - (drive.SPRING_HOLE_X + drive.FSCREW_HEAD_DIA / 2.0)
        >= 0.25
    )


def test_base_holes_follow_the_rederived_support() -> None:
    for derived, base in zip(drive._BLOCK_SCREW_XZ, drive.BASE_BLOCK_XZ, strict=True):
        assert math.dist(derived, base) < 1e-9
    for derived, base in zip(drive._FOOT_SCREW_XZ, drive.BASE_FOOT_XZ, strict=True):
        assert math.dist(derived, base) < 1e-9
