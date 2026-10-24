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
    # Owner ruling 2026-10-24 (T+H3): each pin presses 12.0 up into the
    # crossbar's blind ream and slips 9.5 deep into the knife mount.
    assert dowel.PRESS_DEPTH == top_frame.HANGER_PIN_HOLE_DEPTH == 12.0
    assert dowel.SLIP_DEPTH == knife_mount.PIN_HOLE_DEPTH == 9.5
    assert dowel.PROUD == pytest.approx(7.05)
    assert (dowel.PROUD_MIN, dowel.PROUD_MAX) == pytest.approx((5.996, 8.104))
    assert dowel.SLIP_DEPTH_CLEARANCE_MIN == pytest.approx(0.596)
    assert dowel.SLIP_DEPTH_CLEARANCE_MIN > 0.0
    assert dowel.PRESS_ENGAGEMENT_D_MIN == pytest.approx(3.388, abs=5e-4)
    assert dowel.PRESS_ENGAGEMENT_D_MIN >= dowel.PRESS_ENGAGEMENT_MIN_D == 1.5
    assert dowel.SLIP_ENGAGEMENT_D_MIN == pytest.approx(1.749, abs=5e-4)
    assert dowel.SLIP_ENGAGEMENT_D_MIN >= dowel.PRESS_ENGAGEMENT_MIN_D
    # The ream's +0/-0.010 band keeps the press at both catalogue limits.
    assert (dowel.PRESS_HOLE_DIA, dowel.PRESS_HOLE_DIA_BAND) == (3.175, (0.0, -0.010))
    assert dowel.PRESS_INTERFERENCE == pytest.approx((0.00254, 0.01762))
    assert dowel.PRESS_INTERFERENCE[0] > 0.0
    assert dowel.PRESS_INTERFERENCE_PRINTED == (0.0025, 0.0177)
    # Both parts' stations are the dowel pair's, and the assembly seats the
    # pair there, the -X (slot) pin first.
    assert dowel.PER_MOUNT == 2 and dowel.QUANTITY == 4
    pair = (-dowel.HANGER_OFFSET, dowel.HANGER_OFFSET)
    assert (
        (knife_mount.SLOT_X, knife_mount.PIN_HOLE_X) == top_frame.HANGER_PIN_XS == pair
    )
    assert asm.KNIFE_DOWEL_X_OFFSETS == pair
    # The pressed end on the ream floor, the free end hanging PROUD below
    # the clamped seat, clear of the knife mount's slip-hole floor.
    assert asm.KNIFE_DOWEL_Y == pytest.approx(
        asm.KNIFE_MOUNT_TOP_Y + top_frame.HANGER_PIN_HOLE_DEPTH
    )
    assert asm.KNIFE_DOWEL_END_Y == pytest.approx(asm.KNIFE_DOWEL_Y - dowel.LENGTH)
    assert asm.KNIFE_MOUNT_TOP_Y - asm.KNIFE_DOWEL_END_Y == pytest.approx(dowel.PROUD)
    assert asm.KNIFE_DOWEL_END_Y - (
        asm.KNIFE_MOUNT_TOP_Y - knife_mount.PIN_HOLE_DEPTH
    ) == pytest.approx(2.45)


def test_the_slip_band_and_the_screw_float_absorb_the_dowel_stations() -> None:
    assert dowel.SLIP_CLEARANCE_MIN == pytest.approx(0.02738)
    assert dowel.SLIP_CLEARANCE_MAX == pytest.approx(0.09246)
    assert 0.02 <= dowel.SLIP_CLEARANCE_MIN
    assert dowel.SLIP_CLEARANCE_MAX <= 0.10
    assert knife_mount.PIN_SLIP_PRINTED == (0.027, 0.093)
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
    # Owner ruling 2026-10-24 (T+H3), the block fitted either way round (each
    # ream .XXX from the screw axis).  Along X: 0.13 ream station + 0.075 tap
    # zone + 0.04623 B slip; across: 0.13 + 0.025 (the -X ream's 0.05 zone,
    # B on the -X pin) + 0.075 + (0.04623 + 0.04623 + 0.025) / 2.
    assert knife_mount.STUD_TAP_POSITION_TOL == 0.15
    assert top_frame.HANGER_PIN_X_TOL == 0.13
    assert top_frame.HANGER_PRESS_HOLE_POSITION_TOL == 0.05
    assert asm.HANGER_SCREW_MISMATCH_X == pytest.approx(0.25123)
    assert asm.HANGER_SCREW_MISMATCH_Z == pytest.approx(0.28873)
    assert asm.HANGER_SCREW_MISMATCH == pytest.approx(0.3827290501124784, abs=1e-12)
    # Drift reaches the hole's top end at the faced top, over the longest
    # printed grip (36.50 + 0.51), not the retired one-place cast band.
    assert asm.HANGER_SCREW_DRIFT == pytest.approx(
        math.tan(math.radians(top_frame.KEEPER_TAP_DRILL_WANDER_DEG))
        * (top_frame.HANGER_GRIP + top_frame.HANGER_GRIP_TOL)
    )
    assert asm.HANGER_SCREW_DRIFT == pytest.approx(0.1937856777669617, abs=1e-12)
    assert asm.HANGER_SCREW_FLOAT_SPARE == pytest.approx(0.03298527212056013, abs=1e-12)
    assert (
        asm.HANGER_SCREW_MISMATCH + asm.HANGER_SCREW_DRIFT
        < top_frame.HANGER_SCREW_FLOAT
    )

    # The tap zone Ø0.15 (R4 asked Ø0.25) leaves spare: the stack, each
    # mismatch carrying the zone's radius, closes at Ø0.1968; Ø0.20 and Ø0.25
    # overrun the float.
    def spare_at(zone: float) -> float:
        shift = (zone - knife_mount.STUD_TAP_POSITION_TOL) / 2.0
        mismatch = math.hypot(
            asm.HANGER_SCREW_MISMATCH_X + shift, asm.HANGER_SCREW_MISMATCH_Z + shift
        )
        return top_frame.HANGER_SCREW_FLOAT - mismatch - asm.HANGER_SCREW_DRIFT

    assert spare_at(0.15) == pytest.approx(asm.HANGER_SCREW_FLOAT_SPARE, abs=1e-12)
    assert spare_at(0.16) == pytest.approx(0.025930887746655973, abs=1e-12)
    assert spare_at(0.20) == pytest.approx(-0.002292287523314618, abs=1e-12)
    assert spare_at(0.25) == pytest.approx(-0.03758196696421495, abs=1e-12)
    assert spare_at(0.25) < spare_at(0.20) < 0.0 < spare_at(0.16)
    x0 = asm.HANGER_SCREW_MISMATCH_X - knife_mount.STUD_TAP_POSITION_TOL / 2.0
    z0 = asm.HANGER_SCREW_MISMATCH_Z - knife_mount.STUD_TAP_POSITION_TOL / 2.0
    reach = top_frame.HANGER_SCREW_FLOAT - asm.HANGER_SCREW_DRIFT
    half_zone_max = (
        -(x0 + z0) + math.sqrt((x0 + z0) ** 2 - 2.0 * (x0**2 + z0**2 - reach**2))
    ) / 2.0
    assert 2.0 * half_zone_max == pytest.approx(0.196751637364855, abs=1e-12)
    assert spare_at(2.0 * half_zone_max) == pytest.approx(0.0, abs=1e-12)
    assert 0.16 < 2.0 * half_zone_max < 0.20
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


def test_the_block_slot_takes_up_the_dowel_pair_spacing() -> None:
    # Owner ruling 2026-10-24 (T+H3): the slot moved from the crossbar to the
    # block, datum C, open to its -X face.  Same slip width as the round hole
    # (datum B), so the -X pin keeps its slip across it, and one floor.
    assert knife_mount.SLOT_WIDTH == knife_mount.PIN_HOLE_DIA == dowel.SLIP_HOLE_DIA
    assert knife_mount.SLOT_WIDTH_BAND == knife_mount.PIN_HOLE_DIA_BAND == (0.03, -0.03)
    assert knife_mount.SLOT_X == -knife_mount.PIN_HOLE_X == -7.632
    # Each crossbar ream stands .XXX from its own screw axis, so the -X pin
    # stands 15.264 +/-0.26 from the +X pin, B floating its loosest slip on
    # its own: 15.264 -/+ (0.26 + 0.046).  The block goes on either way round.
    assert dowel.SPAN == pytest.approx(15.264)
    assert dowel.SPAN_TOL == pytest.approx(2.0 * dowel.HANGER_OFFSET_TOL) == 0.26
    assert not hasattr(dowel, "SPAN_PLACES")
    assert knife_mount.SLOT_PIN_FROM_B == pytest.approx((14.95777, 15.57023))
    # Inward the slot's half-round end stops short of the nearest pin at
    # every .XX limit, so the slot walls, not its end, clock the block.
    assert (knife_mount.SLOT_END_FROM_B, knife_mount.SLOT_END_TOL) == (14.40, 0.51)
    assert knife_mount.SLOT_PIN_LOCATION_MARGIN == pytest.approx(0.04777)
    assert knife_mount.SLOT_PIN_LOCATION_MARGIN > 0.0
    # Outward it runs out through the -X face: the farthest pin still bears
    # wholly inside the thinnest block.
    assert knife_mount.SLOT_MOUTH_PIN_MARGIN == pytest.approx(1.86046)
    assert knife_mount.SLOT_MOUTH_PIN_MARGIN > 0.0
    # The slot's width frame: ⌖0.05 to A|B, the crossbar's former slot zone.
    assert knife_mount.SLOT_POSITION_TOL == 0.05


def test_the_slot_end_band_is_functional() -> None:
    # The .XX band on the slot end is functional: at its nearest the end
    # keeps 2.0 to the tap's thread; at its farthest it stays clear of the
    # nearest pin.  A .X end would lose both.
    assert knife_mount.SLOT_TAP_WEB == pytest.approx(2.135)
    assert knife_mount.SLOT_TAP_WEB >= knife_mount.STUD_TAP_WEB_MIN
    band_x = knife_mount._X
    widen = band_x - knife_mount.SLOT_END_TOL
    assert knife_mount.SLOT_PIN_LOCATION_MARGIN - widen == pytest.approx(-0.24223)
    assert knife_mount.SLOT_TAP_WEB - widen == pytest.approx(1.845)
    assert knife_mount.SLOT_PIN_LOCATION_MARGIN - widen < 0.0
    assert knife_mount.SLOT_TAP_WEB - widen < knife_mount.STUD_TAP_WEB_MIN


def test_the_crossbar_webs_hold_round_the_press_reams_and_knockouts() -> None:
    # Owner ruling 2026-10-24 (T+H3): both crossbar dowel holes are Ø3.175
    # +0/-0.010 blind reams, 12.0 deep from the faced underside, each pierced
    # by a knockout drilled through from the faced top, each 7.632 +/-0.13
    # from its own screw axis (the block fits either way round).
    stations = tuple(build_fr_top_frame.HANGER_X + x for x in top_frame.HANGER_PIN_XS)
    assert stations == pytest.approx((-22.632, -7.368))
    assert build_fr_top_frame.PIN_HOLE_X == pytest.approx(-7.368)
    assert build_fr_top_frame.BAR_X1 - build_fr_top_frame.BAR_X0 == pytest.approx(25.0)
    assert (build_fr_top_frame.BAR_X1 + build_fr_top_frame.BAR_X0) / 2.0 == -15.0
    assert build_fr_top_frame.HANGER_BAR_HALF_WIDTH_MIN == pytest.approx(12.1)
    assert top_frame.HANGER_CROSSBAR_CENTER_TOL == pytest.approx(0.05)
    assert (top_frame.HANGER_PIN_HOLE_DIA, top_frame.HANGER_PIN_HOLE_DIA_BAND) == (
        dowel.PRESS_HOLE_DIA,
        dowel.PRESS_HOLE_DIA_BAND,
    )
    # Every wall at its print-worst less the drill drift each hole takes up
    # its depth: drawing-guidelines.md rule 17 (walls and webs)'s 2.0 target
    # holds.  The reams are symmetric, so one pair of walls serves both.
    assert not hasattr(top_frame, "HANGER_PIN_NEG_STATION_TOL")
    assert not hasattr(build_fr_top_frame, "NEG_PIN_HOLE_BAR_WALL")
    walls = {
        "ream to bar face": (build_fr_top_frame.PIN_HOLE_BAR_WALL, 2.633479),
        "ream to screw hole": (build_fr_top_frame.PIN_HOLE_SCREW_WALL, 2.692957),
        "knockout to bar face": (build_fr_top_frame.KNOCKOUT_BAR_WALL, 2.972358),
        "knockout to screw hole": (build_fr_top_frame.KNOCKOUT_SCREW_WALL, 2.905072),
    }
    for label, (wall, expected) in walls.items():
        assert wall == pytest.approx(expected, abs=5e-6), label
        assert wall >= 2.0, label
    # Shortest finished grip (36.50 - 0.51) less the deepest ream floor 12.8.
    assert build_fr_top_frame.PIN_HOLE_FLOOR_MARGIN == pytest.approx(23.19)
    # The knockout leaves the pressed pin a land on the ream floor.
    assert top_frame.HANGER_PIN_FLOOR_LAND_MIN == pytest.approx(0.402)
    # The crossbar's washer stack charges the assembly's very mismatch.
    assert build_fr_top_frame.HANGER_SEAT_BOLT_MISMATCH == pytest.approx(
        asm.HANGER_SCREW_MISMATCH, abs=1e-12
    )


def test_the_datum_frame_is_the_zone_the_stacks_were_derived_on() -> None:
    # Owner ruling 2026-10-24 (T+H3): the block's frame is A (top seat), B
    # (the round slip hole) and C (the slot); the pair's spacing is the
    # crossbar's .XXX span, so the block carries no pattern frame.  Its bore
    # carries Ø0.20 to A|B|C, its only orientation control, which the rock
    # charges in full.
    assert knife_mount.GEOMETRIC_TOLERANCES_MM == {
        "knife-bore position": "0.20",
        "knife-hanger tap position": "0.15",
        "dowel slot position": "0.05",
    }
    assert knife_mount.KNIFE_BORE_ORIENTATION_TOL == knife_mount.KNIFE_BORE_POSITION_TOL
    assert knife_mount.KNIFE_BORE_POSITION_TOL == 0.20
    assert asm.HANGER_SCREW_MISMATCH == pytest.approx(0.38273, abs=5e-6)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(5.143546, abs=5e-6)
    # Enlarging the crossbar's ream position zone to Ø0.23 (it enters the
    # across leg twice: the -X ream off the +X ream's line, and the slot's
    # offset from B) overruns the screw float.
    z_at_023 = (
        top_frame.HANGER_PIN_X_TOL
        + 0.23 / 2.0
        + knife_mount.STUD_TAP_POSITION_TOL / 2.0
        + (dowel.SLIP_CLEARANCE_MAX + 0.23 / 2.0) / 2.0
    )
    mismatch_at_023 = math.hypot(asm.HANGER_SCREW_MISMATCH_X, z_at_023)
    assert mismatch_at_023 == pytest.approx(0.492609, abs=5e-6)
    assert mismatch_at_023 + asm.HANGER_SCREW_DRIFT > top_frame.HANGER_SCREW_FLOAT

    # The bore's Ø0.20 is the largest two-place zone the 5.0 deg floor
    # admits: Ø0.25 drops the worst rock to 4.64 deg.
    def worst_rock(bore_zone: float) -> float:
        offset = (
            asm.KNIFE_BORE_FAR_END_OFFSET
            - knife_mount.KNIFE_BORE_ORIENTATION_TOL
            + bore_zone
        )
        return knife_mount.free_rock_deg(
            offset,
            hex_w=2.0 * lever.KNIFE_SHOULDER_X_MAX,
            r_bore=knife_mount.BORE_R_MIN,
            shoulder_drop=lever.KNIFE_SHOULDER_DROP_MIN,
        )

    assert worst_rock(0.20) == pytest.approx(asm.KNIFE_FREE_ROCK_WORST_DEG)
    assert worst_rock(0.25) == pytest.approx(4.642670, abs=5e-6)
    assert worst_rock(0.25) < asm.KNIFE_FREE_ROCK_FLOOR_DEG <= worst_rock(0.20)


def test_the_knife_mount_webs_hold_round_the_hole_and_the_slot() -> None:
    assert knife_mount.PIN_HOLE_X == pytest.approx(dowel.SPAN / 2.0)
    # Same face-location scheme at functional .X, 25.4 wide; the +X hole
    # (datum B) stands 5.068 .XX from its face, the row 7.0 .X from front.
    assert knife_mount.BLK_HALF_X == 12.7
    assert knife_mount.PIN_HOLE_SIDE_DISTANCE == pytest.approx(5.068)
    assert knife_mount.PIN_HOLE_SIDE_TOL == knife_mount._XX
    assert knife_mount.HOLE_ROW_FACE_DISTANCE == 7.0
    assert knife_mount.HOLE_ROW_FACE_TOL == knife_mount._X
    assert knife_mount.BLOCK_SIZE_TOL == knife_mount._X
    assert knife_mount.BLOCK_HEIGHT_PRINTED == 29.6
    assert knife_mount.BORE_DIA_BAND == (0.03, 0.0)
    webs = {
        "round hole to +X face": (knife_mount.PIN_HOLE_SIDE_WEB, 2.923),
        "round hole to Z faces": (knife_mount.PIN_HOLE_Z_WEB, 3.765),
        "slot cheeks to Z faces": (knife_mount.SLOT_CHEEK_WEB, 3.362237),
        "slot end to -X face": (knife_mount.SLOT_END_TO_MOUTH, 2.477),
        "tap to Z faces": (knife_mount.STUD_TAP_Z_WALL, 2.778783),
        "bore to side faces": (knife_mount.BORE_SIDE_WEB, 5.275),
        "bore to bottom face": (knife_mount.BORE_BOTTOM_WALL, 2.065),
        "round hole to tap": (knife_mount.PIN_HOLE_TAP_WEB, 3.509),
        "slot end to tap": (knife_mount.SLOT_TAP_WEB, 2.135),
        "round hole to bore": (knife_mount.PIN_HOLE_BORE_WEB, 5.78428),
        "slot to bore": (knife_mount.SLOT_BORE_WEB, 5.161132),
    }
    for label, (web, expected) in webs.items():
        assert web == pytest.approx(expected, abs=5e-4), label
        assert web >= knife_mount.STUD_TAP_WEB_MIN, label
    assert min(web for web, _ in webs.values()) == knife_mount.BORE_BOTTOM_WALL


def test_the_knife_edge_keeps_five_degrees_of_rock_at_the_worst_case() -> None:
    # Ruling B: HEX_W 8.080, HEX_H 10.268 (.XXX); ridge 115.1 deg.
    assert (lever.HEX_W, lever.HEX_H, lever.HEX_BAND) == (8.080, 10.268, 0.13)
    assert lever.RIDGE_ANGLE_DEG == pytest.approx(115.137, abs=5e-3)
    # Spreading the dowels preserves five-degree rock without moving the
    # mount or lever: atan(0.11746/15.004), the span's .XXX-per-ream minimum,
    # then t=14.8 tan(yaw)+0.20, the bore's whole Ø0.20 zone to A|B|C (owner
    # ruling 2026-10-24, T+H3).
    assert asm.KNIFE_DOWEL_SPAN_MIN == pytest.approx(15.004)
    assert asm.KNIFE_MOUNT_YAW_DEG == pytest.approx(0.448535376)
    assert asm.KNIFE_BORE_FAR_END_OFFSET == pytest.approx(0.3158629699)
    # Code review C09 (owner ruling T1): the print holds the ridge 4.040
    # +/-0.05 from each side face and each upper flank 122.4 +/-0.5 deg to its
    # side face.  The worst shoulder is 4.09 out on a flank 58.1 deg off the
    # vertical, so 2.5458 under the ridge: 5.144 deg in the smallest bore.
    assert lever.KNIFE_SHOULDER_X_MAX == pytest.approx(4.09)
    assert lever.KNIFE_FLANK_HALF_MAX_DEG == pytest.approx(58.1)
    assert lever.KNIFE_SHOULDER_DROP_MIN == pytest.approx(2.545801, abs=5e-6)
    assert asm.KNIFE_FREE_ROCK_WORST_DEG == pytest.approx(5.143546, abs=5e-6)
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
    assert corners[(0.0, 0.0)] == pytest.approx(5.813, abs=5e-3)
    assert max(corners.values()) == pytest.approx(6.483, abs=5e-3)
    # The counterexample the old controls admitted (code review C09): the
    # included angle at its nominal, held by HexWidth and the angle only, with
    # the flanks split unevenly about the vertical at the widest .XXX
    # section.  One flank 2, 3 or 5 deg flatter drops the rock to 3.97, 3.22,
    # 1.67: under the floor from 2 deg.  T1 bounds each flank to its side
    # face, so no split past 0.5 deg passes the print.
    widest_half = (lever.HEX_W + lever.HEX_BAND) / 2.0
    for split, expected in ((2.0, 3.9690), (3.0, 3.2151), (5.0, 1.6700)):
        flank_to_side = 180.0 - (lever.RIDGE_ANGLE_DEG / 2.0 + split)
        assert rock(widest_half, flank_to_side) == pytest.approx(expected, abs=5e-4)
        assert rock(widest_half, flank_to_side) < asm.KNIFE_FREE_ROCK_FLOOR_DEG
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
    # Owner ruling 2026-10-24 (T+H3): the dowel press row is the crossbar
    # ream's (smallest Ø3.165, 12.0 deep), checked at the top level.
    assert _interference_contracts._KNIFE_DOWEL_HOLE_MIN == pytest.approx(
        dowel.PRESS_HOLE_DIA + min(dowel.PRESS_HOLE_DIA_BAND)
    )
    assert _interference_contracts._KNIFE_DOWEL_DIA_MAX == pytest.approx(dowel.DIA_MAX)
    assert _interference_contracts._KNIFE_DOWEL_PRESS_DEPTH == pytest.approx(
        dowel.PRESS_DEPTH
    )
    assert _interference_contracts._KNIFE_DOWEL_PRESS_DEPTH == pytest.approx(
        top_frame.HANGER_PIN_HOLE_DEPTH
    )
    assert screw.THREAD == knife_mount.STUD_THREAD == "#10-24"
    assert THREAD_MAJOR_MM["#10-24"] == knife_mount.STUD_THREAD_MAJOR
    assert TAP_DRILL_MM["#10-24"] == knife_mount.STUD_TAP_DIA
