"""Offline invariants for the recentered alignment-pinion support closure."""

from __future__ import annotations

import math

import build_drive_train_assembly as drive
import pinion_rig_fitup as FITUP
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


def _world(origin, rows, local):
    return [origin[k] + sum(local[i] * rows[i][k] for i in range(3)) for k in range(3)]


def test_mha135_pin_holes_share_one_axis_at_the_drive_train_pose() -> None:
    # MHA-135 is match-drilled through the lever hub and the lift rod at
    # assembly, so the model's two holes must be one line.  Each part cuts its
    # hole along its own local X (build_pinion_lift_rod / build_pinion_lever
    # "lever pin" axes); the rod is phased to the lever to make them coincide.
    from pinion_lever_geometry import PIN_HOLE_Z, ROD_PIN_HOLE_FROM_END

    rod_origin = [drive.LIFT_X, drive.LIFT_Y, drive.LIFT_ROD_Z0]
    lever_origin = [drive.LIFT_X, drive.LIFT_Y, drive.LEVER_Z]
    rod_point = _world(
        rod_origin, drive.LIFT_ROD_ROWS, [0.0, 0.0, ROD_PIN_HOLE_FROM_END]
    )
    lever_point = _world(lever_origin, drive.LEVER_ROWS, [0.0, 0.0, PIN_HOLE_Z])
    rod_dir = drive.LIFT_ROD_ROWS[0]
    lever_dir = drive.LEVER_ROWS[0]

    cross = [
        rod_dir[1] * lever_dir[2] - rod_dir[2] * lever_dir[1],
        rod_dir[2] * lever_dir[0] - rod_dir[0] * lever_dir[2],
        rod_dir[0] * lever_dir[1] - rod_dir[1] * lever_dir[0],
    ]
    assert math.hypot(*cross) < 1e-9
    assert all(math.isclose(a, b, abs_tol=1e-9) for a, b in zip(rod_point, lever_point))


def test_rod_phase_leaves_the_cams_parked_ecc_down() -> None:
    # The rod carries LEVER_TILT_DEG of phase; the cams must not: their world
    # rows stay the identity the park-gap and engage solves assume, tied back
    # to the rod by the same angle, and the freed spin's rest dihedral moves
    # by exactly that phase.
    identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    assert drive.PINION_CAM_ROWS == identity
    assert math.isclose(drive.CAM_ROD_PHASE_DEG, drive.LEVER_TILT_DEG, abs_tol=1e-9)
    assert math.isclose(
        drive.LIFT_ROD_PARK_DEG, 90.0 + drive.LEVER_TILT_DEG, abs_tol=1e-9
    )
    assert math.isclose(drive._PARK_GAP, 0.1606, abs_tol=5e-4)


# Ruling (c) worst-case stack (user, 2026-09-24).  Physical end play is ONE
# feeler setting, P = 0.25 +/- 0.10, shared by the four axial gaps (front
# block/strap g_f, strap/drum g_df, drum/strap g_db, strap/back block g_b), each
# >= 0; the saved pose is the fit-up vertex, all of P at the front block.  The
# lift rod is captured on the front block between the lever hub and the front
# cam collar, whose feeler leaves the same 0.10..0.35 of rod play.  Every
# quantity below is linear in the gaps, so the extremes sit at the vertices
# swept here.
_P_MAX = FITUP.FRONT_BLOCK_FEELER + FITUP.FRONT_BLOCK_FEELER_BAND
_ROD_PLAY_MAX = FITUP.FRONT_BLOCK_FEELER + FITUP.FRONT_BLOCK_FEELER_BAND
_BACK_CAM_SET_ERR = 0.5  # the back collar is set to its pin by eye


def _strap_t_band() -> tuple[float, float]:
    from pinion_bracket_spec import THICKNESS_BAND

    return (drive.STRAP_T - THICKNESS_BAND, drive.STRAP_T + THICKNESS_BAND)


def test_j19_keeps_two_thirds_face_at_the_worst_stack() -> None:
    # The drum's back end is located from the back block through the back
    # strap: worst when the strap is thickest and all the play sits behind the
    # drum.  Floor 2.0 of the 3.0 face (Main, 2026-09-24: lightly loaded train).
    g19_front = drive.Z_DRUM0 + 19 * drive.Z_PITCH - drive.DRUM_FACE / 2.0
    g19_back = g19_front + drive.DRUM_FACE
    worst = min(
        min(drive.BLOCK_BACK_Z0 - t - g, g19_back) - g19_front
        for t in _strap_t_band()
        for g in (0.0, _P_MAX)
    )
    assert worst >= 2.0, worst
    assert math.isclose(worst, 2.126, abs_tol=5e-3)
    # j = 0 at the front: the drum's front end never uncovers gear 0.
    g0_front = drive.Z_DRUM0 - drive.DRUM_FACE / 2.0
    face_min = drive.APINION_DRUM_LEN - 0.8
    for t in _strap_t_band():
        assert drive.BLOCK_BACK_Z0 - t - face_min <= g0_front - 1.0


def test_follower_pins_stay_on_their_collars_at_the_worst_stack() -> None:
    import itertools

    # Front: collar set off the front block's inner face (rod-play gap c),
    # strap one gap g_f off it; the pin rides the strap's mid-plane.
    front = [
        g_f + t / 2.0 - c
        for g_f, t, c in itertools.product(
            (0.0, _P_MAX), _strap_t_band(), (0.0, _ROD_PLAY_MAX)
        )
    ]
    # Back: collar set to its pin at the model station with the cluster hard
    # back; the strap then moves forward by g_b, the rod by up to its play.
    back = [
        drive.CAM_PIN_STATION[1] - g_b + dr + e
        for g_b, dr, e in itertools.product(
            (0.0, _P_MAX), (0.0, _ROD_PLAY_MAX), (-_BACK_CAM_SET_ERR, _BACK_CAM_SET_ERR)
        )
    ]
    assert math.isclose(drive.CAM_PIN_STATION[0], drive.STRAP_T / 2.0)
    for stations in (front, back):
        assert min(stations) >= 1.0, stations
        assert max(stations) <= drive.CAM_LEN - 1.0, stations
    # The back collar, set to its pin with the cluster hard back, never
    # reaches the back block (the rod only moves forward from there).
    for t in _strap_t_band():
        collar_back = (
            drive.BLOCK_BACK_Z0 - t / 2.0 + (drive.CAM_LEN - drive.CAM_PIN_STATION[1])
        )
        assert drive.BLOCK_BACK_Z0 - collar_back >= 1.0
    # The model front collar is flush with the strap's outer face, one feeler
    # off the block.
    assert math.isclose(
        drive.CAM_Z0[0] - (drive.BLOCK_FRONT_Z0 + drive.BLOCK_DEPTH), 0.25, abs_tol=1e-9
    )
