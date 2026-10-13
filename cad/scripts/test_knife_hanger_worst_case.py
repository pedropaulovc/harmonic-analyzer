"""drawing-guidelines.md rule 17 (walls and webs) worst case of the #6-32 knife hanger (MHA-VN-024 in MHA-SM-002,
keyed by MHA-VN-051), read from the real spec and assembly constants.

The retired 1/2-13 hanger broke its tap-drill point into the knife bore crown
and needed a drawing exception; every number here is judged at the printed
bands (cad/docs/drawing-guidelines.md rule 17 (walls and webs)), and the old geometry is
run through the same web formula to prove it discriminates.  SolidWorks-free.
"""

from __future__ import annotations

import math

import pytest

import _interference_contracts
import build_fr_top_frame
import build_sm_knife_mount
import build_sm_summing_assembly as asm
import fr_top_frame_spec as top_frame
import sm_knife_mount_spec as knife_mount
import sm_summing_lever_spec as lever
import vn_knife_hanger_stud_spec as screw
import vn_knife_mount_dowel_spec as dowel
from _hole_spec import CLEARANCE_MM, TAP_DRILL_MM, THREAD_MAJOR_MM


def test_the_tap_point_leaves_the_web_over_the_bore_crown() -> None:
    assert knife_mount.STUD_TAP_WEB_MIN == 2.0
    # 14.62 - 0.10 - 0.015 - 11.67 - 0.813 at the spec's 14.87 top: the
    # reamed bore's +0.03 and the drill depth's explicit 11.20 +/-0.47.
    assert knife_mount.STUD_TAP_DRILL_DEPTH_MAX == pytest.approx(11.67)
    assert knife_mount.STUD_TAP_WEB_WORST == pytest.approx(2.022, abs=5e-4)
    assert knife_mount.STUD_TAP_WEB_WORST >= knife_mount.STUD_TAP_WEB_MIN
    # The build's exact derived top (14.866) is what gets cut: 2.018.
    built = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        knife_mount.STUD_TAP_DRILL_DEPTH,
        knife_mount.STUD_TAP_DIA,
    )
    assert built == pytest.approx(2.018, abs=5e-4)
    assert built >= knife_mount.STUD_TAP_WEB_MIN
    # The band is the loosest that fits: 0.01 more and the shallowest drill
    # (10.72) runs under one pitch past the deepest thread (9.93); 0.02 more
    # and the deepest drill (11.69) breaks the 2.0 web at the built top.
    wider = knife_mount.STUD_TAP_DRILL_DEPTH_BAND + 0.01
    deepest_thread = (
        knife_mount.STUD_TAP_THREAD_DEPTH + knife_mount.STUD_TAP_THREAD_DEPTH_BAND
    )
    assert (
        knife_mount.STUD_TAP_DRILL_DEPTH - wider - deepest_thread
        < knife_mount.STUD_PITCH
    )
    assert (
        knife_mount.tap_web_worst(
            build_sm_knife_mount.BLK_TOP,
            knife_mount.STUD_TAP_DRILL_DEPTH,
            knife_mount.STUD_TAP_DIA,
            drill_band=wider + 0.01,
        )
        < knife_mount.STUD_TAP_WEB_MIN
    )


def test_the_tap_drill_runs_a_pitch_past_the_full_thread() -> None:
    # Machinist review B2: a bottoming tap needs the drill to run past the
    # full thread.  Shallowest drill (10.73) less deepest thread (9.93):
    # 0.80, at least one 32 TPI pitch (0.794).  The thread is at the title
    # block's general .XX (2026-10-10 ruling); the drill carries the loosest
    # band the web and the runout leave (0.964 of room, under .XX's 1.02).
    assert knife_mount.STUD_TAP_THREAD_DEPTH == 9.42
    assert knife_mount.STUD_TAP_THREAD_DEPTH_BAND == knife_mount._XX == 0.51
    assert knife_mount.STUD_TAP_DRILL_DEPTH == 11.2
    assert knife_mount.STUD_TAP_DRILL_DEPTH_BAND == 0.47
    assert knife_mount.STUD_TAP_RUNOUT_MIN == pytest.approx(0.80)
    assert knife_mount.STUD_TAP_RUNOUT_MIN == pytest.approx(
        knife_mount.STUD_TAP_DRILL_DEPTH
        - knife_mount.STUD_TAP_DRILL_DEPTH_BAND
        - knife_mount.STUD_TAP_THREAD_DEPTH
        - knife_mount.STUD_TAP_THREAD_DEPTH_BAND
    )
    assert knife_mount.STUD_PITCH == pytest.approx(25.4 / 32)
    assert knife_mount.STUD_TAP_RUNOUT_MIN >= knife_mount.STUD_PITCH


def test_the_retired_half_inch_tap_fails_the_same_web_formula() -> None:
    # 1/2-13 x 12.0 blind under the old 14.62 top (MOUNT_GAP 0.25): the drill
    # point broke 0.85 into the crown nominally, -1.71 at the .XX bands its
    # drill depth and bore printed.
    old = knife_mount.tap_web_worst(
        14.62,
        12.0,
        TAP_DRILL_MM["1/2-13"],
        drill_band=knife_mount._XX,
        bore_oversize=knife_mount._XX,
    )
    assert old == pytest.approx(-1.714, abs=5e-4)
    assert old < knife_mount.STUD_TAP_WEB_MIN


def test_the_screw_reach_holds_engagement_and_stays_in_the_thread() -> None:
    asm._assert_knife_hanger_stack()
    assert asm.MOUNT_GAP == 0.0
    assert asm.HANGER_SEAT_Y == pytest.approx(1029.7)
    assert asm.HANGER_STUD_Y == pytest.approx(991.6)
    assert asm.HANGER_REACH == pytest.approx(8.10)
    assert asm.HANGER_REACH_MIN == pytest.approx(6.284)
    assert asm.HANGER_REACH_MAX == pytest.approx(8.90)
    # Engagement: r_min - P >= 1.5 D, 5.49 >= 5.258.
    assert asm.HANGER_ENGAGEMENT_MIN == pytest.approx(
        asm.HANGER_REACH_MIN - screw.PITCH
    )
    assert asm.HANGER_ENGAGEMENT_MIN == pytest.approx(5.49, abs=5e-3)
    assert asm.HANGER_ENGAGEMENT_FLOOR == pytest.approx(1.5 * screw.SHANK_DIA)
    assert asm.HANGER_ENGAGEMENT_MIN >= asm.HANGER_ENGAGEMENT_FLOOR
    # Tip: r_max under the shallowest full thread, 8.90 <= 8.91 (0.01 clear);
    # the screw (91251A157, 1-1/2) is unchanged.
    assert knife_mount.STUD_TAP_THREAD_DEPTH_MIN == pytest.approx(8.91)
    assert asm.HANGER_REACH_MAX <= knife_mount.STUD_TAP_THREAD_DEPTH_MIN
    assert asm.HANGER_TIP_CLEARANCE == pytest.approx(0.01)
    # The partial thread covers the longest reach: 19.05 >= 8.90.
    assert screw.THREAD_LENGTH >= asm.HANGER_REACH_MAX
    # The screw clears the crossbar's #6 loose hole: 4.699 - 3.505.
    assert asm.HANGER_SCREW_CLEARANCE == pytest.approx(1.194, abs=5e-4)


def test_the_dowel_presses_deep_enough_and_never_bottoms_the_slip_hole() -> None:
    assert dowel.SLIP_DEPTH_CLEARANCE_MIN == pytest.approx(0.596)
    assert dowel.SLIP_DEPTH_CLEARANCE_MIN > 0.0
    assert dowel.PRESS_ENGAGEMENT_D_MIN == pytest.approx(2.60, abs=5e-3)
    assert dowel.PRESS_ENGAGEMENT_D_MIN >= dowel.PRESS_ENGAGEMENT_MIN_D == 1.5
    assert knife_mount.PIN_PRESS_INTERFERENCE[0] > 0.0
    # Both parts' stations are the dowel pair's, and the assembly seats the
    # pair there, the -X (slot) pin first.
    assert dowel.PER_MOUNT == 2 and dowel.QUANTITY == 4
    pair = (-dowel.HANGER_OFFSET, dowel.HANGER_OFFSET)
    assert knife_mount.PIN_HOLE_XS == top_frame.HANGER_PIN_XS == pair
    assert asm.KNIFE_DOWEL_X_OFFSETS == pair
    assert (top_frame.HANGER_SLOT_X, top_frame.HANGER_ROUND_X) == pair
    assert asm.KNIFE_DOWEL_Y == pytest.approx(
        asm.KNIFE_MOUNT_TOP_Y - knife_mount.PIN_HOLE_DEPTH
    )
    assert top_frame.HANGER_PIN_HOLE_DEPTH == dowel.SLIP_DEPTH


def test_the_slip_band_and_the_screw_float_absorb_the_dowel_stations() -> None:
    assert top_frame.HANGER_PIN_SLIP_CLEARANCE_MIN == pytest.approx(0.02738)
    assert top_frame.HANGER_PIN_SLIP_CLEARANCE_MAX == pytest.approx(0.09246)
    assert 0.02 <= top_frame.HANGER_PIN_SLIP_CLEARANCE_MIN
    assert top_frame.HANGER_PIN_SLIP_CLEARANCE_MAX <= 0.10
    assert top_frame.HANGER_SCREW_FLOAT == pytest.approx(0.597)
    # Option C: the Ø4.699 loose hole; the knife-mount tap is held Ø0.10 to
    # A|B.  Along X: 0.13 crossbar station + 0.065 half-span + 0.05 tap
    # zone + 0.046 slip; across: 0.13 + 0.05 + (0.046 + 0.046 + 0.025) / 2.
    assert knife_mount.STUD_TAP_POSITION_TOL == 0.10
    assert asm.HANGER_SCREW_MISMATCH_X == pytest.approx(0.29123)
    assert asm.HANGER_SCREW_MISMATCH_Z == pytest.approx(0.238730)
    assert asm.HANGER_SCREW_MISMATCH == pytest.approx(0.3766, abs=5e-4)
    # The hole is drilled from the underside, so its axis wanders up the
    # longest .X grip: tan 0.3 deg x 30.8 at the head end.
    assert asm.HANGER_SCREW_DRIFT == pytest.approx(
        math.tan(math.radians(top_frame.KEEPER_TAP_DRILL_WANDER_DEG))
        * (top_frame.HANGER_GRIP + top_frame.HANGER_GRIP_TOL)
    )
    assert asm.HANGER_SCREW_DRIFT == pytest.approx(0.1613, abs=5e-4)
    assert asm.HANGER_SCREW_FLOAT_SPARE == pytest.approx(0.0592, abs=5e-4)
    assert (
        asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT
        < top_frame.HANGER_SCREW_FLOAT
    )
    # The normal-fit Ø4.318 it replaced (float 0.4065) cannot take the drift.
    normal_float = (CLEARANCE_MM[("#6", "normal")] - screw.SHANK_DIA) / 2.0
    assert normal_float == pytest.approx(0.4065)
    assert asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT > normal_float


def test_the_slot_takes_up_the_dowel_pair_spacing() -> None:
    # Same slip width as the round hole, so the pin keeps its slip across it.
    assert top_frame.HANGER_SLOT_WIDTH == top_frame.HANGER_PIN_HOLE_DIA
    assert top_frame.HANGER_SLOT_WIDTH_BAND == top_frame.HANGER_PIN_HOLE_DIA_BAND
    # The slot stands BASIC 14.200 from its round hole, its centre +-0.13
    # along the slot, so the crossbar's stations drop out.  Travel either
    # way: 0.13 slot centre + 0.13 knife-mount span + 0.046 round-hole slip;
    # the shortest .XXX slot holds the largest pin.
    assert top_frame.HANGER_SLOT_FROM_ROUND == pytest.approx(14.2)
    assert top_frame.HANGER_SLOT_TRAVEL == pytest.approx(0.30623)
    assert top_frame.HANGER_SLOT_LENGTH_REQUIRED == pytest.approx(3.79508)
    assert (top_frame.HANGER_SLOT_LENGTH, top_frame.HANGER_SLOT_LENGTH_PLACES) == (
        4.20,
        3,
    )
    assert top_frame.HANGER_SLOT_LENGTH_TOL == 0.13
    shortest = top_frame.HANGER_SLOT_LENGTH - top_frame.HANGER_SLOT_LENGTH_TOL
    assert shortest - top_frame.HANGER_SLOT_LENGTH_REQUIRED == pytest.approx(0.27492)
    assert top_frame.HANGER_SLOT_DEPTH == top_frame.HANGER_PIN_HOLE_DEPTH


def test_the_crossbar_webs_hold_round_the_hole_and_the_slot() -> None:
    assert build_fr_top_frame.SLOT_X == pytest.approx(-22.1)
    assert build_fr_top_frame.PIN_HOLE_X == pytest.approx(-7.9)
    # Every wall at its print-worst less the drill drift each hole takes up
    # its depth (both enter from the underside): drawing-guidelines.md rule 17 (walls and webs)'s 2.0 holds.
    assert build_fr_top_frame.PIN_HOLE_BAR_WALL == pytest.approx(3.068, abs=5e-4)
    assert build_fr_top_frame.PIN_HOLE_SCREW_WALL == pytest.approx(2.801, abs=5e-4)
    # The longest .XXX slot (4.33) with its station at the round hole's
    # .XXX limit plus its own .XXX (0.26).
    assert top_frame.HANGER_SLOT_STATION_TOL == pytest.approx(0.26)
    assert build_fr_top_frame.SLOT_BAR_WALL == pytest.approx(2.408, abs=5e-4)
    assert build_fr_top_frame.SLOT_SCREW_WALL == pytest.approx(2.141, abs=5e-4)
    for wall in (
        build_fr_top_frame.PIN_HOLE_BAR_WALL,
        build_fr_top_frame.PIN_HOLE_SCREW_WALL,
        build_fr_top_frame.SLOT_BAR_WALL,
        build_fr_top_frame.SLOT_SCREW_WALL,
    ):
        assert wall >= 2.0
    assert build_fr_top_frame.SLOT_FLOOR_MARGIN == pytest.approx(18.0)


def test_the_slot_length_band_is_functional() -> None:
    # Codex review of 080fda97 asked for a one-place slot length.  The .XXX
    # band is what keeps both ends of the stack: at the title block's .XX or
    # .X band the shortest slot must still take the dowel's travel, so the
    # longest one cuts the wall to the screw clearance hole under drawing-guidelines.md rule 17 (walls and webs)'s
    # 2.0 target.
    wall_at_longest = (
        build_fr_top_frame.SLOT_SCREW_WALL
        + (top_frame.HANGER_SLOT_LENGTH + top_frame.HANGER_SLOT_LENGTH_TOL) / 2.0
    )
    walls = {}
    for places in (1, 2, 3):
        band = top_frame.PRINTED_LINEAR_BAND_MM[places]
        shortest_nominal = (
            math.ceil(
                round((top_frame.HANGER_SLOT_LENGTH_REQUIRED + band) * 10**places, 6)
            )
            / 10**places
        )
        walls[places] = wall_at_longest - (shortest_nominal + band) / 2.0
    assert walls[1] == pytest.approx(1.6065, abs=5e-4)
    assert walls[2] == pytest.approx(1.8965, abs=5e-4)
    assert max(walls[1], walls[2]) < 2.0 <= walls[3]
    assert walls[3] >= build_fr_top_frame.SLOT_SCREW_WALL


def test_the_dowel_pattern_frame_is_the_zone_the_stacks_were_derived_on() -> None:
    # The 2026-10-09 ruling: the pair's 2X ream carries ⌖Ø0.13 to A, its span
    # BASIC; each hole within 0.065 of true position, so the span varies by
    # the zone's Ø -- the 0.13 the .XXX span gave -- and every stack holds.
    zone = knife_mount.GEOMETRIC_TOLERANCES_MM["dowel hole pattern position"]
    assert zone == "0.13"
    assert knife_mount.PIN_HOLE_POSITION_TOL == 0.13
    assert knife_mount.PIN_HOLE_SPAN_TOL == dowel.SPAN_TOL == float(zone)
    assert knife_mount.PIN_HOLE_HALF_SPAN_TOL == pytest.approx(0.065)
    assert asm.HANGER_SCREW_MISMATCH == pytest.approx(0.3766, abs=5e-5)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(6.308, abs=5e-4)
    assert top_frame.HANGER_SLOT_LENGTH_REQUIRED == pytest.approx(3.795, abs=5e-4)
    # The conversion the ruling corrected: Ø0.23 (half-span 0.115) would
    # have stacked 0.416 against the 0.4065 float of the normal-fit Ø4.318
    # hole the crossbar then drilled.
    x_at_023 = (
        asm.HANGER_SCREW_MISMATCH_X - knife_mount.PIN_HOLE_HALF_SPAN_TOL + 0.23 / 2.0
    )
    assert math.hypot(x_at_023, asm.HANGER_SCREW_MISMATCH_Z) == pytest.approx(
        0.4164, abs=5e-4
    )
    normal_float = (CLEARANCE_MM[("#6", "normal")] - screw.SHANK_DIA) / 2.0
    assert math.hypot(x_at_023, asm.HANGER_SCREW_MISMATCH_Z) > normal_float


def test_the_knife_mount_webs_hold_round_both_dowel_holes() -> None:
    assert knife_mount.PIN_HOLE_SPAN == pytest.approx(14.2)
    assert knife_mount.PIN_HOLE_SPAN_TOL == 0.13
    assert knife_mount.PIN_HOLE_X_TOL == pytest.approx(0.115)
    # Machinist review B1: the +X hole located 5.40 .XX from the +X face,
    # the row 7.0 .X from the front face; the overall block at .X (25.0,
    # 29.6, 14.0) and the bore reamed +0.03/0.  Every web holds 2.0; the
    # binding one is the floor under the bore.
    assert knife_mount.BLK_HALF_X == 12.5
    assert knife_mount.PIN_HOLE_SIDE_DISTANCE == pytest.approx(5.40)
    assert knife_mount.PIN_HOLE_SIDE_TOL == knife_mount._XX
    assert knife_mount.HOLE_ROW_FACE_DISTANCE == 7.0
    assert knife_mount.HOLE_ROW_FACE_TOL == knife_mount._X
    assert knife_mount.BLOCK_SIZE_TOL == knife_mount._X
    assert knife_mount.BLOCK_HEIGHT_PRINTED == 29.6
    assert knife_mount.BORE_DIA_BAND == (0.03, 0.0)
    webs = {
        "dowel hole to +X face": (knife_mount.PIN_HOLE_SIDE_WEB, 3.3025),
        "dowel hole to -X face": (knife_mount.PIN_HOLE_FAR_SIDE_WEB, 2.3725),
        "dowel hole to Z faces": (knife_mount.PIN_HOLE_Z_WEB, 3.4324),
        "tap to Z faces": (knife_mount.STUD_TAP_Z_WALL, 3.4074),
        "bore to side faces": (knife_mount.BORE_SIDE_WEB, 5.01),
        "bore to bottom face": (knife_mount.BORE_BOTTOM_WALL, 2.065),
        "dowel hole to tap": (knife_mount.PIN_HOLE_TAP_WEB, 3.645),
        "dowel hole to bore": (knife_mount.PIN_HOLE_BORE_WEB, 5.5195),
    }
    for label, (web, expected) in webs.items():
        assert web == pytest.approx(expected, abs=5e-4), label
        assert web >= knife_mount.STUD_TAP_WEB_MIN, label
    assert min(web for web, _ in webs.values()) == knife_mount.BORE_BOTTOM_WALL


def test_the_knife_edge_keeps_five_degrees_of_rock_at_the_worst_case() -> None:
    # Ruling B: HEX_W 8.080 (.XXX), HEX_H 10.268 (.XXX); ridge 115.1 deg.
    assert (lever.HEX_W, lever.HEX_H, lever.HEX_BAND) == (8.080, 10.268, 0.13)
    assert lever.RIDGE_ANGLE_DEG == pytest.approx(115.137, abs=5e-3)
    # shortest span: atan(0.11746 / 14.07) = 0.478 deg; across the deepest
    # .X block, t = 14.8 tan + 0.05.
    assert asm.KNIFE_DOWEL_SPAN_MIN == pytest.approx(14.07)
    assert asm.KNIFE_MOUNT_YAW_DEG == pytest.approx(0.4783, abs=5e-4)
    assert asm.KNIFE_BORE_FAR_END_OFFSET == pytest.approx(0.1736, abs=5e-4)
    # W 8.21, H 10.138, the reamed bore's smallest R 6.0: 6.308 deg against
    # the 5.0 floor.
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(6.308, abs=5e-3)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG >= asm.KNIFE_FREE_ROCK_FLOOR_DEG == 5.0
    assert knife_mount.BORE_R_MIN == 6.0
    assert knife_mount.free_rock_deg(
        0.1736, hex_w=8.21, hex_h=10.138, r_bore=6.0
    ) == pytest.approx(6.308, abs=5e-3)
    # With the reamed bore the width ruling B replaced (8.653) still fails
    # the floor, and so does any width from 8.33 up; 8.090 now holds 6.25.
    for hex_w, holds in ((8.653, False), (8.33, False), (8.090, True)):
        rock = knife_mount.free_rock_deg(
            asm.KNIFE_BORE_FAR_END_OFFSET,
            hex_w=hex_w + lever.HEX_BAND,
            hex_h=lever.HEX_H - lever.HEX_BAND,
            r_bore=knife_mount.BORE_R_MIN,
        )
        assert (rock >= 5.0) is holds, hex_w
    # Nominal geometry, straight bore: 8.92 deg.
    assert knife_mount.KNIFE_FREE_ROCK_DEG == pytest.approx(8.924, abs=5e-3)
    assert math.isclose(
        lever.KNIFE_FACE_NORMAL[0] ** 2 + lever.KNIFE_FACE_NORMAL[1] ** 2, 1.0
    )


def test_the_summing_interference_rows_match_their_owners() -> None:
    # _interference_contracts keeps the knife-mount-owned terms as literals.
    assert _interference_contracts._KNIFE_HANGER_REACH == pytest.approx(
        asm.HANGER_REACH
    )
    assert _interference_contracts._KNIFE_DOWEL_HOLE_MIN == pytest.approx(
        knife_mount.PIN_HOLE_DIA + min(knife_mount.PIN_HOLE_DIA_BAND)
    )
    assert _interference_contracts._KNIFE_DOWEL_DIA_MAX == pytest.approx(dowel.DIA_MAX)
    assert _interference_contracts._KNIFE_DOWEL_PRESS_DEPTH == pytest.approx(
        dowel.PRESS_DEPTH
    )
    assert screw.THREAD == knife_mount.STUD_THREAD == "#6-32"
    assert THREAD_MAJOR_MM["#6-32"] == knife_mount.STUD_THREAD_MAJOR
    assert TAP_DRILL_MM["#6-32"] == knife_mount.STUD_TAP_DIA
