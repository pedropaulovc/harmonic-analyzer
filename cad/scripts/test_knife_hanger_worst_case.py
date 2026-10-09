"""Rule-12 worst case of the #6-32 knife hanger (MHA-VN-024 in MHA-SM-002,
keyed by MHA-VN-051), read from the real spec and assembly constants.

The retired 1/2-13 hanger broke its tap-drill point into the knife bore crown
and needed a drawing exception; every number here is judged at the printed
bands (cad/docs/drawing-simplicity-policy.md rule 12), and the old geometry is
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
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM


def test_the_tap_point_leaves_the_web_over_the_bore_crown() -> None:
    assert knife_mount.STUD_TAP_WEB_MIN == 2.0
    # 14.62 - 0.10 - 0.255 - 11.41 - 0.813 at the spec's 14.87 top.
    assert knife_mount.STUD_TAP_WEB_WORST == pytest.approx(2.042, abs=5e-4)
    assert knife_mount.STUD_TAP_WEB_WORST >= knife_mount.STUD_TAP_WEB_MIN
    # The build's exact derived top (14.866) is what gets cut: 2.038.
    built = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        knife_mount.STUD_TAP_DRILL_DEPTH,
        knife_mount.STUD_TAP_DIA,
    )
    assert built == pytest.approx(2.038, abs=5e-4)
    assert built >= knife_mount.STUD_TAP_WEB_MIN


def test_the_retired_half_inch_tap_fails_the_same_web_formula() -> None:
    # 1/2-13 x 12.0 blind under the old 14.62 top (MOUNT_GAP 0.25): the drill
    # point broke 0.85 into the crown nominally, -1.71 at the printed bands.
    old = knife_mount.tap_web_worst(14.62, 12.0, TAP_DRILL_MM["1/2-13"])
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
    # Tip: r_max under the shallowest full thread, 8.90 <= 9.19 (0.29 clear).
    assert knife_mount.STUD_TAP_THREAD_DEPTH_MIN == pytest.approx(9.19)
    assert asm.HANGER_REACH_MAX <= knife_mount.STUD_TAP_THREAD_DEPTH_MIN
    assert asm.HANGER_TIP_CLEARANCE == pytest.approx(0.29)
    # The partial thread covers the longest reach: 19.05 >= 8.90.
    assert screw.THREAD_LENGTH >= asm.HANGER_REACH_MAX
    # The screw clears the crossbar's #6 hole: 4.318 - 3.505.
    assert asm.HANGER_SCREW_CLEARANCE == pytest.approx(0.813, abs=5e-4)


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
    assert top_frame.HANGER_SCREW_FLOAT == pytest.approx(0.4065)
    # Option (b): the Ø4.318 hole stays; the knife-mount tap is held Ø0.10
    # to A|B.  Along X: 0.13 crossbar station + 0.065 half-span + 0.05 tap
    # zone + 0.046 slip; across: 0.13 + 0.05 + (0.046 + 0.046 + 0.025) / 2.
    assert knife_mount.STUD_TAP_POSITION_TOL == 0.10
    assert asm.HANGER_SCREW_MISMATCH_X == pytest.approx(0.29123)
    assert asm.HANGER_SCREW_MISMATCH_Z == pytest.approx(0.238730)
    assert asm.HANGER_SCREW_MISMATCH == pytest.approx(0.3766, abs=5e-4)
    assert asm.HANGER_SCREW_MISMATCH <= top_frame.HANGER_SCREW_FLOAT


def test_the_slot_takes_up_the_dowel_pair_spacing() -> None:
    # Same slip width as the round hole, so the pin keeps its slip across it.
    assert top_frame.HANGER_SLOT_WIDTH == top_frame.HANGER_PIN_HOLE_DIA
    assert top_frame.HANGER_SLOT_WIDTH_BAND == top_frame.HANGER_PIN_HOLE_DIA_BAND
    # Travel either way: 2 x 0.13 crossbar stations + 0.13 knife-mount span
    # + 0.046 round-hole slip; the shortest .XXX slot holds the largest pin.
    assert top_frame.HANGER_SLOT_TRAVEL == pytest.approx(0.43623)
    assert top_frame.HANGER_SLOT_LENGTH_REQUIRED == pytest.approx(4.05508)
    assert (top_frame.HANGER_SLOT_LENGTH, top_frame.HANGER_SLOT_LENGTH_PLACES) == (
        4.60,
        3,
    )
    shortest = top_frame.HANGER_SLOT_LENGTH - top_frame.HANGER_SLOT_LENGTH_TOL
    assert shortest - top_frame.HANGER_SLOT_LENGTH_REQUIRED == pytest.approx(0.41492)
    assert top_frame.HANGER_SLOT_DEPTH == top_frame.HANGER_PIN_HOLE_DEPTH


def test_the_crossbar_webs_hold_round_the_hole_and_the_slot() -> None:
    assert build_fr_top_frame.SLOT_X == pytest.approx(-21.35)
    assert build_fr_top_frame.PIN_HOLE_X == pytest.approx(-8.65)
    assert build_fr_top_frame.PIN_HOLE_BAR_WALL == pytest.approx(2.885, abs=5e-4)
    assert build_fr_top_frame.PIN_HOLE_SCREW_WALL == pytest.approx(2.376, abs=5e-4)
    assert build_fr_top_frame.SLOT_BAR_WALL == pytest.approx(2.155, abs=5e-4)
    assert build_fr_top_frame.SLOT_SCREW_WALL == pytest.approx(1.646, abs=5e-4)
    assert build_fr_top_frame.SLOT_FLOOR_MARGIN == pytest.approx(18.0)


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
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(5.038, abs=5e-4)
    assert top_frame.HANGER_SLOT_LENGTH_REQUIRED == pytest.approx(4.055, abs=5e-4)
    # The conversion the ruling corrected: Ø0.23 (half-span 0.115) would
    # stack 0.416 against the 0.4065 float.
    x_at_023 = (
        asm.HANGER_SCREW_MISMATCH_X - knife_mount.PIN_HOLE_HALF_SPAN_TOL + 0.23 / 2.0
    )
    assert math.hypot(x_at_023, asm.HANGER_SCREW_MISMATCH_Z) == pytest.approx(
        0.4164, abs=5e-4
    )
    assert (
        math.hypot(x_at_023, asm.HANGER_SCREW_MISMATCH_Z) > top_frame.HANGER_SCREW_FLOAT
    )


def test_the_knife_mount_webs_hold_round_both_dowel_holes() -> None:
    assert knife_mount.PIN_HOLE_SPAN == pytest.approx(12.7)
    assert knife_mount.PIN_HOLE_SPAN_TOL == 0.13
    assert knife_mount.PIN_HOLE_X_TOL == pytest.approx(0.115)
    assert knife_mount.PIN_HOLE_SIDE_WEB == pytest.approx(3.9325)
    assert knife_mount.PIN_HOLE_TAP_WEB == pytest.approx(2.895)
    assert knife_mount.PIN_HOLE_BORE_WEB == pytest.approx(4.951, abs=5e-4)
    for web in (
        knife_mount.PIN_HOLE_SIDE_WEB,
        knife_mount.PIN_HOLE_TAP_WEB,
        knife_mount.PIN_HOLE_BORE_WEB,
    ):
        assert web >= knife_mount.STUD_TAP_WEB_MIN


def test_the_knife_edge_keeps_five_degrees_of_rock_at_the_worst_case() -> None:
    # Ruling B: HEX_W 8.080 (.XXX), HEX_H 10.268 (.XXX); ridge 115.1 deg.
    assert (lever.HEX_W, lever.HEX_H, lever.HEX_BAND) == (8.080, 10.268, 0.13)
    assert lever.RIDGE_ANGLE_DEG == pytest.approx(115.137, abs=5e-3)
    # The pair yaws the block by the slot pin's worst offset over the
    # shortest span: atan(0.11746 / 12.57) = 0.535 deg; t = 14 tan + 0.05.
    assert asm.KNIFE_DOWEL_SPAN_MIN == pytest.approx(12.57)
    assert asm.KNIFE_MOUNT_YAW_DEG == pytest.approx(0.5354, abs=5e-4)
    assert asm.KNIFE_BORE_FAR_END_OFFSET == pytest.approx(0.1808, abs=5e-4)
    # W 8.21, H 10.138, R 5.745: 5.038 deg against the 5.0 floor.
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(5.038, abs=5e-3)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG >= asm.KNIFE_FREE_ROCK_FLOOR_DEG == 5.0
    assert knife_mount.free_rock_deg(
        0.1808, hex_w=8.21, hex_h=10.138, r_bore=5.745
    ) == pytest.approx(5.038, abs=5e-3)
    # The width it replaced and the next 0.01 up both fail the floor.
    for hex_w in (8.653, 8.090):
        assert (
            knife_mount.free_rock_deg(
                asm.KNIFE_BORE_FAR_END_OFFSET,
                hex_w=hex_w + lever.HEX_BAND,
                hex_h=lever.HEX_H - lever.HEX_BAND,
                r_bore=knife_mount.R_BORE - knife_mount.BORE_DIA_TOL / 2.0,
            )
            < 5.0
        )
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
    assert screw.THREAD == knife_mount.STUD_THREAD == "#6-32"
    assert THREAD_MAJOR_MM["#6-32"] == knife_mount.STUD_THREAD_MAJOR
    assert TAP_DRILL_MM["#6-32"] == knife_mount.STUD_TAP_DIA
