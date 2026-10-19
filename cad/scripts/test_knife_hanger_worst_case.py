"""Worst case of the cut #10-24 plain hex knife hanger (MHA-SM-VN-52
in MHA-SM-02, new SAE washer, keyed by MHA-SM-VN-53), from real spec constants.

The retired 1/2-13 hanger broke its tap-drill point into the knife bore crown
and needed a drawing exception. The current proof charges the printed depth,
diameter and toolpoint-angle limits under cad/docs/drawing-guidelines.md:
rule 17 (walls and webs), rule 18 (thread engagement) and rule 19 (absorb
stacks). Even the old nominal toolpoint calculation fails. SolidWorks-free.
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
import sm_vn_knife_hanger_stud_spec as screw
import sm_vn_knife_hanger_washer_spec as washer
import sm_vn_knife_mount_dowel_spec as dowel
from _hole_spec import CLEARANCE_MM, TAP_DRILL_MM, THREAD_MAJOR_MM
from _printed_tolerance import drilled_oversize_mm


def test_the_tap_point_leaves_the_web_over_the_bore_crown() -> None:
    assert knife_mount.STUD_TAP_WEB_MIN == 2.0
    # Reamed bore largest, axis highest, drill deepest, and the accepted
    # native toolpoint at its smallest included angle. The pilot proof
    # deliberately charges more diameter than the native accepted maximum.
    assert knife_mount.STUD_TAP_DIA == pytest.approx(3.797)
    assert knife_mount.STUD_TAP_DIA_BAND == pytest.approx((0.10, 0.0))
    assert knife_mount.STUD_TAP_DIA_ACCEPTED == pytest.approx(
        (0.1495 * 25.4, 0.1495 * 25.4 + 0.10), abs=1e-12
    )
    assert knife_mount.STUD_TAP_DIA_OVERSIZE == pytest.approx(
        max(knife_mount._XXX, drilled_oversize_mm())
    )
    assert knife_mount.STUD_TAP_DIA_OVERSIZE == pytest.approx(0.13)
    assert knife_mount.STUD_TAP_DIA_MAX == pytest.approx(3.927)
    assert knife_mount.STUD_TAP_DIA_MAX > max(knife_mount.STUD_TAP_DIA_ACCEPTED)
    assert knife_mount.STUD_TAP_POINT_ANGLE_DEG == pytest.approx(118.0)
    assert knife_mount.STUD_TAP_POINT_ANGLE_MIN_DEG == pytest.approx(117.0)
    point_height = 3.927 / (2.0 * math.tan(math.radians(117.0 / 2.0)))
    assert point_height == pytest.approx(1.2032343475)
    assert knife_mount.STUD_TAP_POINT_H == pytest.approx(point_height)
    assert knife_mount.STUD_TAP_DRILL_DEPTH_MAX == pytest.approx(11.29)
    # Spec mirror top 14.87: crown depth 14.62, less the position radius,
    # bore radius oversize, maximum cylindrical drill depth and point height.
    assert knife_mount.STUD_TAP_WEB_WORST == pytest.approx(
        14.62 - 0.10 - 0.015 - 11.29 - point_height
    )
    assert knife_mount.STUD_TAP_WEB_WORST == pytest.approx(2.0117656525)
    assert knife_mount.STUD_TAP_WEB_WORST >= knife_mount.STUD_TAP_WEB_MIN
    # Exact built top 14.866 is 0.004 lower than the spec mirror.
    built = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        knife_mount.STUD_TAP_DRILL_DEPTH,
        knife_mount.STUD_TAP_DIA,
    )
    assert built == pytest.approx(2.0077656525)
    assert build_sm_knife_mount._TAP_WEB_WORST == pytest.approx(built)
    assert built >= knife_mount.STUD_TAP_WEB_MIN
    # A 0.01 wider drill-depth band consumes the remaining functional web.
    assert (
        knife_mount.tap_web_worst(
            build_sm_knife_mount.BLK_TOP,
            knife_mount.STUD_TAP_DRILL_DEPTH,
            knife_mount.STUD_TAP_DIA,
            drill_band=knife_mount.STUD_TAP_DRILL_DEPTH_BAND + 0.01,
        )
        < knife_mount.STUD_TAP_WEB_MIN
    )


@pytest.mark.parametrize(
    ("drill_dia_oversize", "point_angle_deg"),
    [(0.0, 117.0), (0.13, 118.0), (0.0, 118.0)],
)
def test_omitting_pilot_oversize_or_point_angle_overstates_the_crown_web(
    drill_dia_oversize: float, point_angle_deg: float
) -> None:
    charged = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        knife_mount.STUD_TAP_DRILL_DEPTH,
        knife_mount.STUD_TAP_DIA,
    )
    undercharged = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        knife_mount.STUD_TAP_DRILL_DEPTH,
        knife_mount.STUD_TAP_DIA,
        drill_dia_oversize=drill_dia_oversize,
        point_angle_deg=point_angle_deg,
    )
    assert undercharged > charged


def test_previous_drill_depth_fails_when_pilot_and_point_limits_are_charged() -> None:
    charged = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        11.29,
        knife_mount.STUD_TAP_DIA,
    )
    optimistic = knife_mount.tap_web_worst(
        build_sm_knife_mount.BLK_TOP,
        11.29,
        knife_mount.STUD_TAP_DIA,
        drill_dia_oversize=0.0,
        point_angle_deg=118.0,
    )
    # The old apparent pass used the nominal pilot and exact nominal angle;
    # it is not an accepted physical worst case.
    assert optimistic == pytest.approx(2.02026729, abs=5e-6)
    assert optimistic >= knife_mount.STUD_TAP_WEB_MIN
    assert charged == pytest.approx(1.9577656525)
    assert charged < knife_mount.STUD_TAP_WEB_MIN


def test_the_tap_drill_runs_a_pitch_past_the_full_thread() -> None:
    # Full thread keeps its explicit functional ±0.13 at two printed places;
    # the drill has its explicit depth band. Nominal runout 1.59 >=1.5P.
    assert knife_mount.STUD_TAP_THREAD_DEPTH == 9.65
    assert knife_mount.STUD_TAP_THREAD_DEPTH_BAND == knife_mount._XXX == 0.13
    assert knife_mount.STUD_TAP_THREAD_DEPTH_MIN == pytest.approx(9.52)
    assert knife_mount.STUD_TAP_DRILL_DEPTH == 11.24
    assert knife_mount.STUD_TAP_DRILL_DEPTH_BAND == 0.05
    assert knife_mount.STUD_TAP_RUNOUT == pytest.approx(1.59)
    assert knife_mount.STUD_TAP_RUNOUT >= 1.5 * knife_mount.STUD_PITCH
    assert knife_mount.STUD_TAP_RUNOUT_MIN == pytest.approx(1.41)
    assert knife_mount.STUD_TAP_RUNOUT_MIN == pytest.approx(
        knife_mount.STUD_TAP_DRILL_DEPTH
        - knife_mount.STUD_TAP_DRILL_DEPTH_BAND
        - knife_mount.STUD_TAP_THREAD_DEPTH
        - knife_mount.STUD_TAP_THREAD_DEPTH_BAND
    )
    assert knife_mount.STUD_PITCH == pytest.approx(25.4 / 24)
    assert knife_mount.STUD_TAP_RUNOUT_MIN >= knife_mount.STUD_PITCH


def test_the_retired_half_inch_tap_fails_the_same_web_formula() -> None:
    # Historical optimistic calculation, NOT an accepted stock bound: nominal
    # 1/2-13 pilot at exact 118 degrees still broke into the crown under the
    # old 14.62 top (MOUNT_GAP 0.25), even before charging pilot and angle bands.
    old = knife_mount.tap_web_worst(
        14.62,
        12.0,
        TAP_DRILL_MM["1/2-13"],
        drill_band=knife_mount._XX,
        bore_oversize=knife_mount._XX,
        drill_dia_oversize=0.0,
        point_angle_deg=118.0,
    )
    assert old == pytest.approx(-1.714, abs=5e-4)
    assert old < knife_mount.STUD_TAP_WEB_MIN


def test_the_screw_reach_holds_engagement_and_stays_in_the_thread() -> None:
    asm._assert_knife_hanger_stack()
    assert asm.MOUNT_GAP == 0.0
    assert asm.CROSSBAR_TOP_Y == pytest.approx(1036.2)
    assert asm.HANGER_WASHER_Y == pytest.approx(1036.2)
    assert asm.HANGER_UNDERHEAD_Y == pytest.approx(1037.4827)
    assert asm.HANGER_STUD_Y == pytest.approx(990.7827)
    assert asm.HANGER_REACH == pytest.approx(8.9173)
    # MHA-SM-00 cuts each bolt to its measured stack plus 8.92 +/-0.15.
    assert asm.HANGER_REACH_MIN == pytest.approx(8.77)
    assert asm.HANGER_REACH_MAX == pytest.approx(9.07)
    # Cut-tip lead costs one incomplete pitch: 7.7116667 >= 1.5D =7.239.
    assert asm.HANGER_ENGAGEMENT_MIN == pytest.approx(
        asm.HANGER_REACH_MIN - screw.INCOMPLETE_TIP_LEN_MAX
    )
    assert screw.INCOMPLETE_TIP_LEN_MAX == screw.PITCH
    assert asm.HANGER_ENGAGEMENT_MIN == pytest.approx(7.7116666667)
    assert asm.HANGER_ENGAGEMENT_FLOOR == pytest.approx(1.5 * screw.SHANK_DIA)
    assert asm.HANGER_ENGAGEMENT_MIN >= asm.HANGER_ENGAGEMENT_FLOOR
    assert asm.HANGER_ENGAGEMENT_FLOOR == pytest.approx(7.239)
    # Full tap's shallowest limit stays 0.45 beyond the longest reach.
    assert knife_mount.STUD_TAP_THREAD_DEPTH_MIN == pytest.approx(9.52)
    assert asm.HANGER_REACH_MAX <= knife_mount.STUD_TAP_THREAD_DEPTH_MIN
    assert asm.HANGER_TIP_CLEARANCE == pytest.approx(0.45)
    # Modified-part incoming inspection proves this cut tail's full form;
    # catalogue "fully threaded" is not assumed to specify thread-to-head.
    assert screw.THREAD_LENGTH_MIN == pytest.approx(10.62)
    assert screw.FULL_FORM_TAIL_MIN == pytest.approx(9.5616666667)
    assert asm.HANGER_THREAD_SPARE == pytest.approx(0.4916666667)
    assert (
        screw.THREAD_LENGTH_MIN - screw.INCOMPLETE_TIP_LEN_MAX >= asm.HANGER_REACH_MAX
    )
    assert asm.HANGER_SCREW_CLEARANCE == pytest.approx(1.219)
    assert washer.THICKNESS == pytest.approx(1.2827)


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
    assert top_frame.HANGER_CLEARANCE_DIA == CLEARANCE_MM[("#10", "loose")] == 6.045
    # The hole's explicit native unilateral band prevents a smaller .XXX
    # general-band hole from silently consuming the radial float budget.
    assert top_frame.HANGER_CLEARANCE_DIA_BAND == (0.13, 0.0)
    assert top_frame.HANGER_CLEARANCE_DIA_MIN == pytest.approx(6.045)
    assert top_frame.HANGER_CLEARANCE_DIA_MAX == pytest.approx(6.175)
    assert top_frame.HANGER_SCREW_FLOAT == pytest.approx(
        (top_frame.HANGER_CLEARANCE_DIA_MIN - screw.SHANK_DIA) / 2.0
    )
    assert top_frame.HANGER_SCREW_FLOAT == pytest.approx(0.6095)
    # Along X: 0.13 crossbar station + 0.065 half-span + 0.075 tap zone
    # +0.04623 slip; across: 0.13 +0.075 +(0.04623+0.04623+0.025)/2.
    assert knife_mount.STUD_TAP_POSITION_TOL == 0.15
    assert asm.HANGER_SCREW_MISMATCH_X == pytest.approx(0.31623)
    assert asm.HANGER_SCREW_MISMATCH_Z == pytest.approx(0.26373)
    assert asm.HANGER_SCREW_MISMATCH == pytest.approx(0.4117704770864468, abs=1e-12)
    # Drift reaches the hole's top end at the faced top, over the longest
    # printed grip (36.50 + 0.51), not the retired one-place cast band.
    assert asm.HANGER_SCREW_DRIFT == pytest.approx(
        math.tan(math.radians(top_frame.KEEPER_TAP_DRILL_WANDER_DEG))
        * (top_frame.HANGER_GRIP + top_frame.HANGER_GRIP_TOL)
    )
    assert asm.HANGER_SCREW_DRIFT == pytest.approx(0.1937856777669617, abs=1e-12)
    assert asm.HANGER_SCREW_FLOAT_SPARE == pytest.approx(
        0.003943845146591629, abs=1e-12
    )
    assert (
        asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT
        < top_frame.HANGER_SCREW_FLOAT
    )

    # The tap zone is the largest two-place zone the float admits (R4 asked
    # Ø0.25): the stack, each mismatch carrying the zone's radius, closes at
    # Ø0.1556; Ø0.16 and Ø0.25 overrun the float.
    def spare_at(zone: float) -> float:
        shift = (zone - knife_mount.STUD_TAP_POSITION_TOL) / 2.0
        mismatch = math.hypot(
            asm.HANGER_SCREW_MISMATCH_X + shift, asm.HANGER_SCREW_MISMATCH_Z + shift
        )
        return top_frame.HANGER_SCREW_FLOAT - mismatch - asm.HANGER_SCREW_DRIFT

    assert spare_at(0.15) == pytest.approx(asm.HANGER_SCREW_FLOAT_SPARE, abs=1e-12)
    assert spare_at(0.16) == pytest.approx(-0.0030989127536319994, abs=1e-12)
    assert spare_at(0.25) == pytest.approx(-0.06652102051985437, abs=1e-12)
    assert spare_at(0.16) < 0.0 and spare_at(0.25) < 0.0
    x0 = asm.HANGER_SCREW_MISMATCH_X - knife_mount.STUD_TAP_POSITION_TOL / 2.0
    z0 = asm.HANGER_SCREW_MISMATCH_Z - knife_mount.STUD_TAP_POSITION_TOL / 2.0
    reach = top_frame.HANGER_SCREW_FLOAT - asm.HANGER_SCREW_DRIFT
    half_zone_max = (
        -(x0 + z0) + math.sqrt((x0 + z0) ** 2 - 2.0 * (x0**2 + z0**2 - reach**2))
    ) / 2.0
    assert 2.0 * half_zone_max == pytest.approx(0.1556000271700153, abs=1e-12)
    assert spare_at(2.0 * half_zone_max) == pytest.approx(0.0, abs=1e-12)
    assert 0.15 <= 2.0 * half_zone_max < 0.16
    # Negative control: inheriting the general symmetric .XXX hole band
    # would allow an undersize hole that fails the very same float proof.
    undersize_float = (
        top_frame.HANGER_CLEARANCE_DIA
        - top_frame.PRINTED_LINEAR_BAND_MM[3]
        - screw.SHANK_DIA
    ) / 2.0
    assert undersize_float == pytest.approx(0.5445)
    assert asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT > undersize_float
    # Standard normal-fit #10 clearance cannot take this complete mismatch.
    normal_float = (CLEARANCE_MM[("#10", "normal")] - screw.SHANK_DIA) / 2.0
    assert normal_float == pytest.approx(0.3935)
    assert asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT > normal_float


def test_the_slot_takes_up_the_dowel_pair_spacing() -> None:
    # Same slip width as the round hole, so the pin keeps its slip across it.
    assert top_frame.HANGER_SLOT_WIDTH == top_frame.HANGER_PIN_HOLE_DIA
    assert top_frame.HANGER_SLOT_WIDTH_BAND == top_frame.HANGER_PIN_HOLE_DIA_BAND
    # The slot stands BASIC 15.264 from its round hole, its centre +-0.13
    # along the slot, so the crossbar's stations drop out.  Travel either
    # way: 0.13 slot centre + 0.13 knife-mount span + 0.046 round-hole slip;
    # the shortest .XXX slot holds the largest pin.
    assert top_frame.HANGER_SLOT_FROM_ROUND == pytest.approx(15.264)
    assert top_frame.HANGER_SLOT_TRAVEL == pytest.approx(0.30623)
    assert top_frame.HANGER_SLOT_LENGTH_REQUIRED == pytest.approx(3.79508)
    assert (top_frame.HANGER_SLOT_LENGTH, top_frame.HANGER_SLOT_LENGTH_PLACES) == (
        3.95,
        3,
    )
    assert top_frame.HANGER_SLOT_LENGTH_TOL == 0.13
    shortest = top_frame.HANGER_SLOT_LENGTH - top_frame.HANGER_SLOT_LENGTH_TOL
    assert shortest - top_frame.HANGER_SLOT_LENGTH_REQUIRED == pytest.approx(0.02492)
    assert top_frame.HANGER_SLOT_DEPTH == top_frame.HANGER_PIN_HOLE_DEPTH


def test_the_crossbar_webs_hold_round_the_hole_and_the_slot() -> None:
    assert build_fr_top_frame.SLOT_X == pytest.approx(-22.632)
    assert build_fr_top_frame.PIN_HOLE_X == pytest.approx(-7.368)
    assert build_fr_top_frame.BAR_X1 - build_fr_top_frame.BAR_X0 == pytest.approx(25.0)
    assert (build_fr_top_frame.BAR_X1 + build_fr_top_frame.BAR_X0) / 2.0 == -15.0
    assert build_fr_top_frame.HANGER_BAR_HALF_WIDTH_MIN == pytest.approx(12.1)
    assert top_frame.HANGER_CROSSBAR_CENTER_TOL == pytest.approx(0.05)
    # Every wall at its print-worst less the drill drift each hole takes up
    # its depth (both enter from the underside): drawing-guidelines.md
    # rule 17 (walls and webs)'s 2.0 target holds.
    assert build_fr_top_frame.PIN_HOLE_BAR_WALL == pytest.approx(2.585979, abs=5e-6)
    assert build_fr_top_frame.PIN_HOLE_SCREW_WALL == pytest.approx(
        2.645457488, abs=5e-6
    )
    # Shortest .X bar width, functional 0.10 centring zone, and longest
    # .XXX slot (4.08) at its combined station limit (0.26), both drifted.
    assert top_frame.HANGER_SLOT_STATION_TOL == pytest.approx(0.26)
    assert build_fr_top_frame.SLOT_BAR_WALL == pytest.approx(2.050979, abs=5e-6)
    assert build_fr_top_frame.SLOT_SCREW_WALL == pytest.approx(2.110457488, abs=5e-6)
    for wall in (
        build_fr_top_frame.PIN_HOLE_BAR_WALL,
        build_fr_top_frame.PIN_HOLE_SCREW_WALL,
        build_fr_top_frame.SLOT_BAR_WALL,
        build_fr_top_frame.SLOT_SCREW_WALL,
    ):
        assert wall >= 2.0
    # Shortest finished grip (36.50 - 0.51) less the deepest slot floor 12.8.
    assert build_fr_top_frame.SLOT_FLOOR_MARGIN == pytest.approx(23.19)


def test_the_slot_length_band_is_functional() -> None:
    # The .XXX band is functional: the shortest slot must absorb the dowel
    # travel while its longest end preserves the OUTER crossbar wall.
    # Both the 25.0 overall .X width and 0.05 centring band enter that wall,
    # keeping drawing-guidelines.md rule 17 (walls and webs)'s 2.0 target.
    wall_at_longest = (
        build_fr_top_frame.SLOT_BAR_WALL
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
    assert walls[1] == pytest.approx(1.390979, abs=5e-6)
    assert walls[2] == pytest.approx(1.680979, abs=5e-6)
    assert max(walls[1], walls[2]) < 2.0 <= walls[3]
    assert walls[3] >= build_fr_top_frame.SLOT_BAR_WALL


def test_the_dowel_pattern_frame_is_the_zone_the_stacks_were_derived_on() -> None:
    # The 2026-10-09 ruling: the pair's 2X ream carries ⌖Ø0.13 to A, its span
    # BASIC; each hole within 0.065 of true position, so the span varies by
    # the zone's Ø -- the 0.13 the .XXX span gave -- and every stack holds.
    zone = knife_mount.GEOMETRIC_TOLERANCES_MM["dowel hole pattern position"]
    assert zone == "0.13"
    assert knife_mount.PIN_HOLE_POSITION_TOL == 0.13
    assert knife_mount.PIN_HOLE_SPAN_TOL == dowel.SPAN_TOL == float(zone)
    assert knife_mount.PIN_HOLE_HALF_SPAN_TOL == pytest.approx(0.065)
    assert asm.HANGER_SCREW_MISMATCH == pytest.approx(0.41177, abs=5e-5)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(6.636235, abs=5e-6)
    assert top_frame.HANGER_SLOT_LENGTH_REQUIRED == pytest.approx(3.795, abs=5e-4)
    # Enlarging the pattern zone to Ø0.23 would consume more screw float
    # even before the hole's deep-drill drift is charged.
    x_at_023 = (
        asm.HANGER_SCREW_MISMATCH_X - knife_mount.PIN_HOLE_HALF_SPAN_TOL + 0.23 / 2.0
    )
    assert math.hypot(x_at_023, asm.HANGER_SCREW_MISMATCH_Z) == pytest.approx(
        0.4513, abs=5e-4
    )
    normal_float = (CLEARANCE_MM[("#10", "normal")] - screw.SHANK_DIA) / 2.0
    assert math.hypot(x_at_023, asm.HANGER_SCREW_MISMATCH_Z) > normal_float


def test_the_knife_mount_webs_hold_round_both_dowel_holes() -> None:
    assert knife_mount.PIN_HOLE_SPAN == pytest.approx(15.264)
    assert knife_mount.PIN_HOLE_SPAN_TOL == 0.13
    assert knife_mount.PIN_HOLE_X_TOL == pytest.approx(0.14)
    # Same face-location scheme, minimally widened to 25.4 at functional .X;
    # the +X hole stands 5.068 .XX from its face, the row 7.0 .X from front.
    assert knife_mount.BLK_HALF_X == 12.7
    assert knife_mount.PIN_HOLE_SIDE_DISTANCE == pytest.approx(5.068)
    assert knife_mount.PIN_HOLE_SIDE_TOL == knife_mount._XX
    assert knife_mount.HOLE_ROW_FACE_DISTANCE == 7.0
    assert knife_mount.HOLE_ROW_FACE_TOL == knife_mount._X
    assert knife_mount.BLOCK_SIZE_TOL == knife_mount._X
    assert knife_mount.BLOCK_HEIGHT_PRINTED == 29.6
    assert knife_mount.BORE_DIA_BAND == (0.03, 0.0)
    webs = {
        "dowel hole to +X face": (knife_mount.PIN_HOLE_SIDE_WEB, 2.9705),
        "dowel hole to -X face": (knife_mount.PIN_HOLE_FAR_SIDE_WEB, 2.0405),
        "dowel hole to Z faces": (knife_mount.PIN_HOLE_Z_WEB, 3.413797),
        "tap to Z faces": (knife_mount.STUD_TAP_Z_WALL, 2.712648),
        "bore to side faces": (knife_mount.BORE_SIDE_WEB, 5.21),
        "bore to bottom face": (knife_mount.BORE_BOTTOM_WALL, 2.065),
        "dowel hole to tap": (knife_mount.PIN_HOLE_TAP_WEB, 3.4915),
        "dowel hole to bore": (knife_mount.PIN_HOLE_BORE_WEB, 5.775544),
    }
    for label, (web, expected) in webs.items():
        assert web == pytest.approx(expected, abs=5e-4), label
        assert web >= knife_mount.STUD_TAP_WEB_MIN, label
    assert min(web for web, _ in webs.values()) == knife_mount.PIN_HOLE_FAR_SIDE_WEB


def test_the_knife_edge_keeps_five_degrees_of_rock_at_the_worst_case() -> None:
    # Ruling B: HEX_W 8.080, HEX_H 10.268 (.XXX); ridge 115.1 deg.
    assert (lever.HEX_W, lever.HEX_H, lever.HEX_BAND) == (8.080, 10.268, 0.13)
    assert lever.RIDGE_ANGLE_DEG == pytest.approx(115.137, abs=5e-3)
    # Spreading the dowels preserves five-degree rock without moving the
    # mount or lever: atan(0.11746/15.134), then t=14.8 tan(yaw)+0.05.
    assert asm.KNIFE_DOWEL_SPAN_MIN == pytest.approx(15.134)
    assert asm.KNIFE_MOUNT_YAW_DEG == pytest.approx(0.4446826439)
    assert asm.KNIFE_BORE_FAR_END_OFFSET == pytest.approx(0.1648677151)
    # Code review C09 (owner ruling T1): the print holds the ridge 4.040
    # +/-0.05 from each side face and each upper flank 122.4 +/-0.5 deg to its
    # side face.  The worst shoulder is 4.09 out on a flank 58.1 deg off the
    # vertical, so 2.5458 under the ridge: 6.636 deg in the smallest bore.
    assert lever.KNIFE_SHOULDER_X_MAX == pytest.approx(4.09)
    assert lever.KNIFE_FLANK_HALF_MAX_DEG == pytest.approx(58.1)
    assert lever.KNIFE_SHOULDER_DROP_MIN == pytest.approx(2.545801, abs=5e-6)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(6.636235, abs=5e-6)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG >= asm.KNIFE_FREE_ROCK_FLOOR_DEG == 5.0
    assert knife_mount.BORE_R_MIN == 6.0

    def rock(ridge_from_side: float, flank_to_side_deg: float) -> float:
        half = math.radians(180.0 - flank_to_side_deg)
        return knife_mount.free_rock_deg(
            asm.KNIFE_BORE_FAR_END_OFFSET,
            hex_w=2.0 * ridge_from_side,
            r_bore=knife_mount.BORE_R_MIN,
            shoulder_drop=ridge_from_side / math.tan(half),
        )

    # Every corner of the two printed bands: the proof's corner is the least.
    x_tol, a_tol = lever.RIDGE_FROM_SIDE_TOL, lever.KNIFE_FLANK_TO_SIDE_TOL_DEG
    corners = {
        (dx, da): rock(lever.RIDGE_FROM_SIDE + dx, lever.KNIFE_FLANK_TO_SIDE_DEG + da)
        for dx in (-x_tol, 0.0, x_tol)
        for da in (-a_tol, 0.0, a_tol)
    }
    assert min(corners, key=corners.get) == (x_tol, -a_tol)
    assert min(corners.values()) == pytest.approx(asm.KNIFE_FREE_ROCK_WORST_DEG)
    assert corners[(0.0, 0.0)] == pytest.approx(7.306, abs=5e-3)
    assert max(corners.values()) == pytest.approx(7.976, abs=5e-3)
    # The counterexample the old controls admitted (code review C09): the
    # included angle at its nominal, held by HexWidth and the angle only, with
    # the flanks split unevenly about the vertical at the widest .XXX
    # section.  One flank 2, 3 or 5 deg flatter drops the rock to 5.46, 4.71,
    # 3.17: under the floor from 3 deg.  T1 bounds each flank to its side
    # face, so no split past 0.5 deg passes the print.
    widest_half = (lever.HEX_W + lever.HEX_BAND) / 2.0
    for split, expected in ((2.0, 5.4628), (3.0, 4.7098), (5.0, 3.1666)):
        flank_to_side = 180.0 - (lever.RIDGE_ANGLE_DEG / 2.0 + split)
        assert rock(widest_half, flank_to_side) == pytest.approx(expected, abs=5e-4)
        assert flank_to_side < lever.KNIFE_FLANK_TO_SIDE_DEG - a_tol
        assert widest_half > lever.RIDGE_FROM_SIDE + x_tol
    # The width, now a reference, cannot reach the old widest section.
    assert 2.0 * lever.KNIFE_SHOULDER_X_MAX < lever.HEX_W + lever.HEX_BAND
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
    assert screw.THREAD == knife_mount.STUD_THREAD == "#10-24"
    assert THREAD_MAJOR_MM["#10-24"] == knife_mount.STUD_THREAD_MAJOR
    assert TAP_DRILL_MM["#10-24"] == knife_mount.STUD_TAP_DIA
